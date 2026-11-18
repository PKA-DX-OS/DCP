# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""T-02: thông tin giấy phép đã ký và tra cứu công khai."""

import time
import urllib.request

import httpx

from tests.integration._ho_so import GATEWAY_URL, cap_phep_den_buoc_duyet, complete_task, get_token, run_sql


def test_T02_thong_tin_giay_phep_rpc_and_public_verify():
    """
    T-02: Kiểm tra RPC app_cap_phep.thong_tin_giay_phep và API xác minh công khai:
    - Hồ sơ đã cấp phép: trả về đủ số giấy phép, họ tên người ký, thuật toán, mã công khai.
    - Quyền truy cập: cdt.lan gọi hồ sơ của cdt.minh -> bị từ chối 403.
    - Tra cứu công khai /kiem-tra/{public_code} không cần đăng nhập trả về 'Hợp lệ'.
    - U-01: không còn tải bản gốc công khai; bản gốc tải qua file_url kèm token của chủ hồ sơ.
    """
    token_minh = get_token("cdt.minh")
    token_lan = get_token("cdt.lan")

    # 1. Tự cấp một giấy phép cho hồ sơ mới của cdt.minh (không dựa vào dữ liệu test khác)
    st = cap_phep_den_buoc_duyet("cdt.minh", {
        "ho_ten": "Tran Van T02",
        "cccd": "001200000022",
        "dien_thoai": "0988000022",
        "dia_chi_cong_trinh": "22 Duong T02 Phuong A",
        "thua_dat": "Thua 22 To 2",
        "so_tang": 2,
        "dien_tich_san_m2": 130.0,
        "khu_quan_ly_kien_truc": True,
    }, tag_prefix="T02_permit")
    r = complete_task(st["tokens"]["ld.hoa"], st["task"]["id"],
                      {"dongYCapPhep": True, "pheDuyet": True, "yKienPheDuyet": "Đồng ý cấp phép"})
    assert r.status_code == 200, f"Lãnh đạo duyệt cấp phép thất bại: {r.status_code} {r.text}"
    hs_id = st["ho_so"]["id"]
    for _ in range(10):
        if run_sql(f"SELECT count(*) FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';") == "1":
            break
        time.sleep(1)
    assert run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';") == "DA_CAP"

    # 2. cdt.minh gọi RPC thong_tin_giay_phep
    with httpx.Client(timeout=10.0) as client:
        res = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/thong_tin_giay_phep",
            headers={"Authorization": f"Bearer {token_minh}"},
            json={"p_ho_so_id": hs_id},
        )
        assert res.status_code == 200, f"cdt.minh phải gọi được thong_tin_giay_phep: {res.text}"
        data = res.json()
        assert data.get("so_giay_phep"), "Phải có số giấy phép"
        assert ("Ed25519" in str(data.get("thuat_toan"))) or ("PAdES" in str(data.get("thuat_toan"))), "Thuật toán phải ghi rõ Ed25519 hoặc PAdES"
        assert data.get("ma_cong_khai"), "Phải có mã công khai"
        assert data.get("nguoi_ky"), "Phải có tên người ký"
        assert not data["nguoi_ky"].startswith("ld."), "Tên người ký phải là họ tên từ users_directory, không phải sub"
        public_code = data["ma_cong_khai"]

        # 3. cdt.lan (khác chủ) gọi RPC với hồ sơ của cdt.minh -> 403 Forbidden
        res_lan = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/thong_tin_giay_phep",
            headers={"Authorization": f"Bearer {token_lan}"},
            json={"p_ho_so_id": hs_id},
        )
        assert res_lan.status_code == 403, f"cdt.lan phải bị từ chối 403 khi xem giấy phép hồ sơ khác, nhận: {res_lan.status_code}"

    # 4. Tra cứu công khai /kiem-tra/{public_code} không cần token
    verify_url = f"{GATEWAY_URL}/kiem-tra/{public_code}"
    req_pub = urllib.request.Request(verify_url, headers={"Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req_pub, timeout=5) as pub_resp:
        assert pub_resp.status == 200
        html = pub_resp.read().decode("utf-8")
        assert "Hợp lệ" in html or "Hop_le" in html, f"Trang tra cứu phải thể hiện trạng thái Hợp lệ: {html[:200]}"
        assert public_code in html, "Trang tra cứu phải hiển thị mã công khai"

    # 5. U-01: đường tải công khai cũ không còn trả PDF
    old_url = f"{GATEWAY_URL}/kiem-tra/{public_code}/download"
    with httpx.Client(timeout=5.0) as client:
        old_resp = client.get(old_url)
        assert old_resp.status_code in (404, 405), f"Không được tải bản gốc công khai: {old_resp.status_code}"
        assert not old_resp.content.startswith(b"%PDF")
        assert "cccd" not in html.lower(), "Trang công khai không được chứa CCCD"

        # Bản gốc chỉ tải được kèm token của chủ hồ sơ
        file_url = data.get("file_url")
        assert file_url and file_url.startswith("/api/v1/docs/"), f"file_url phải trỏ tới endpoint có xác thực: {file_url}"
        no_tok = client.get(f"{GATEWAY_URL}{file_url}")
        assert no_tok.status_code == 401, f"Không token phải 401: {no_tok.status_code}"
        dl = client.get(f"{GATEWAY_URL}{file_url}", headers={"Authorization": f"Bearer {token_minh}"})
        assert dl.status_code == 200 and dl.content.startswith(b"%PDF"), f"Chủ hồ sơ phải tải được: {dl.status_code}"
        lan = client.get(f"{GATEWAY_URL}{file_url}", headers={"Authorization": f"Bearer {token_lan}"})
        assert lan.status_code == 404, f"Người khác không được tải bản gốc: {lan.status_code}"
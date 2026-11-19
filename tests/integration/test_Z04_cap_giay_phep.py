# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Z-04: lãnh đạo duyệt thì hook tự ký số, sinh đúng một giấy phép và một công trình."""

import time

import httpx

from tests.integration._ho_so import GATEWAY_URL, cap_phep_den_buoc_duyet, complete_task, run_sql


def test_Z04_permit_auto_generation_and_signing():
    # 1-4. Nộp hồ sơ, tiếp nhận, phân công, thẩm định
    st = cap_phep_den_buoc_duyet("cdt.minh", {
        "ho_ten": "Tran Thi Z04",
        "cccd": "001200000044",
        "dien_thoai": "0988776655",
        "dia_chi_cong_trinh": "123 Duong Z04 Phuong A",
        "thua_dat": "Thua 4 To 4",
        "so_tang": 2,
        "dien_tich_san_m2": 120.0,
        "khu_quan_ly_kien_truc": True,
    }, tag_prefix="Z04_cap_giay_phep")
    hs_id = st["ho_so"]["id"]
    assert st["ho_so"]["ma_ho_so"], "Hồ sơ phải có mã hồ sơ"

    # 5. Lãnh đạo phê duyệt: taskDuyetCapPhep -> hook ký số và cấp phép
    r = complete_task(st["tokens"]["ld.hoa"], st["task"]["id"],
                      {"dongYCapPhep": True, "pheDuyet": True, "yKienPheDuyet": "Đồng ý cấp phép"})
    assert r.status_code == 200, f"Lãnh đạo duyệt cấp phép thất bại: {r.status_code} {r.text}"

    gp_count = 0
    for _ in range(10):
        gp_count = int(run_sql(f"SELECT count(*) FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';") or "0")
        if gp_count:
            break
        time.sleep(1)

    # 6a. Đúng 1 giấy phép, số đúng định dạng GPXD-<tenant>-<năm>-<số>
    assert gp_count == 1, f"Kỳ vọng đúng 1 giấy phép được sinh ra, thực tế: {gp_count}"
    so_gp = run_sql(f"SELECT so_giay_phep FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';")
    assert so_gp.startswith("GPXD-phuong-a-"), f"Số giấy phép phải đúng định dạng GPXD-tenant-yyyy-seq: {so_gp}"
    signed_doc_id = run_sql(f"SELECT signed_doc_id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';")
    assert signed_doc_id, "Giấy phép phải gắn với signed_doc_id"

    # 6b. Văn bản ký số ở trạng thái valid và có mã công khai
    doc_status = run_sql(f"SELECT status FROM core.signed_docs WHERE id = '{signed_doc_id}';")
    assert doc_status == "valid", f"Trạng thái văn bản ký số phải là 'valid', thực tế: {doc_status}"
    public_code = run_sql(f"SELECT public_code FROM core.signed_docs WHERE id = '{signed_doc_id}';")
    assert public_code, "Văn bản phải có public_code"

    # 6c. Đúng 1 công trình gắn với giấy phép
    ct_count = int(run_sql(
        "SELECT count(*) FROM app_cap_phep.cong_trinh WHERE giay_phep_id = "
        f"(SELECT id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}');"
    ) or "0")
    assert ct_count == 1, f"Kỳ vọng đúng 1 công trình gắn với giấy phép, thực tế: {ct_count}"

    # 6d. Hồ sơ ở trạng thái DA_CAP
    hs_status = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")
    assert hs_status == "DA_CAP", f"Trạng thái hồ sơ phải là DA_CAP, thực tế: {hs_status}"

    # 6e. Tra cứu công khai trả 200 và trạng thái hợp lệ
    chk = httpx.get(f"{GATEWAY_URL}/kiem-tra/{public_code}", headers={"Accept": "application/json"}, timeout=10.0)
    assert chk.status_code == 200, f"Tra cứu công khai /kiem-tra/{public_code} phải trả 200: {chk.status_code}"
    assert chk.json().get("trang_thai") == "Hop_le", f"Giấy phép vừa ký phải hợp lệ: {chk.text}"

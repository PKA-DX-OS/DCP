# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import httpx

from tests.integration._ho_so import GATEWAY_URL, get_token, submit_dossier


def test_T09_notifications_role_isolation_and_persistence():
    """
    T-09: Kiểm tra hệ thống chuông thông báo:
    - Khi cdt.minh nộp hồ sơ, cán bộ một cửa cùng phường (mc.thu) nhận được thông báo lưu trữ.
    - cdt.lan không nhận được thông báo này (cô lập theo vai trò).
    - mc.thu đánh dấu đã đọc thành công.
    - Đăng xuất / gọi lại API vẫn thấy danh sách thông báo đã lưu.
    """
    token_minh = get_token("cdt.minh")
    token_thu = get_token("mc.thu")
    token_lan = get_token("cdt.lan")

    with httpx.Client(timeout=60.0) as client:
        # 1. cdt.minh nộp hồ sơ mới
        res_nop = submit_dossier(token_minh, {
                "ho_ten": "Trần Văn Minh",
                "cccd": "001200112233",
                "dien_thoai": "0912345678",
                "dia_chi_cong_trinh": "456 Phố T09 Thông Báo",
                "thua_dat": "T09-99",
                "so_tang": 2,
                "dien_tich_san_m2": 120.0,
                "khu_quan_ly_kien_truc": True,
            }, tag_prefix="T09_notifications", client=client)
        assert res_nop.status_code == 200, f"Lỗi nộp hồ sơ: {res_nop.status_code} - {res_nop.text}"
        data_nop = res_nop.json()
        ma_ho_so = data_nop["ma_ho_so"]

        # 2. mc.thu gọi lay_thong_bao -> Có thông báo hồ sơ mới
        res_notif_thu = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/lay_thong_bao",
            headers={"Authorization": f"Bearer {token_thu}"},
            json={},
        )
        assert res_notif_thu.status_code == 200, f"Lỗi lấy thông báo mc.thu: {res_notif_thu.status_code} - {res_notif_thu.text}"
        list_thu = res_notif_thu.json()
        assert isinstance(list_thu, list), f"Phản hồi thông báo phải là danh sách: {list_thu}"

        matched_notif = next((n for n in list_thu if ma_ho_so in (n.get("title", "") + n.get("body", ""))), None)
        assert matched_notif is not None, f"mc.thu không nhận được thông báo cho hồ sơ {ma_ho_so}: {list_thu}"
        assert matched_notif.get("read_at") is None, "Thông báo mới phải chưa đọc"

        # 3. cdt.lan gọi lay_thong_bao -> Không có thông báo hồ sơ của cdt.minh
        res_notif_lan = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/lay_thong_bao",
            headers={"Authorization": f"Bearer {token_lan}"},
            json={},
        )
        assert res_notif_lan.status_code == 200
        list_lan = res_notif_lan.json()
        lan_matched = next((n for n in list_lan if ma_ho_so in (n.get("title", "") + n.get("body", ""))), None)
        assert lan_matched is None, f"cdt.lan không được phép thấy thông báo của cán bộ/hồ sơ khác: {lan_matched}"

        # 4. mc.thu đánh dấu đã đọc
        notif_id = matched_notif["id"]
        res_read = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/danh_dau_da_doc",
            headers={"Authorization": f"Bearer {token_thu}"},
            json={"p_id": notif_id},
        )
        assert res_read.status_code == 200, f"Lỗi đánh dấu đã đọc: {res_read.status_code} - {res_read.text}"

        # 5. Gọi lại lay_thong_bao -> Đã lưu trạng thái read_at
        res_after = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/lay_thong_bao",
            headers={"Authorization": f"Bearer {token_thu}"},
            json={},
        )
        assert res_after.status_code == 200
        list_after = res_after.json()
        updated_notif = next((n for n in list_after if n["id"] == notif_id), None)
        assert updated_notif is not None
        assert updated_notif.get("read_at") is not None, "read_at phải được cập nhật"

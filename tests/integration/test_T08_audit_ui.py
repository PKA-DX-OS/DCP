# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import httpx

from tests.integration._ho_so import GATEWAY_URL, get_token, sub_of, submit_dossier


def test_T08_applicant_dossier_audit_log_access():
    """
    T-08: Kiểm tra nhật ký truy cập hồ sơ dành cho chủ đầu tư:
    1. cdt.minh nộp hồ sơ.
    2. td.cuong (chưa phân công) gửi yêu cầu truy cập khẩn cấp kèm lý do.
    3. ld.hoa phê duyệt yêu cầu truy cập khẩn.
    4. cdt.minh gọi RPC lay_nhat_ky_ho_so:
       - Thấy thao tác 'break_glass.requested' hoặc 'break_glass.approved'
       - Có họ tên cán bộ 'Vũ Quốc Cường' (actor_name)
       - Có lý do khẩn cấp (detail->reason)
    5. cdt.lan gọi RPC lay_nhat_ky_ho_so với hồ sơ của cdt.minh -> 403 / Bị từ chối.
    """
    token_minh = get_token("cdt.minh")
    token_lan = get_token("cdt.lan")
    token_cuong = get_token("td.cuong")
    token_hoa = get_token("ld.hoa")

    with httpx.Client(timeout=60.0) as client:
        # 1. cdt.minh nộp hồ sơ
        res_nop = submit_dossier(token_minh, {
                "ho_ten": "Trần Văn Minh",
                "cccd": "001200112233",
                "dien_thoai": "0912345678",
                "dia_chi_cong_trinh": "123 Đường T08 Audit",
                "thua_dat": "T08-01",
                "so_tang": 3,
                "dien_tich_san_m2": 150.0,
                "khu_quan_ly_kien_truc": True,
            }, tag_prefix="T08_audit_ui", client=client)
        assert res_nop.status_code == 200, f"Lỗi nộp hồ sơ: {res_nop.status_code} - {res_nop.text}"
        ho_so_id = res_nop.json()["id"]

        # 2. td.cuong gửi yêu cầu break-glass kèm lý do
        reason_text = "Kiểm tra khẩn cấp phản ánh xây dựng trái phép từ công dân"
        res_bg = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/xin_truy_cap_khan",
            headers={"Authorization": f"Bearer {token_cuong}"},
            json={
                "p_ho_so_id": ho_so_id,
                "p_ly_do": reason_text,
            },
        )
        assert res_bg.status_code == 200, f"Lỗi xin break-glass: {res_bg.status_code} - {res_bg.text}"

        # 3. ld.hoa duyệt truy cập khẩn
        res_approve = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/duyet_truy_cap_khan",
            headers={"Authorization": f"Bearer {token_hoa}"},
            json={
                "p_ho_so_id": ho_so_id,
                "p_user_sub": sub_of(token_cuong),
                "p_dong_y": True,
            },
        )
        assert res_approve.status_code == 200, f"Lỗi duyệt break-glass: {res_approve.status_code} - {res_approve.text}"

        # 4. cdt.minh gọi lay_nhat_ky_ho_so
        res_audit = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/lay_nhat_ky_ho_so",
            headers={"Authorization": f"Bearer {token_minh}"},
            json={"p_ho_so_id": ho_so_id, "p_limit": 50},
        )
        assert res_audit.status_code == 200, f"Lỗi lấy nhật ký: {res_audit.status_code} - {res_audit.text}"
        audit_items = res_audit.json()
        assert isinstance(audit_items, list) and len(audit_items) > 0

        # Kiểm tra sự xuất hiện của dòng break-glass với tên và lý do
        bg_items = [
            it for it in audit_items
            if "break_glass" in it.get("action", "") or "truy_cap_khan" in it.get("action", "")
        ]
        assert len(bg_items) > 0, f"Không tìm thấy bản ghi truy cập khẩn trong nhật ký: {audit_items}"

        bg_req = next((it for it in bg_items if it.get("action") == "break_glass.requested"), bg_items[0])
        assert "Vũ Quốc Cường" in (bg_req.get("actor_name") or ""), f"Tên cán bộ không khớp: {bg_req}"
        detail = bg_req.get("detail", {})
        assert reason_text in (detail.get("reason") or detail.get("ly_do") or ""), f"Lý do không khớp: {detail}"

        # 5. cdt.lan gọi lay_nhat_ky_ho_so trên hồ sơ của cdt.minh -> 403 / ACCESS_DENIED
        res_lan = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/lay_nhat_ky_ho_so",
            headers={"Authorization": f"Bearer {token_lan}"},
            json={"p_ho_so_id": ho_so_id, "p_limit": 50},
        )
        assert res_lan.status_code == 403 or (res_lan.status_code == 200 and res_lan.json().get("ma_loi") == "ACCESS_DENIED"), \
            f"Kỳ vọng bị từ chối khi cdt.lan truy cập hồ sơ cdt.minh, nhận: {res_lan.status_code} - {res_lan.text}"

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""T-03: màn hình công trình và hậu kiểm (danh sách công trình, lập phiếu kiểm tra)."""

import httpx

from tests.integration._ho_so import GATEWAY_URL, get_token


def test_T03_construction_view_and_inspection_workflow():
    """
    T-03: Kiểm tra hiển thị công trình và hậu kiểm:
    1. kt.an (dx:auditor) truy vấn danh sách công trình phải nhận được danh sách
       (công trình mẫu CT-01 của seed; không bị rỗng do lỗi cột created_at).
    2. tt.khanh (trat-tu-xd) tạo phiếu kiểm tra chủ động qua RPC lap_phieu_kiem_tra.
    3. cdt.lan không có quyền truy cập phiếu kiểm tra (403/0 dòng).
    4. View v_cong_trinh, v_phieu_kiem_tra trả mã hồ sơ cho giao diện.

    Chưa kiểm tra mô phỏng cảm biến (POST /api/v1/ingest/demo-sensor): service
    ingest hiện chưa có endpoint này.
    """
    token_an = get_token("kt.an")
    token_khanh = get_token("tt.khanh")
    token_lan = get_token("cdt.lan")

    # 1. Kiểm tra API công trình với kt.an (trước đây bị lỗi 400 và nuốt thành [])
    with httpx.Client(timeout=10.0) as client:
        resp_an = client.get(
            f"{GATEWAY_URL}/api/v1/rest/cong_trinh?order=created_at.desc",
            headers={"Authorization": f"Bearer {token_an}"},
        )
        assert resp_an.status_code == 200, f"kt.an gọi cong_trinh?order=created_at.desc phải 200, nhận: {resp_an.status_code} - {resp_an.text}"
        constructions = resp_an.json()
        assert len(constructions) > 0, "kt.an phải thấy các công trình đã được cấp phép trong tenant của mình"
        target_ct = constructions[0]
        assert target_ct.get("ma_cong_trinh"), f"Công trình phải có mã: {target_ct}"

        # 2. tt.khanh tạo phiếu kiểm tra chủ động cho công trình
        phieu_resp = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/lap_phieu_kiem_tra",
            headers={"Authorization": f"Bearer {token_khanh}"},
            json={
                "p_cong_trinh_id": target_ct["id"],
                "p_ghi_chu": "Kiểm tra định kỳ hiện trường",
            },
        )
        assert phieu_resp.status_code == 200, f"tt.khanh tạo phiếu kiểm tra chủ động phải 200: {phieu_resp.text}"
        phieu_id = phieu_resp.json().get("id") or phieu_resp.json().get("phieu_id")
        assert phieu_id, "Phiếu kiểm tra phải được tạo thành công"

        # tt.khanh đọc lại được phiếu vừa lập
        phieu_khanh = client.get(
            f"{GATEWAY_URL}/api/v1/rest/phieu_kiem_tra?id=eq.{phieu_id}",
            headers={"Authorization": f"Bearer {token_khanh}"},
        )
        assert phieu_khanh.status_code == 200 and len(phieu_khanh.json()) == 1, (
            f"tt.khanh phải thấy phiếu vừa lập: {phieu_khanh.status_code} {phieu_khanh.text}"
        )

        # 3. cdt.lan gọi đọc phiếu kiểm tra của phường -> 403 hoặc 0 dòng
        phieu_lan = client.get(
            f"{GATEWAY_URL}/api/v1/rest/phieu_kiem_tra?id=eq.{phieu_id}",
            headers={"Authorization": f"Bearer {token_lan}"},
        )
        # PostgREST RLS sẽ trả 200 với mảng rỗng [] hoặc 403
        if phieu_lan.status_code == 200:
            assert len(phieu_lan.json()) == 0, "cdt.lan không được thấy phiếu kiểm tra của đơn vị"
        else:
            assert phieu_lan.status_code == 403, f"cdt.lan phải bị từ chối xem phiếu: {phieu_lan.status_code}"

        # 4. Kiểm tra truy vấn khung nhìn v_cong_trinh và v_phieu_kiem_tra
        v_ct_resp = client.get(
            f"{GATEWAY_URL}/api/v1/rest/v_cong_trinh?order=created_at.desc",
            headers={"Authorization": f"Bearer {token_an}"},
        )
        assert v_ct_resp.status_code == 200, f"kt.an truy vấn v_cong_trinh phải 200: {v_ct_resp.text}"
        v_ct_data = v_ct_resp.json()
        assert len(v_ct_data) > 0, "v_cong_trinh phải có dữ liệu"
        assert "ma_ho_so" in v_ct_data[0], "v_cong_trinh phải có cột ma_ho_so thay vì UUID"

        v_pk_resp = client.get(
            f"{GATEWAY_URL}/api/v1/rest/v_phieu_kiem_tra?order=created_at.desc",
            headers={"Authorization": f"Bearer {token_an}"},
        )
        assert v_pk_resp.status_code == 200, f"kt.an truy vấn v_phieu_kiem_tra phải 200: {v_pk_resp.text}"

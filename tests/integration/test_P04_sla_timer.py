# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy cho lỗi P-04:
- Boundary timer SLA trong BPMN cap-phep được kích hoạt theo thời hạn động (${han_buoc_at}).
- Đặt SLA của taskKiemTraHopLe = PT1M qua biến môi trường test / biến ghi đè quy trình.
- Sau khi quá hạn (chờ tối đa 150 giây):
  + Bản ghi hồ sơ có cờ qua_han = true.
  + Ghi nhận sự kiện audit sla.qua_han trong core.audit_log.
  + Nhiệm vụ taskKiemTraHopLe vẫn duy trì mở (timer non-interrupting, không ngắt luồng).
"""

import time
import uuid

import httpx

from tests.integration._ho_so import GATEWAY_URL, flowable, get_token, run_sql, sub_of


def test_P04_sla_timer_expiration_and_audit():
    # SLA của taskKiemTraHopLe rút còn 1 phút qua biến quy trình _test_sla (service flow đọc khi khởi động)
    token_cdt = get_token("cdt.minh")
    headers = {"Authorization": f"Bearer {token_cdt}", "Content-Type": "application/json"}

    unique_code = f"CP-P04-{uuid.uuid4().hex[:6].upper()}"
    dossier_id = str(uuid.uuid4())
    cdt_sub = sub_of(token_cdt)

    # 1. Nộp hồ sơ và ghi nhận vào CSDL
    run_sql(f"""
    INSERT INTO app_cap_phep.ho_so (
        id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
        dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2,
        khu_quan_ly_kien_truc, trang_thai, buoc, han_tong_at
    ) VALUES (
        '{dossier_id}'::uuid, 'phuong-a', '{unique_code}', '{cdt_sub}', 'Trần Văn Minh',
        '001099001234', '0901234567', 'Số 99 Phố SLA Test P04', 'Thửa 99 Tờ 99', 2, 100.0,
        true, 'DA_NOP', 'tiep_nhan', now() + interval '15 days'
    );
    """)

    proc_id = None
    try:
        # 2. Khởi động quy trình BPMN thông qua facade service flow
        with httpx.Client(base_url=GATEWAY_URL, timeout=15.0) as client:
            resp = client.post(
                "/api/v1/flow/processes/start",
                headers=headers,
                json={
                    "process_key": "cap-phep",
                    "business_key": unique_code,
                    "variables": {
                        "ma_ho_so": unique_code,
                        "ho_so_id": dossier_id,
                        "chu_dau_tu_sub": cdt_sub,
                        "tenant": "phuong-a",
                        "dien_tich_san_m2": 100.0,
                        "khu_quan_ly_kien_truc": True,
                        "_test_sla": {"taskKiemTraHopLe": "PT1M"},
                    },
                },
            )
            assert resp.status_code in (200, 201), f"Lỗi khởi động quy trình flow: {resp.text}"
            proc_id = resp.json().get("process_id")
            assert proc_id, "Không nhận được process_id từ dịch vụ flow"

        # 3. Chờ boundary timer quá hạn (tối đa 150 giây)
        is_qua_han = False
        audit_found = False
        start_wait = time.time()
        timeout_seconds = 150

        while time.time() - start_wait < timeout_seconds:
            # Kiểm tra cờ qua_han trong CSDL
            qua_han_val = run_sql(f"SELECT qua_han FROM app_cap_phep.ho_so WHERE id = '{dossier_id}';")
            if qua_han_val == "t":
                is_qua_han = True

            # Kiểm tra sự kiện kiểm toán sla.qua_han
            audit_count = run_sql(f"SELECT count(*) FROM core.audit_log WHERE action = 'sla.qua_han' AND object_id = '{dossier_id}';")
            if int(audit_count or "0") > 0:
                audit_found = True

            if is_qua_han and audit_found:
                break
            time.sleep(5)

        elapsed = time.time() - start_wait
        assert is_qua_han, f"Hồ sơ {unique_code} chưa được cập nhật qua_han = true sau {elapsed:.1f}s (tối đa {timeout_seconds}s)"
        assert audit_found, f"Chưa phát sinh bản ghi kiểm toán sla.qua_han cho hồ sơ {unique_code} sau {elapsed:.1f}s"

        # 4. Kiểm tra nhiệm vụ taskKiemTraHopLe vẫn còn mở (timer non-interrupting, không ngắt quy trình)
        with flowable() as fl_client:
            tasks_res = fl_client.get(f"/service/runtime/tasks?processInstanceId={proc_id}")
            assert tasks_res.status_code == 200, f"Lỗi lấy danh sách nhiệm vụ Flowable: {tasks_res.text}"
            tasks_data = tasks_res.json().get("data", [])
            assert len(tasks_data) >= 1, f"Kỳ vọng nhiệm vụ vẫn còn mở sau timer, nhưng không có task nào: {tasks_data}"
            task_defs = [t.get("taskDefinitionKey") for t in tasks_data]
            assert "taskKiemTraHopLe" in task_defs, f"Kỳ vọng taskKiemTraHopLe vẫn mở, thực tế: {task_defs}"

    finally:
        # Dọn dẹp dữ liệu kiểm thử quy trình và hồ sơ
        if proc_id:
            try:
                with flowable() as fl_client:
                    fl_client.delete(f"/service/runtime/process-instances/{proc_id}")
            except Exception:
                pass
        run_sql(
            f"DELETE FROM app_cap_phep.ho_so_lich_su WHERE ho_so_id = '{dossier_id}';"
            f"DELETE FROM app_cap_phep.ho_so WHERE id = '{dossier_id}';"
        )

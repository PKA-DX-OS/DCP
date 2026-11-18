# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""N-03: doc-sign lỗi lúc lãnh đạo duyệt thì quy trình giữ nguyên trạng thái và thử lại được.

Test tạm dừng container dxos-doc-sign rồi bật lại trong `finally`.
"""

import subprocess
import time

import httpx

from tests.integration._ho_so import GATEWAY_URL, cap_phep_den_buoc_duyet, complete_task, run_sql


def _cho_doc_sign_san_sang() -> None:
    for _ in range(30):
        res = subprocess.run(
            ["docker", "inspect", "dxos-doc-sign", "--format", "{{.State.Health.Status}}"],
            capture_output=True, text=True,
        )
        if res.stdout.strip() == "healthy":
            return
        time.sleep(1)
    raise AssertionError("dxos-doc-sign không về trạng thái healthy sau 30 giây")


def _hook_status(proc_id: str) -> str:
    return run_sql(
        "SELECT status FROM core.hook_runs "
        f"WHERE process_instance_id = '{proc_id}' AND task_def = 'taskDuyetCapPhep' "
        "ORDER BY created_at DESC LIMIT 1;"
    )


def test_N03_hook_failure_and_retry():
    st = cap_phep_den_buoc_duyet("cdt.minh", {
        "ho_ten": "Hoang Thi N03",
        "cccd": "001200000033",
        "dien_thoai": "0911223344",
        "dia_chi_cong_trinh": "789 Duong N03 Phuong A",
        "thua_dat": "Thua 3 To 3",
        "so_tang": 3,
        "dien_tich_san_m2": 150.0,
        "khu_quan_ly_kien_truc": True,
    }, tag_prefix="N03_hook_failure")
    hs_id, proc_id = st["ho_so"]["id"], st["proc_id"]
    ld_token, td_token = st["tokens"]["ld.hoa"], st["tokens"]["td.binh"]
    retry_body = {"process_instance_id": proc_id, "task_def": "taskDuyetCapPhep"}

    # 1. Dừng doc-sign để giả lập sự cố ký số
    subprocess.run(["docker", "stop", "dxos-doc-sign"], check=True, capture_output=True)
    try:
        r = complete_task(ld_token, st["task"]["id"],
                          {"dongYCapPhep": True, "pheDuyet": True, "yKienPheDuyet": "Duyet cap phep"})
        assert r.status_code == 502, f"Kỳ vọng 502 khi doc-sign lỗi nhưng nhận {r.status_code}: {r.text}"

        # Hook ghi FAILED, chưa sinh giấy phép, hồ sơ chưa sang DA_CAP
        assert _hook_status(proc_id) == "FAILED", "hook_runs phải lưu FAILED"
        assert run_sql(f"SELECT count(*) FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';") == "0"
        assert run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';") != "DA_CAP"

        # 2. Thẩm định viên không được gọi retry
        r_unauth = httpx.post(f"{GATEWAY_URL}/api/v1/flow/hooks/retry",
                              headers={"Authorization": f"Bearer {td_token}"}, json=retry_body, timeout=10.0)
        assert r_unauth.status_code == 403, f"Thẩm định viên gọi retry phải nhận 403, nhận: {r_unauth.status_code}"
    finally:
        subprocess.run(["docker", "start", "dxos-doc-sign"], check=True, capture_output=True)
        _cho_doc_sign_san_sang()

    # 3. Lãnh đạo retry sau khi doc-sign chạy lại
    r_retry = httpx.post(f"{GATEWAY_URL}/api/v1/flow/hooks/retry",
                         headers={"Authorization": f"Bearer {ld_token}"}, json=retry_body, timeout=30.0)
    assert r_retry.status_code == 200, f"Retry lãnh đạo thất bại: {r_retry.status_code} {r_retry.text}"
    data = r_retry.json()
    assert data.get("status") == "success"
    assert data.get("signed_doc_id"), "Phải có signed_doc_id sau khi retry"

    # 4. Kết quả: hook COMPLETED, đúng 1 giấy phép, hồ sơ DA_CAP
    assert _hook_status(proc_id) == "COMPLETED", "hook_runs phải chuyển sang COMPLETED"
    assert run_sql(f"SELECT count(*) FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';") == "1"
    assert run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';") == "DA_CAP"

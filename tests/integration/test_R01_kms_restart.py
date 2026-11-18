# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import base64
import json
import subprocess
import time
import httpx
import pytest
from pathlib import Path
from tests.integration.conftest import GATEWAY_URL, get_token, submit_dossier


def parse_sub(tok: str) -> str:
    raw = tok.split(".")[1]
    raw += "=" * (-len(raw) % 4)
    return json.loads(base64.urlsafe_b64decode(raw))["sub"]


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()


def check_openbao_status() -> dict:
    cmd = ["docker", "compose", "exec", "-T", "openbao", "bao", "status", "-format=json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode in (0, 2):  # bao status returns 2 if sealed
        try:
            return json.loads(res.stdout)
        except Exception:
            pass
    return {"raw": res.stdout, "returncode": res.returncode}


def create_and_advance_dossier(suffix: str):
    cdt_token = get_token("cdt.minh", force_fresh=True)
    mc_token = get_token("mc.thu", force_fresh=True)
    ld_token = get_token("ld.hoa", force_fresh=True)
    td_token = get_token("td.binh", force_fresh=True)
    binh_sub = parse_sub(td_token)
    hoa_sub = parse_sub(ld_token)

    with httpx.Client(timeout=10.0) as client:
        for _ in range(6):
            resp = submit_dossier(cdt_token, {
                    "ho_ten": f"Chu Dau Tu {suffix}",
                    "cccd": f"001200{suffix[:6]}",
                    "dien_thoai": "0911223344",
                    "dia_chi_cong_trinh": f"{suffix} Duong Phuong A",
                    "thua_dat": f"Thua {suffix}",
                    "so_tang": 2,
                    "dien_tich_san_m2": 120.0,
                    "khu_quan_ly_kien_truc": True,
                }, tag_prefix="R01_kms_restart", client=client)
            if resp.status_code == 200:
                break
            time.sleep(1)
        assert resp.status_code == 200, f"Nop ho so that bai: {resp.text}"
        hs_data = resp.json()
        hs_id = hs_data["id"]
        ma_hs = hs_data["ma_ho_so"]
        proc_id = hs_data.get("process_instance_id")

    if not proc_id:
        with httpx.Client(timeout=10.0) as client:
            for _ in range(6):
                wf_resp = client.post(
                    f"{GATEWAY_URL}/api/v1/flow/processes/start",
                    headers={"Authorization": f"Bearer {cdt_token}"},
                    json={
                        "process_key": "cap-phep",
                        "business_key": ma_hs,
                        "variables": {
                            "ho_so_id": hs_id,
                            "object_id": hs_id,
                            "p_object_id": hs_id,
                            "cdt_sub": "cdt.minh",
                            "tenant": "phuong-a",
                        },
                    },
                )
                if wf_resp.status_code == 200:
                    break
                time.sleep(1)
            assert wf_resp.status_code == 200, f"Start process that bai: {wf_resp.text}"
            proc_id = wf_resp.json()["process_id"]
            assert wf_resp.status_code == 200, f"Start process that bai: {wf_resp.text}"
            proc_id = wf_resp.json()["process_id"]

    def get_task_id(user_token: str, task_def: str) -> str:
        for _ in range(12):
            with httpx.Client(timeout=5.0) as cl:
                r = cl.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": f"Bearer {user_token}"})
                if r.status_code == 200:
                    data = r.json()
                    task_list = data.get("tasks", []) if isinstance(data, dict) else data
                    for t in task_list:
                        if t.get("processInstanceId") == proc_id and t.get("taskDefinitionKey") == task_def:
                            return t["id"]
            time.sleep(1)
        raise RuntimeError(f"Task {task_def} khong tim thay cho {proc_id}")

    # 1. Tiếp nhận một cửa
    t1_id = get_task_id(mc_token, "taskKiemTraHopLe")
    with httpx.Client(timeout=5.0) as cl:
        r = cl.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t1_id}/complete",
            headers={"Authorization": f"Bearer {mc_token}"},
            json={"variables": {"hoSoHopLe": True}},
        )
        assert r.status_code == 200

    # 2. Phân công
    t2_id = get_task_id(ld_token, "taskPhanCong")
    with httpx.Client(timeout=5.0) as cl:
        r = cl.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t2_id}/complete",
            headers={"Authorization": f"Bearer {ld_token}"},
            json={"variables": {"nguoiThamDinh": binh_sub, "lanhDaoPhanCong": hoa_sub}},
        )
        assert r.status_code == 200

    # 3. Thẩm định
    t3_id = get_task_id(td_token, "taskThamDinh")
    with httpx.Client(timeout=5.0) as cl:
        r = cl.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t3_id}/complete",
            headers={"Authorization": f"Bearer {td_token}"},
            json={"variables": {"ketQuaThamDinh": "DAT", "noiDungThamDinh": "Dat tieu chuan"}},
        )
        assert r.status_code == 200

    t4_id = get_task_id(ld_token, "taskDuyetCapPhep")
    return hs_id, ma_hs, proc_id, t4_id, ld_token


def test_R01_case1_restart_unseal_and_sign():
    if not (Path(__file__).resolve().parent.parent.parent / "dx.ps1").exists():
        pytest.skip("C12 chưa có dx.ps1; kiểm tra auto-unseal sau C12")
    """Ca 1: restart openbao -> dx up (auto-unseal) -> duyệt hồ sơ -> DA_CAP và có signed_docs."""
    # 1. Khởi động lại openbao container (dẫn đến trạng thái sealed)
    subprocess.run(["docker", "compose", "restart", "openbao"], check=True)
    time.sleep(3)

    # 2. Chạy dx up (tự động phát hiện sealed và unseal trong demo mode)
    up_cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ".\\dx.ps1 up"]
    clean_env = os.environ.copy()
    clean_env.pop("KEYCLOAK_INTERNAL_URL", None)
    clean_env.pop("FLOWABLE_URL", None)
    clean_env.pop("POSTGRES_HOST", None)
    subprocess.run(up_cmd, env=clean_env, check=True)

    # Xác nhận openbao đã unsealed
    stat = check_openbao_status()
    assert stat.get("sealed") is False, f"OpenBao phai unsealed sau dx up, nhung sealed={stat.get('sealed')}"

    # 3. Duyệt hồ sơ
    hs_id, ma_hs, proc_id, t4_id, ld_token = create_and_advance_dossier("R01Case1")
    with httpx.Client(timeout=15.0) as client:
        r_duyet = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t4_id}/complete",
            headers={"Authorization": f"Bearer {ld_token}"},
            json={"variables": {"dongYCapPhep": True, "pheDuyet": True, "yKienPheDuyet": "Duyet cap phep hop le"}},
        )
        assert r_duyet.status_code == 200, f"Duyet ho so that bai: {r_duyet.text}"

    # Kiểm tra trạng thái hồ sơ DA_CAP
    hs_status = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")
    assert hs_status == "DA_CAP", f"Ky vong ho so DA_CAP, thuc te: {hs_status}"

    # Kiểm tra bảng core.signed_docs có chữ ký hợp lệ
    doc_count = int(run_sql(f"SELECT count(*) FROM core.signed_docs WHERE id IN (SELECT signed_doc_id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}') AND signature IS NOT NULL;") or "0")
    assert doc_count >= 1, f"Ky vong co signed_docs hop le cho {ma_hs}, thuc te: {doc_count}"


def test_R01_case2_sealed_fail_closed_and_retry():
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    signing_mode = os.getenv("SIGNING_MODE", "")
    if not signing_mode:
        for line in env_text.splitlines():
            if line.startswith("SIGNING_MODE="):
                signing_mode = line.split("=", 1)[1].strip()
                break
    if signing_mode.lower() == "pkcs11":
        pytest.skip("OpenBao sealed không chặn PAdES/SoftHSM; test này chỉ áp dụng SIGNING_MODE=openbao")

    """Ca 2: openbao sealed -> duyệt trả 503 KMS_SEALED, hồ sơ ở CHO_KY -> unseal -> retry -> DA_CAP."""
    # 1. Khởi động lại openbao container để đưa vào trạng thái sealed
    subprocess.run(["docker", "compose", "restart", "openbao"], check=True)
    time.sleep(3)

    # Khởi động lại doc-sign để đảm bảo kết nối mới gặp openbao sealed
    subprocess.run(["docker", "compose", "restart", "doc-sign"], check=True)
    time.sleep(3)

    # Xác nhận OpenBao thực sự đang sealed
    stat = check_openbao_status()
    assert stat.get("sealed") is True, f"OpenBao phai o trang thai sealed, nhung sealed={stat.get('sealed')}"

    # 2. Tạo và đẩy hồ sơ tới bước ký duyệt
    hs_id, ma_hs, proc_id, t4_id, ld_token = create_and_advance_dossier("R01Case2")

    # Xác nhận trạng thái trước khi duyệt là CHO_DUYET
    hs_status_before = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")
    assert hs_status_before == "CHO_DUYET", f"Ky vong ho so o CHO_DUYET truoc khi ky, thuc te: {hs_status_before}"

    # 3. Lãnh đạo cố gắng ký duyệt khi OpenBao sealed -> kỳ vọng 503 với ma_loi = KMS_SEALED
    with httpx.Client(timeout=10.0) as client:
        r_duyet = client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{t4_id}/complete",
            headers={"Authorization": f"Bearer {ld_token}"},
            json={"variables": {"dongYCapPhep": True, "pheDuyet": True, "yKienPheDuyet": "Duyet cap phep khi KMS sealed"}},
        )
        assert r_duyet.status_code == 503, f"Ky vong HTTP 503 khi OpenBao sealed nhung nhan {r_duyet.status_code}: {r_duyet.text}"
        res_data = r_duyet.json()
        detail = res_data.get("detail", {})
        ma_loi = detail.get("ma_loi") if isinstance(detail, dict) else res_data.get("ma_loi")
        assert ma_loi in ("KMS_SEALED", "KMS_UNAVAILABLE"), f"Ky vong ma_loi la KMS_SEALED hoac KMS_UNAVAILABLE, nhan: {ma_loi}"

    # Hồ sơ phải giữ nguyên ở CHO_KY (Fail-Closed, không chuyển DA_CAP)
    hs_status_fail = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")
    assert hs_status_fail == "CHO_KY", f"Ho so phai giu nguyen CHO_KY sau khi ky fail-closed, thuc te: {hs_status_fail}"

    # 4. Thực hiện unseal OpenBao và restart doc-sign
    subprocess.run(["docker", "compose", "run", "--rm", "-T", "tools", "python", "scripts/bao_ops.py", "unseal"], check=True)
    subprocess.run(["docker", "compose", "restart", "doc-sign"], check=True)
    time.sleep(4)

    # Xác nhận openbao đã unsealed
    stat_after = check_openbao_status()
    assert stat_after.get("sealed") is False, "OpenBao phai unsealed sau khi chay bao_ops unseal"

    # 5. Lãnh đạo gọi retry hook ký lại
    with httpx.Client(timeout=15.0) as client:
        r_retry = client.post(
            f"{GATEWAY_URL}/api/v1/flow/hooks/retry",
            headers={"Authorization": f"Bearer {ld_token}"},
            json={"process_instance_id": proc_id, "task_def": "taskDuyetCapPhep"},
        )
        assert r_retry.status_code == 200, f"Retry that bai sau khi unseal: {r_retry.text}"
        data = r_retry.json()
        assert data.get("status") == "success"
        assert data.get("signed_doc_id"), "Phai co signed_doc_id sau khi retry thanh cong"

    # 6. Kiểm tra CSDL: hồ sơ chuyển sang DA_CAP
    hs_status_final = run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")
    assert hs_status_final == "DA_CAP", f"Ky vong ho so chuyen sang DA_CAP sau khi retry, thuc te: {hs_status_final}"

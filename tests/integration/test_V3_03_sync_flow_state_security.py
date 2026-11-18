# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
import urllib.error
import subprocess
from tests.integration.conftest import GATEWAY_URL, get_token

ALLOWED_PUBLIC_RPCS = {
    # Danh sách các RPCs được phép công bố cho web_user
    "core_api": {
        "dong_y_du_lieu",
        "rut_dong_y_du_lieu",
        "gui_yeu_cau_dsar",
        "xin_truy_cap_khan",
        "duyet_truy_cap_khan",
        "xu_ly_dsar",
        "ds_truy_cap_khan",
    },
    "app_cap_phep": {
        "nop_ho_so",
        "bo_sung_ho_so",
        "dinh_kem_tep",
        "mo_ho_so",
        "xin_truy_cap_khan",
        "duyet_truy_cap_khan",
        "dong_y_du_lieu",
        "rut_dong_y_du_lieu",
        "gui_yeu_cau_dsar",
        "xu_ly_dsar",
        "lay_nhat_ky_ho_so",
        "lay_nhat_ky_phuong",
        "ds_can_bo",
        "ds_truy_cap_khan",
        "thong_tin_giay_phep",
        "lap_phieu_kiem_tra",
        "lay_thong_bao",
        "danh_dau_da_doc",
        "kiem_tra_giay_to_nop",
        "danh_gia_tep",
    },
}


def test_V3_03_sync_flow_state_cannot_be_called_by_web_user():
    # 1. cdt.minh gọi sync_flow_state qua PostgREST phải bị từ chối
    token_minh = get_token("cdt.minh")
    url = f"{GATEWAY_URL}/api/v1/rest/rpc/sync_flow_state"
    data = json.dumps({
        "p_process_id": "test-proc-id",
        "p_task_def": "taskDuyetCapPhep",
        "p_variables": {},
    }).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token_minh}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    is_rejected = False
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status_code = resp.status
    except urllib.error.HTTPError as e:
        status_code = e.code
        is_rejected = True

    assert is_rejected or status_code in (401, 403, 404), f"cdt.minh vẫn gọi được sync_flow_state! HTTP {status_code}"


def test_V3_03_pg_proc_exposed_schemas_allowlist():
    # 2. Kiểm tra pg_proc: Không hàm nội bộ nào cấp quyền EXECUTE cho web_user ngoài allowlist
    query = """
    SELECT n.nspname, p.proname
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname IN ('core_api', 'app_cap_phep')
      AND has_function_privilege('web_user', p.oid, 'EXECUTE')
      AND p.prokind = 'f';
    """
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", query]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = [line.strip() for line in proc.stdout.strip().splitlines() if line.strip()]

    disallowed = []
    for line in lines:
        schema, func = line.split("|")
        allowed_in_schema = ALLOWED_PUBLIC_RPCS.get(schema, set())
        if func not in allowed_in_schema:
            disallowed.append(f"{schema}.{func}")

    assert not disallowed, f"Các hàm sau cấp EXECUTE cho web_user mà không nằm trong allowlist bảo mật: {disallowed}"

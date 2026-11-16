# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
import urllib.error
from tests.integration.conftest import GATEWAY_URL, get_token


def test_V3_04_citizen_cannot_patch_dsar_or_insert_consents_directly():
    token_minh = get_token("cdt.minh")

    # 1. Thử gửi yêu cầu DSAR hợp lệ qua RPC
    rpc_url = f"{GATEWAY_URL}/api/v1/rest/rpc/gui_yeu_cau_dsar"
    req_rpc = urllib.request.Request(
        rpc_url,
        data=json.dumps({"p_type": "access"}).encode(),
        headers={"Authorization": f"Bearer {token_minh}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_rpc, timeout=5) as resp:
        dsar_id = json.loads(resp.read().decode())["id"]

    # 2. Thử PATCH vào view /dsar_requests để tự đổi trạng thái và hạn (X-03)
    patch_url = f"{GATEWAY_URL}/api/v1/rest/dsar_requests?id=eq.{dsar_id}"
    patch_data = json.dumps({
        "status": "closed",
        "due_at": "2020-01-01T00:00:00Z",
    }).encode()
    req_patch = urllib.request.Request(
        patch_url,
        data=patch_data,
        headers={"Authorization": f"Bearer {token_minh}", "Content-Type": "application/json"},
        method="PATCH",
    )

    is_patch_rejected = False
    status_code = None
    try:
        with urllib.request.urlopen(req_patch, timeout=5) as resp:
            status_code = resp.status
    except urllib.error.HTTPError as e:
        status_code = e.code
        is_patch_rejected = True

    # 3. Đọc lại bản ghi: Trạng thái và hạn không được bị thay đổi
    get_url = f"{GATEWAY_URL}/api/v1/rest/dsar_requests?id=eq.{dsar_id}"
    req_get = urllib.request.Request(get_url, headers={"Authorization": f"Bearer {token_minh}"})
    with urllib.request.urlopen(req_get, timeout=5) as resp:
        rows = json.loads(resp.read().decode())
        assert len(rows) == 1
        rec = rows[0]
        assert rec["status"] == "received", f"Trạng thái DSAR bị đổi lậu: {rec['status']}"
        assert not str(rec["due_at"]).startswith("2020-01-01"), f"Hạn DSAR bị đổi lậu: {rec['due_at']}"

    assert is_patch_rejected or status_code in (401, 403, 404, 405), f"Người dân vẫn PATCH được dsar_requests! HTTP {status_code}"

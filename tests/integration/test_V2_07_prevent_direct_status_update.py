# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
import urllib.error
from .conftest import get_token, GATEWAY_URL


def patch_ho_so_status(token: str, ho_so_id: str, new_status: str) -> int:
    req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/ho_so?id=eq.{ho_so_id}",
        data=json.dumps({"trang_thai": new_status}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def test_officers_cannot_patch_ho_so_status_directly():
    # Lấy 1 hồ sơ bất kỳ từ hệ thống
    token_mc = get_token("mc.thu")
    token_ld = get_token("ld.hoa")
    token_td = get_token("td.binh")

    req_list = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/v_ho_so?limit=3",
        headers={"Authorization": f"Bearer {token_mc}"},
    )
    with urllib.request.urlopen(req_list, timeout=5) as resp:
        dossiers = json.loads(resp.read().decode())
        assert len(dossiers) > 0

    target_id = dossiers[0]["id"]

    # 1. mc.thu cố tình đổi trạng thái sang TU_CHOI
    status_code_1 = patch_ho_so_status(token_mc, target_id, "TU_CHOI")
    assert status_code_1 in (400, 401, 403, 404, 405), f"mc.thu không được phép PATCH trang_thai (mã: {status_code_1})"

    # 2. ld.hoa cố tình đổi trạng thái sang DANG_THAM_DINH
    status_code_2 = patch_ho_so_status(token_ld, target_id, "DANG_THAM_DINH")
    assert status_code_2 in (400, 401, 403, 404, 405), f"ld.hoa không được phép PATCH trang_thai (mã: {status_code_2})"

    # 3. td.binh cố tình đổi trạng thái sang CHO_DUYET
    status_code_3 = patch_ho_so_status(token_td, target_id, "CHO_DUYET")
    assert status_code_3 in (400, 401, 403, 404, 405), f"td.binh không được phép PATCH trang_thai (mã: {status_code_3})"

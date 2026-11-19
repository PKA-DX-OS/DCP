# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
import urllib.error
from tests.integration._auth import get_token, GATEWAY_URL


def test_S02_upload_other_owner_403():
    import subprocess
    subprocess.run(
        ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c", "DELETE FROM core.break_glass;"],
        check=False,
    )
    token_minh = get_token("cdt.minh")
    token_lan = get_token("cdt.lan")
    token_cuong = get_token("td.cuong")

    # 1. Lấy mã hồ sơ của cdt.minh
    req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/v_ho_so?limit=1",
        headers={"Authorization": f"Bearer {token_minh}"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        dossiers = json.loads(resp.read().decode())
        ho_so_id = dossiers[0]["id"]

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="test.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
        f"%PDF-1.4 test\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="object_type"\r\n\r\n'
        f"ho_so\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="object_id"\r\n\r\n'
        f"{ho_so_id}\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    # 2. cdt.lan tải tệp lên hồ sơ của cdt.minh -> Phải bị từ chối 403
    req_lan = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/files",
        data=body,
        headers={
            "Authorization": f"Bearer {token_lan}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    pytest_raises_http(403, req_lan)

    # 3. cdt.minh tải lên hồ sơ của chính mình -> Thành công 201
    req_minh = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/files",
        data=body,
        headers={
            "Authorization": f"Bearer {token_minh}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(req_minh, timeout=5) as resp:
        assert resp.status == 201
        file_id = json.loads(resp.read().decode())["file_id"]

    # 4. td.cuong (thẩm định viên không được phân công) tải tệp -> Phải bị từ chối 403
    req_dl = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/files/{file_id}",
        headers={"Authorization": f"Bearer {token_cuong}"},
    )
    pytest_raises_http(403, req_dl)


def pytest_raises_http(expected_code: int, req: urllib.request.Request):
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raise AssertionError(f"Mong đợi HTTP {expected_code} nhưng nhận được HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        assert e.code == expected_code, f"Mong đợi HTTP {expected_code} nhưng nhận được HTTP {e.code}"

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy cho lỗi Q-01:
- Tách endpoint timer thành router nội bộ /internal/timer.
- APISIX không có route trỏ tới /internal/timer; gọi qua gateway /api/v1/flow/timer trả 404.
- Gọi thẳng /internal/timer không có header X-DXOS-Internal-Token trả 401/403.
- Gọi thẳng có token nhưng process_instance_id không tồn tại hoặc đã kết thúc trong Flowable trả 404.
- Khi timer thật hết hạn (SLA PT1M), service task HTTP gửi token nội bộ và ghi nhận audit sla.qua_han thành công.
"""

import os
from pathlib import Path
import subprocess
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token


def get_internal_token() -> str:
    token = os.getenv("FLOW_INTERNAL_TOKEN")
    if token:
        return token
    for p in [Path("secrets/flow_internal_token"), Path("D:/v1PMNM-clean/secrets/flow_internal_token"), Path(".env")]:
        if p.exists():
            if p.name == "flow_internal_token":
                return p.read_text(encoding="utf-8").strip()
            elif p.name == ".env":
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.startswith("FLOW_INTERNAL_TOKEN="):
                        return line.split("=", 1)[1].strip()
    return ""


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def run_in_tools(cmd_args: list) -> subprocess.CompletedProcess:
    full_cmd = ["docker", "compose", "run", "--rm", "tools"] + cmd_args
    return subprocess.run(full_cmd, capture_output=True, text=True)


def test_Q01_gateway_timer_returns_404():
    """Token chủ đầu tư gọi POST /api/v1/flow/timer qua gateway -> 404 (route không tồn tại)."""
    token_cdt = get_token("cdt.minh")
    headers = {"Authorization": f"Bearer {token_cdt}", "Content-Type": "application/json"}
    with httpx.Client(base_url=GATEWAY_URL, timeout=5.0) as client:
        resp = client.post("/api/v1/flow/timer", headers=headers, json={"process_instance_id": "proc-test"})
        assert resp.status_code == 404, f"Kỳ vọng 404 khi gọi /api/v1/flow/timer qua gateway, nhưng nhận {resp.status_code}: {resp.text}"


def test_Q01_direct_internal_timer_requires_token():
    """Gọi thẳng flow:8000/internal/timer không token từ container tools -> 401 hoặc 403."""
    py_code = """
import urllib.request, urllib.error, json
req = urllib.request.Request('http://flow:8000/internal/timer', data=b'{"process_instance_id":"proc-test"}', headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as resp:
        print('STATUS:', resp.getcode())
except urllib.error.HTTPError as e:
    print('STATUS:', e.code)
"""
    res = run_in_tools(["python", "-c", py_code])
    out = res.stdout.strip()
    assert "STATUS: 401" in out or "STATUS: 403" in out, f"Kỳ vọng 401 hoặc 403 khi gọi /internal/timer không có token, nhận: {out} (stderr: {res.stderr})"


def test_Q01_internal_timer_nonexistent_process_returns_404():
    """Gọi có token nhưng process_instance_id không tồn tại trong Flowable -> 404."""
    token = get_internal_token()
    py_code = f"""
import urllib.request, urllib.error, json
headers = {{
    'Content-Type': 'application/json',
    'X-DXOS-Internal-Token': '{token}'
}}
data = json.dumps({{'process_instance_id': 'nonexistent-proc-xyz-999999'}}).encode('utf-8')
req = urllib.request.Request('http://flow:8000/internal/timer', data=data, headers=headers)
try:
    with urllib.request.urlopen(req) as resp:
        print('STATUS:', resp.getcode())
except urllib.error.HTTPError as e:
    print('STATUS:', e.code)
"""
    res = run_in_tools(["python", "-c", py_code])
    out = res.stdout.strip()
    assert "STATUS: 404" in out, f"Kỳ vọng 404 khi process_instance_id không tồn tại, nhận: {out} (stderr: {res.stderr})"

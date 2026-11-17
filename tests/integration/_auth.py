# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Helper xác thực dùng chung cho test tích hợp.

Tách khỏi `conftest.py` (C14) để các test A06/A07 không phụ thuộc file
chưa có. Khi C14 merge, conftest có thể dùng lại hoặc thay thế module này.
"""

import base64
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8080")
DEMO_ACCOUNTS_FILE = ROOT / "secrets" / "demo-accounts.txt"


def _load_accounts() -> dict:
    accounts = {}
    if DEMO_ACCOUNTS_FILE.exists():
        for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(":")
                accounts[parts[0]] = parts[1]
    return accounts


_ACCOUNTS = _load_accounts()
_TOKEN_CACHE = {}


def get_token(username: str, force_fresh: bool = False) -> str:
    if not force_fresh and username in _TOKEN_CACHE:
        token = _TOKEN_CACHE[username]
        try:
            raw = token.split(".")[1]
            raw += "=" * (-len(raw) % 4)
            payload = json.loads(base64.urlsafe_b64decode(raw))
            if payload.get("exp", 0) > time.time() + 120:
                return token
        except Exception:
            pass

    password = _ACCOUNTS.get(username, "Demo@123456")
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": "dx-test",
        "username": username,
        "password": password,
    }).encode()

    token_url = f"{GATEWAY_URL}/auth/realms/dxos/protocol/openid-connect/token"
    req = urllib.request.Request(token_url, data=data)
    with urllib.request.urlopen(req, timeout=5) as resp:
        token = json.loads(resp.read().decode())["access_token"]
        _TOKEN_CACHE[username] = token
        return token

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

import httpx

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


def _env(key: str) -> str | None:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return None


def get_keycloak_admin_client() -> tuple[httpx.Client, str]:
    """Trả client trỏ Keycloak và access token realm master (dùng cho test quản trị)."""
    pw = _env("KEYCLOAK_ADMIN_PASSWORD")
    assert pw, "Thiếu KEYCLOAK_ADMIN_PASSWORD trong .env"
    user = _env("KEYCLOAK_ADMIN") or "admin"
    last = None
    for base in ("http://127.0.0.1:8081/auth", f"{GATEWAY_URL}/auth"):
        client = httpx.Client(base_url=base, timeout=10.0)
        try:
            r = client.post(
                "/realms/master/protocol/openid-connect/token",
                data={"client_id": "admin-cli", "username": user, "password": pw, "grant_type": "password"},
            )
            if r.status_code == 200:
                return client, r.json()["access_token"]
            last = f"{base}: HTTP {r.status_code}"
        except httpx.HTTPError as e:
            last = f"{base}: {e}"
        client.close()
    raise AssertionError(f"Không lấy được token quản trị Keycloak ({last})")


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

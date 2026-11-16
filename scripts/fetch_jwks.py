#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kịch bản đồng bộ JWKS từ Keycloak sang PostgREST (F-04):
- Tải danh sách khóa công khai RS256 từ endpoint Keycloak.
- Ghi vào `core/postgrest/jwks.json` (tệp được mount vào container PostgREST).
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Ensure UTF-8 output on all platforms
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception) as _e:
        _ = _e

import httpx

ROOT = Path(__file__).resolve().parent.parent
JWKS_FILE = ROOT / "core" / "postgrest" / "jwks.json"

CANDIDATE_URLS = [
    "http://keycloak:8080/auth/realms/dxos/protocol/openid-connect/certs",
    "http://apisix:8080/auth/realms/dxos/protocol/openid-connect/certs",
    f"{os.getenv('KEYCLOAK_URL', 'http://localhost:8080/auth')}/realms/dxos/protocol/openid-connect/certs",
    "http://localhost:8081/auth/realms/dxos/protocol/openid-connect/certs",
    "http://127.0.0.1:8081/auth/realms/dxos/protocol/openid-connect/certs",
]


def main():
    JWKS_FILE.parent.mkdir(parents=True, exist_ok=True)

    jwks_data = None
    target_url = None

    print("=== [DX-OS JWKS] Đang tìm kiếm và nạp JWKS từ Keycloak... ===")

    for _attempt in range(15):
        for url in CANDIDATE_URLS:
            try:
                with httpx.Client(timeout=3.0) as client:
                    resp = client.get(url)
                    if resp.status_code == 200 and "keys" in resp.json():
                        jwks_data = resp.json()
                        target_url = url
                        break
            except (httpx.RequestError, httpx.HTTPStatusError):
                continue
        if jwks_data:
            break
        time.sleep(2)

    if not jwks_data or not jwks_data.get("keys") or len(jwks_data.get("keys", [])) == 0:
        print("[FAIL] Không thể lấy JWKS từ Keycloak hoặc danh sách keys rỗng!", file=sys.stderr)
        sys.exit(1)

    print(f"  - Kết nối thành công tới: {target_url}")
    JWKS_FILE.write_text(json.dumps(jwks_data, indent=2), encoding="utf-8")
    print(f"[OK] Đã lưu {len(jwks_data.get('keys', []))} khóa công khai vào {JWKS_FILE}")

    # PostgREST được restart bởi dx up trên host; trong tools container không có docker CLI.
    if shutil.which("docker"):
        try:
            subprocess.run(["docker", "compose", "restart", "postgrest"], capture_output=True)
            print("[OK] Da khoi dong lai PostgREST de ap dung JWKS moi.")
        except Exception as e:
            print(f"[INFO] Khong the restart PostgREST tu tools container: {e}")


if __name__ == "__main__":
    main()


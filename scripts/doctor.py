#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
DX-OS Doctor Diagnostic Script:
- Lấy token thật từ Keycloak cho tài khoản demo (cdt.minh).
- Gọi GET /api/v1/rest/v_ho_so?limit=1 qua Gateway APISIX.
- Nếu khác 200: thoát mã ≠ 0.
"""

import os
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
DEMO_ACCOUNTS_FILE = ROOT / "secrets" / "demo-accounts.txt"


def get_gateway_url() -> str:
    url = os.getenv("GATEWAY_INTERNAL_URL")
    if url:
        return url
    for host in ["http://apisix:8080", "http://localhost:8080", "http://127.0.0.1:8080"]:
        try:
            with httpx.Client(timeout=1.0) as client:
                r = client.get(f"{host}/api/v1/health")
                if r.status_code == 200:
                    return host
        except Exception:
            continue
    return "http://apisix:8080"


def get_keycloak_url() -> str:
    url = os.getenv("KEYCLOAK_INTERNAL_URL")
    if url:
        return url
    for host in [
        "http://keycloak:8080/auth",
        "http://apisix:8080/auth",
        "http://localhost:8080/auth",
        "http://localhost:8081/auth",
    ]:
        try:
            with httpx.Client(timeout=1.0) as client:
                r = client.get(f"{host}/realms/dxos/.well-known/openid-configuration")
                if r.status_code == 200:
                    return host
        except Exception:
            continue
    return "http://localhost:8080/auth"


def get_demo_account() -> tuple[str, str]:
    if DEMO_ACCOUNTS_FILE.exists():
        for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Format 1: cdt.minh:password:...
            if ":" in line:
                parts = line.split(":")
                if parts[0] == "cdt.minh":
                    return parts[0], parts[1]
            # Format 2: * Tài khoản: cdt.minh | Mật khẩu: ...
            if "cdt.minh" in line and "|" in line:
                parts = line.split("|")
                pw = ""
                for p in parts:
                    if "Mật khẩu:" in p:
                        pw = p.split("Mật khẩu:")[1].strip()
                if pw:
                    return "cdt.minh", pw
    return "cdt.minh", "Demo@123456"


def main():
    print("=== [DX-OS DOCTOR] Kiểm tra trạng thái hoạt động hệ thống & xác thực PostgREST ===")
    
    # 0. In phiên bản hình ảnh container đang chạy (V2-03)
    print("--> 1. Phiên bản các hình ảnh container đang hoạt động:")
    import subprocess
    try:
        res = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Image}}\t{{.Status}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                print(f"      {line}")
        else:
            print("      (Không thể lấy danh sách container qua docker ps)")
    except Exception as e:
        print(f"      (docker ps không khả dụng: {e})")

    gateway = get_gateway_url()
    keycloak = get_keycloak_url()
    username, password = get_demo_account()

    print("--> 2. Kiểm tra kết nối dịch vụ:")
    print(f"  - Gateway API: {gateway}")
    print(f"  - Keycloak SSO: {keycloak}")
    print(f"  - Thử nghiệm tài khoản: {username}")

    token_url = f"{keycloak}/realms/dxos/protocol/openid-connect/token"
    token = None

    for _attempt in range(5):
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    token_url,
                    data={
                        "client_id": "dx-test",
                        "grant_type": "password",
                        "username": username,
                        "password": password,
                    },
                )
                if resp.status_code == 200:
                    token = resp.json().get("access_token")
                    break
                else:
                    print(f"  [WAIT] Lấy token {username}: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [WAIT] Kết nối tới Keycloak: {e}")
        time.sleep(2)

    if not token:
        print("  [INFO] Thử đồng bộ tài khoản mẫu qua seed.py...")
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "apps" / "cap-phep" / "seed" / "seed.py")], check=False)
        username, password = get_demo_account()
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    token_url,
                    data={
                        "client_id": "dx-test",
                        "grant_type": "password",
                        "username": username,
                        "password": password,
                    },
                )
                if resp.status_code == 200:
                    token = resp.json().get("access_token")
        except Exception as e:
            print(f"  [WAIT] Lỗi kết nối Keycloak: {e}")

    if not token:
        print("[FAIL] Không thể lấy access token từ Keycloak! Kiểm tra dịch vụ Keycloak.", file=sys.stderr)
        sys.exit(1)

    print("  [OK] Đã lấy access token thật thành công từ Keycloak.")

    # Gọi GET /api/v1/rest/v_ho_so?limit=1
    rest_url = f"{gateway}/api/v1/rest/v_ho_so?limit=1"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(rest_url, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 200:
                print(f"[PASS] [DX DOCTOR OK] PostgREST trả về HTTP 200. Dữ liệu nhận được: {len(resp.json())} bản ghi.")
                sys.exit(0)
            else:
                print(f"[FAIL] [DX DOCTOR LỖI] PostgREST trả về HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
                sys.exit(1)
    except Exception as e:
        print(f"[FAIL] [DX DOCTOR LỖI] Lỗi kết nối tới Gateway /api/v1/rest: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


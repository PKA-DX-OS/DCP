#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kịch bản quản trị OpenBao KMS (dx bao-init, dx bao-unseal):
- Khởi tạo Shamir Secret Sharing (5 mảnh khóa, ngưỡng 3 mảnh).
- Mở khóa Unseal thật với 3 mảnh khóa.
- Bật Transit Engine, sinh khóa ký số Ed25519 cho doc-sign.
- Cấp phát Policy và Service Token chuyên biệt cho dịch vụ doc-sign.
"""

import argparse
import json
import os
import sys
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
SECRETS_FILE = ROOT / "secrets" / "bao-unseal.json"
DOC_SIGN_TOKEN_FILE = ROOT / "secrets" / "bao-doc-sign.token"
ENV_FILE = ROOT / ".env"

OPENBAO_ADDR = os.getenv("OPENBAO_ADDR", "http://openbao:8200")
# Khi chạy từ host, thử kết nối localhost nếu openbao không phân giải được
if "openbao" in OPENBAO_ADDR:
    try:
        import socket
        socket.gethostbyname("openbao")
    except Exception:
        OPENBAO_ADDR = "http://localhost:8200"


def check_status(client: httpx.Client) -> dict:
    try:
        resp = client.get(f"{OPENBAO_ADDR}/v1/sys/seal-status")
        return resp.json()
    except Exception as e:
        print(f"[ERROR] Không thể kết nối tới OpenBao tại {OPENBAO_ADDR}: {e}")
        sys.exit(1)


def bao_unseal(client: httpx.Client, keys: list):
    print("--> Đang thực hiện mở khóa (Unseal) OpenBao KMS...")
    for idx, k in enumerate(keys[:3], 1):
        resp = client.put(f"{OPENBAO_ADDR}/v1/sys/unseal", json={"key": k})
        data = resp.json()
        print(f"  - Mảnh khóa #{idx}: Tiến độ unseal = {data.get('progress', 0)}/{data.get('t', 3)}, Sealed = {data.get('sealed')}")
        if not data.get("sealed"):
            print("[OK] OpenBao KMS đã được MỞ KHÓA THÀNH CÔNG (Unsealed)!")
            return True
    return False


def cmd_init():
    print("=== [DX-OS OPENBAO] Khởi tạo hệ thống OpenBao KMS (5/3) ===")
    with httpx.Client(timeout=10.0) as client:
        status = check_status(client)
        if status.get("initialized"):
            print("[INFO] OpenBao đã được khởi tạo trước đó.")
            if status.get("sealed"):
                print("[INFO] OpenBao đang ở trạng thái Sealed. Vui lòng chạy `dx bao-unseal`.")
            else:
                print("[OK] OpenBao đã unsealed và sẵn sàng hoạt động.")
            return

        print("--> 1. Khởi tạo 5 mảnh khóa Shamir và ngưỡng 3 mảnh...")
        init_payload = {"secret_shares": 5, "secret_threshold": 3}
        resp = client.post(f"{OPENBAO_ADDR}/v1/sys/init", json=init_payload)
        if resp.status_code != 200:
            print(f"[FAIL] Lỗi khởi tạo OpenBao: {resp.text}")
            sys.exit(1)

        init_data = resp.json()
        unseal_keys = init_data["keys"]
        root_token = init_data["root_token"]

        # Lưu khóa vào secrets/bao-unseal.json
        SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SECRETS_FILE.write_text(
            json.dumps(
                {
                    "warning": "TỆP CHỨA KHÓA TỐI MẬT CỦA HỆ THỐNG DX-OS. KHÔNG BAO GIỜ COMMIT VÀO GIT!",
                    "keys": unseal_keys,
                    "root_token": root_token,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  [OK] Đã lưu 5 mảnh khóa unseal và root token vào {SECRETS_FILE}")

        # 2. Mở khóa Unseal bằng 3 mảnh đầu tiên
        bao_unseal(client, unseal_keys)

        # 3. Kích hoạt Transit secrets engine và tạo khóa doc-sign
        print("--> 2. Kích hoạt Transit Engine và tạo khóa ký Ed25519 cho doc-sign...")
        headers = {"X-Vault-Token": root_token}

        # Bật transit engine nếu chưa bật
        resp_mounts = client.get(f"{OPENBAO_ADDR}/v1/sys/mounts", headers=headers)
        if "transit/" not in resp_mounts.json():
            client.post(f"{OPENBAO_ADDR}/v1/sys/mounts/transit", headers=headers, json={"type": "transit"})
            print("  - Đã bật engine transit/")

        # Tạo khóa Ed25519
        client.post(
            f"{OPENBAO_ADDR}/v1/transit/keys/doc-sign",
            headers=headers,
            json={"type": "ed25519"},
        )
        print("  - Đã khởi tạo cặp khóa Ed25519 `transit/keys/doc-sign`")

        # 4. Tạo Policy chuyên biệt cho doc-sign (Least Privilege)
        policy_hcl = """
path "transit/sign/doc-sign" {
  capabilities = ["update"]
}
path "transit/verify/doc-sign" {
  capabilities = ["update"]
}
path "transit/keys/doc-sign" {
  capabilities = ["read"]
}
"""
        client.put(
            f"{OPENBAO_ADDR}/v1/sys/policy/doc-sign",
            headers=headers,
            json={"policy": policy_hcl},
        )
        print("  - Đã thiết lập policy `doc-sign` với quyền tối thiểu.")

        # 5. Sinh Service Token riêng cho doc-sign
        token_resp = client.post(
            f"{OPENBAO_ADDR}/v1/auth/token/create",
            headers=headers,
            json={"policies": ["doc-sign"], "ttl": "720h", "renewable": True},
        )
        doc_sign_token = token_resp.json()["auth"]["client_token"]
        DOC_SIGN_TOKEN_FILE.write_text(doc_sign_token, encoding="utf-8")
        print(f"  - Đã tạo Service Token riêng cho doc-sign và lưu vào {DOC_SIGN_TOKEN_FILE}")

        # 6. Cập nhật OPENBAO_TOKEN trong .env
        if ENV_FILE.exists():
            env_text = ENV_FILE.read_text(encoding="utf-8")
            lines = []
            replaced = False
            for line in env_text.splitlines():
                if line.startswith("OPENBAO_TOKEN="):
                    lines.append(f"OPENBAO_TOKEN={doc_sign_token}")
                    replaced = True
                else:
                    lines.append(line)
            if not replaced:
                lines.append(f"OPENBAO_TOKEN={doc_sign_token}")
            ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print("  - Đã cập nhật OPENBAO_TOKEN trong .env thành Service Token của doc-sign.")

        print("=== [DX-OS OPENBAO] Khởi tạo hoàn tất thành công! ===")


def cmd_unseal():
    print("=== [DX-OS OPENBAO] Mở khóa Unseal OpenBao KMS ===")
    if not SECRETS_FILE.exists():
        print(f"[ERROR] Không tìm thấy tệp {SECRETS_FILE}! Hệ thống chưa được chạy `dx bao-init`.")
        sys.exit(1)

    with open(SECRETS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    keys = data.get("keys", [])

    if len(keys) < 3:
        print("[ERROR] Không đủ 3 mảnh khóa trong tệp bí mật!")
        sys.exit(1)

    with httpx.Client(timeout=10.0) as client:
        status = check_status(client)
        if not status.get("sealed"):
            print("[OK] OpenBao KMS đã ở trạng thái Unsealed sẵn sàng.")
            return

        success = bao_unseal(client, keys)
        if not success:
            print("[FAIL] Mở khóa OpenBao thất bại.")
            sys.exit(1)


def cmd_status():
    with httpx.Client(timeout=10.0) as client:
        status = check_status(client)
        is_init = status.get("initialized", False)
        is_sealed = status.get("sealed", True)
        if not is_init:
            print("[OPENBAO STATUS] Chưa khởi tạo (Not initialized). Chạy `.\\dx.ps1 bao-init` để khởi tạo.")
            return 0
        elif is_sealed:
            print("[OPENBAO STATUS] Đang bị khóa (Sealed). Chạy `.\\dx.ps1 bao-unseal` để mở khóa.")
            return 0
        else:
            print("[OPENBAO STATUS] Đã mở khóa (Unsealed) và sẵn sàng hoạt động.")
            return 0


def main():
    parser = argparse.ArgumentParser(description="DX-OS OpenBao Manager")
    parser.add_argument("action", choices=["init", "unseal", "status"], help="Hành động (init, unseal, status)")
    args = parser.parse_args()

    if args.action == "init":
        cmd_init()
    elif args.action == "unseal":
        cmd_unseal()
    elif args.action == "status":
        sys.exit(cmd_status())


if __name__ == "__main__":
    main()


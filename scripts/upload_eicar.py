# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
import base64
import sys
import httpx

def main():
    # EICAR standard test string decoded at runtime to prevent static antivirus scanner triggers
    eicar_bytes = base64.b64decode(b"WDVPIVAlQEFQWzRQWlhkNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=")
    files = {"file": ("eicar.txt", eicar_bytes, "text/plain")}
    data = {
        "object_type": "ho_so",
        "object_id": "00000000-0000-0000-0000-000000000000"
    }

    print("--> Đang gửi tệp kiểm thử mã độc EICAR tới dịch vụ quét ClamAV qua APISIX...")
    try:
        r = httpx.post("http://apisix:8080/api/v1/files", files=files, data=data, timeout=10.0)
        print(f"Mã phản hồi HTTP: {r.status_code}")
        print(f"Nội dung phản hồi: {r.text}")
    except Exception as e:
        print(f"Lỗi kết nối tới dịch vụ: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

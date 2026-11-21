#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Sinh khóa HMAC cho dữ liệu chủ (D-MDM-01) nếu chưa có: secrets/mdm-hmac.key.

CCCD chỉ lưu dạng HMAC-SHA256 với khóa này; khóa nằm ngoài DB và ngoài Git. Đã có khóa thì giữ
nguyên (đổi khóa làm mọi cccd_hmac cũ không còn khớp). `dx up` gọi script này trước khi chạy dịch vụ.

Chạy: python scripts/dh_khoa.py [--secrets thư_mục]
"""

import argparse
import os
import secrets
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
TEN_TEP = "mdm-hmac.key"


def dam_bao_khoa(thu_muc: Path) -> bool:
    """Tạo khóa 256 bit (hex) nếu chưa có; trả True nếu vừa tạo."""
    tep = thu_muc / TEN_TEP
    if tep.exists() and len(tep.read_text(encoding="utf-8").strip()) >= 32:
        return False
    thu_muc.mkdir(parents=True, exist_ok=True)
    tep.write_text(secrets.token_hex(32) + "\n", encoding="utf-8")
    try:
        if os.name != "nt":
            os.chmod(tep, 0o644)
    except OSError:
        pass
    return True


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Sinh khóa HMAC dữ liệu chủ nếu chưa có")
    p.add_argument("--secrets", type=Path, default=ROOT / "secrets")
    a = p.parse_args(argv)
    if dam_bao_khoa(a.secrets):
        print(f"  - Đã sinh khóa HMAC dữ liệu chủ vào secrets/{TEN_TEP}")
    else:
        print(f"  - Giữ khóa HMAC dữ liệu chủ hiện có (secrets/{TEN_TEP})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

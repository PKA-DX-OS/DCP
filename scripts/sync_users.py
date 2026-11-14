#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kịch bản đồng bộ người dùng từ Keycloak sang bảng core.users_directory (P-05, N-06):
- Đọc danh sách người dùng trong realm dxos từ Keycloak admin API.
- Lấy thông tin tenant từ attributes và roles từ role-mappings.
- Cập nhật / chèn vào bảng core.users_directory.
- Đặt active = false khi user bị vô hiệu hóa hoặc xóa khỏi Keycloak.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services"))

from dxos_core.user_sync import sync_keycloak_users


async def sync():
    print("--> Bắt đầu đồng bộ danh mục người dùng từ Keycloak sang core.users_directory (P-05)...")
    try:
        summary = await sync_keycloak_users()
        print(
            f"  [PASS] Đã đồng bộ {summary['synced_count']}/{summary['total_keycloak_users']} người dùng "
            f"(đã vô hiệu hóa {summary['deactivated_count']} tài khoản không còn tồn tại)."
        )
    except Exception as e:
        print(f"  [ERROR] Đồng bộ người dùng thất bại: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    asyncio.run(sync())


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kịch bản xác minh tính toàn vẹn của chuỗi băm kiểm toán (make verify):
- Kiểm tra tính liên tục của prev_hash.
- Tính toán lại mã băm SHA-256 từng dòng dữ liệu và so khớp.
- Phát hiện và chỉ đích danh ID của bản ghi bị chỉnh sửa trái phép.
"""

import asyncio
import sys
from pathlib import Path

# Ensure UTF-8 output on all platforms
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception) as _e:
        _ = _e

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services"))

from dxos_core.audit import verify_audit_chain
from dxos_core.db import get_db_pool


async def main():
    print("==========================================================")
    print(" [DX-OS AUDIT VERIFY] BẮT ĐẦU XÁC MINH CHUỖI BĂM KIỂM TOÁN ")
    print("==========================================================")

    try:
        pool = await get_db_pool()
    except Exception as e:
        print(f"[ERROR] Cơ sở dữ liệu PostgreSQL không sẵn sàng: {e}", file=sys.stderr)
        sys.exit(1)

    if not pool:
        print("[ERROR] Cơ sở dữ liệu PostgreSQL không sẵn sàng! Không thể kết nối để xác minh chuỗi kiểm toán.", file=sys.stderr)
        sys.exit(1)

    tenants = []
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT DISTINCT tenant FROM core.audit_log")
        tenants = [r["tenant"] for r in rows]

    if not tenants:
        print("[INFO] Chưa có bản ghi kiểm toán nào trong hệ thống.")
        return

    all_valid = True
    for t in tenants:
        print(f"--> Đang kiểm tra chuỗi kiểm toán của thuê ước: [{t}]...")
        result = await verify_audit_chain(t)
        if result["valid"]:
            print(f"  [PASS] Hợp lệ! Đã xác minh {result['count']} bản ghi. Head Hash: {result.get('head_hash', '')[:16]}...")
        else:
            all_valid = False
            print(f"  [FAIL] PHÁT HIỆN GIAN LẬN DỮ LIỆU TẠI BẢN GHI AUDIT ID: {result.get('tampered_id')}!")
            print(f"         Lý do: {result.get('reason')}")

    print("==========================================================")
    if all_valid:
        print(" [SUCCESS] TOÀN BỘ CHUỖI KIỂM TOÁN HỢP LỆ VÀ NGUYÊN VẸN.")
        print("==========================================================")
        sys.exit(0)
    else:
        print(" [ERROR] PHÁT HIỆN DỮ LIỆU BỊ CAN THIỆP TRÁI PHÉP!")
        print("==========================================================")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

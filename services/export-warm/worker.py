# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import asyncio
import importlib
import logging

logger = logging.getLogger("export_warm_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    logger.info("Khởi động worker export-warm theo chu kỳ (mỗi 5 phút)...")
    await asyncio.sleep(10)
    export_mod = importlib.import_module("export-warm.main")
    while True:
        try:
            await export_mod.run_export_warm()
        except Exception as e:
            logger.error("Lỗi trong chu kỳ export-warm: %s", e)
        await asyncio.sleep(300)


if __name__ == "__main__":
    asyncio.run(main())


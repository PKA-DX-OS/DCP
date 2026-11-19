# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import logging
import asyncio
import asyncpg
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import HTTPException, status
from dxos_core.config import settings
from dxos_core.jwt import UserClaims

logger = logging.getLogger("dxos.db")
_POOL: Optional[asyncpg.Pool] = None


async def get_db_pool() -> Optional[asyncpg.Pool]:
    """
    Khởi tạo hoặc trả về connection pool tới PostgreSQL với cơ chế thử lại có giới hạn.
    Tuân thủ nguyên tắc fail-closed, timeout ngắn (<= 3s) để trả 503 nhanh (O-05).
    """
    global _POOL
    if _POOL is not None:
        return _POOL

    for attempt in range(2):
        try:
            _POOL = await asyncpg.create_pool(
                dsn=settings.postgres_dsn,
                min_size=1,
                max_size=10,
                command_timeout=3.0,
                timeout=2.0,
            )
            return _POOL
        except Exception as e:
            if attempt == 1:
                logger.error(f"Không thể kết nối cơ sở dữ liệu sau các lần thử: {e}")
                return None
            await asyncio.sleep(0.3)
    return None


async def check_db_health() -> bool:
    """Kiểm tra sức khỏe kết nối cơ sở dữ liệu thật."""
    try:
        pool = await get_db_pool()
        if pool is None:
            return False
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1")
            return val == 1
    except Exception:
        return False


async def close_db_pool():
    global _POOL
    if _POOL is not None:
        try:
            await _POOL.close()
        except Exception as e:
            logger.warning(f"Lỗi khi đóng database pool: {e}")
        _POOL = None


@asynccontextmanager
async def get_db_connection(claims: Optional[UserClaims] = None) -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Lấy kết nối cơ sở dữ liệu và tự động thiết lập ngữ cảnh RLS cho người dùng/dịch vụ.
    Nếu cơ sở dữ liệu không sẵn sàng, ném HTTPException 503 (Fail-Closed).
    """
    pool = await get_db_pool()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cơ sở dữ liệu tạm thời không sẵn sàng",
        )

    try:
        async with pool.acquire(timeout=2.0) as conn:
            async with conn.transaction():
                if claims:
                    role_to_set = "svc" if ("dx:service" in claims.roles or claims.tenant == "global") else "web_user"
                    claims_dict = {
                        "sub": claims.sub,
                        "tenant": claims.tenant,
                        "roles": claims.roles,
                        "preferred_username": claims.preferred_username,
                        "role": role_to_set,
                    }
                    claims_json = json.dumps(claims_dict)
                    try:
                        await conn.execute("SELECT set_config('request.jwt.claims', $1, true)", claims_json)
                        await conn.execute(f"SET LOCAL ROLE {role_to_set}")
                    except Exception as e:
                        logger.error(f"Lỗi thiết lập ngữ cảnh cơ sở dữ liệu (SET LOCAL ROLE {role_to_set}): {e}")
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Không thể thiết lập ngữ cảnh phân quyền cơ sở dữ liệu",
                        )
                yield conn
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lỗi truy vấn cơ sở dữ liệu: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cơ sở dữ liệu tạm thời không sẵn sàng",
        )

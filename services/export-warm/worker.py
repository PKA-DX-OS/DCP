# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Worker xuất chuỗi thời gian core.timeseries ra Parquet theo lô (C05).

- Phân vùng: s3://lake/core/timeseries/tenant=<tenant>/thang=<YYYY-MM>/data.parquet
- Chỉ xuất 5 cột đo: tenant, entity_id, metric, ts, value (không có PII).
- Chạy lại: cùng tenant và tháng dùng cùng khóa, PUT ghi đè, không tạo tệp trùng.

Ví dụ:
  python worker.py --month 2026-11                 # mọi tenant, ghi vào bucket lake
  python worker.py --month 2026-11 --tenant <tenant> --local-out dist/warm/export.parquet
"""

import argparse
import asyncio
import io
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger("dxos.export-warm")

BUCKET = "lake"
PREFIX = "core/timeseries"
COLUMNS = ("tenant", "entity_id", "metric", "ts", "value")
SCHEMA = pa.schema([
    ("tenant", pa.string()),
    ("entity_id", pa.string()),
    ("metric", pa.string()),
    ("ts", pa.timestamp("us", tz="UTC")),
    ("value", pa.float64()),
])
TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

FETCH_SQL = """
SELECT tenant, entity_id, metric, ts, value
FROM core.timeseries
WHERE tenant = $1 AND ts >= $2 AND ts < $3
ORDER BY ts, entity_id, metric
"""
LIST_TENANTS_SQL = """
SELECT DISTINCT tenant FROM core.timeseries
WHERE ts >= $1 AND ts < $2
ORDER BY tenant
"""

Fetch = Callable[[str, datetime, datetime], Awaitable[List[Dict]]]
Write = Callable[[str, bytes], None]


def parse_month(month: str) -> Tuple[datetime, datetime]:
    """Trả về (đầu tháng, đầu tháng sau) theo UTC."""
    start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def object_key(tenant: str, month: str) -> str:
    if not TENANT_RE.match(tenant):
        raise ValueError(f"tenant không hợp lệ: {tenant}")
    parse_month(month)
    return f"{PREFIX}/tenant={tenant}/thang={month}/data.parquet"


def build_table(rows: List[Dict]) -> pa.Table:
    cols: Dict[str, list] = {c: [] for c in COLUMNS}
    for r in rows:
        for c in COLUMNS:
            cols[c].append(r[c])
    return pa.Table.from_pydict(cols, schema=SCHEMA)


def table_to_bytes(table: pa.Table) -> bytes:
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    return buf.getvalue()


async def export_month(tenants: List[str], month: str, fetch: Fetch, write: Write) -> List[Dict]:
    """Xuất từng tenant một (mỗi tenant-tháng là một lô)."""
    start, end = parse_month(month)
    report: List[Dict] = []
    for tenant in tenants:
        rows = await fetch(tenant, start, end)
        key = object_key(tenant, month)
        data = table_to_bytes(build_table(rows))
        write(key, data)
        report.append({"tenant": tenant, "thang": month, "key": key, "so_dong": len(rows)})
        logger.info(f"Đã xuất {tenant} {month}: {len(rows)} dòng -> {key}")
    return report


def make_s3_writer() -> Write:
    from dxos_core.storage import storage_client

    def write(key: str, data: bytes) -> None:
        storage_client.put_object(BUCKET, key, data, content_type="application/vnd.apache.parquet")

    return write


def make_local_writer(path: Path) -> Write:
    def write(_key: str, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    return write


async def make_db_access():
    from dxos_core.db import get_db_pool

    pool = await get_db_pool()
    if pool is None:
        raise RuntimeError("Không kết nối được cơ sở dữ liệu")

    async def fetch(tenant: str, start: datetime, end: datetime) -> List[Dict]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(FETCH_SQL, tenant, start, end)
        return [dict(r) for r in rows]

    async def list_tenants(start: datetime, end: datetime) -> List[str]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(LIST_TENANTS_SQL, start, end)
        return [r["tenant"] for r in rows]

    return fetch, list_tenants


async def _run(args) -> int:
    fetch, list_tenants = await make_db_access()
    start, end = parse_month(args.month)
    tenants = args.tenant or await list_tenants(start, end)
    if not tenants:
        logger.info("Không có dữ liệu trong tháng này")
        return 0
    if args.local_out:
        if len(tenants) != 1:
            raise SystemExit("--local-out chỉ dùng với đúng một --tenant")
        write = make_local_writer(Path(args.local_out))
    else:
        write = make_s3_writer()
    report = await export_month(tenants, args.month, fetch, write)
    for item in report:
        print(item)
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(description="Xuất core.timeseries ra Parquet theo lô")
    p.add_argument("--month", required=True, help="YYYY-MM")
    p.add_argument("--tenant", action="append", help="Có thể lặp; bỏ trống = mọi tenant")
    p.add_argument("--local-out", help="Ghi ra file cục bộ (chỉ với một tenant)")
    args = p.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
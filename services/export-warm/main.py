# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import asyncio
import io
from datetime import datetime, timezone
import pyarrow as pa
import pyarrow.parquet as pq
from dxos_core.db import get_db_pool
from dxos_core.storage import storage_client
from dxos_core.lineage import record_lineage_event


async def run_export_warm():
    print("=== [export-warm] Bắt đầu kết xuất dữ liệu sang Data Lake Parquet ===")
    pool = await get_db_pool()
    now = datetime.now(timezone.utc)
    thang_str = now.strftime("%Y-%m")
    total_exported = 0

    storage_client.ensure_buckets()

    async with pool.acquire() as conn:
        # 1. Kết xuất timeseries cũ hơn 7 ngày (hoặc toàn bộ trong chế độ demo)
        rows = await conn.fetch(
            """
            SELECT tenant, entity_id, metric, ts, value
            FROM core.timeseries
            ORDER BY ts ASC
            """
        )

        if rows:
            # Gom nhóm theo tenant
            tenants = set(r["tenant"] for r in rows)
            for t in tenants:
                t_rows = [r for r in rows if r["tenant"] == t]
                data_dict = {
                    "entity_id": [r["entity_id"] for r in t_rows],
                    "metric": [r["metric"] for r in t_rows],
                    "ts": [r["ts"].isoformat() for r in t_rows],
                    "value": [float(r["value"]) for r in t_rows],
                }
                table = pa.Table.from_pydict(data_dict)
                buf = io.BytesIO()
                pq.write_table(table, buf, compression="snappy")
                parquet_bytes = buf.getvalue()

                parquet_key = f"core/timeseries/tenant={t}/thang={thang_str}/data.parquet"
                storage_client.put_object("lake", parquet_key, parquet_bytes, "application/octet-stream")
                total_exported += len(t_rows)
                print(f"  - Đã xuất {len(t_rows)} bản ghi timeseries vào s3://lake/{parquet_key}")

        # 2. Ghi nhận phả hệ OpenLineage
        await record_lineage_event(
            job="export_warm_lakehouse",
            inputs=[{"name": "core.timeseries"}],
            outputs=[{"name": f"s3://lake/core/timeseries/thang={thang_str}/"}],
            facets={"exported_records": total_exported, "compression": "snappy"},
        )

    print(f"=== [export-warm] Hoàn thành kết xuất {total_exported} bản ghi vào Data Lake ===")


if __name__ == "__main__":
    asyncio.run(run_export_warm())

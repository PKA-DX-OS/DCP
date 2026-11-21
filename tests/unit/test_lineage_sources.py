# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from dxos_core.lineage import _matches_source, get_lineage_by_sources


def test_matches_source():
    assert _matches_source({"name": "core.timeseries"}, ["core.timeseries"])
    assert _matches_source({"namespace": "core", "name": "timeseries"}, ["core.timeseries"])
    assert _matches_source({"name": "timeseries"}, ["core.timeseries"])
    assert not _matches_source({"name": "other.table"}, ["core.timeseries"])
    assert not _matches_source(None, ["core.timeseries"])
    assert not _matches_source("not-dict", ["core.timeseries"])


@pytest.mark.asyncio
async def test_get_lineage_by_sources_loc_dung_nguon_va_tenant(monkeypatch):
    sample_rows = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "event_time": datetime(2026, 11, 21, 10, 0, tzinfo=timezone.utc),
            "job": "job_a",
            "run_id": "r1",
            "inputs": json.dumps([{"name": "core.table_a"}]),
            "outputs": json.dumps([{"name": "core.table_b"}]),
            "facets": json.dumps({"tenant": "tenant-1"}),
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "event_time": datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc),
            "job": "export_warm_lakehouse",
            "run_id": "r2",
            "inputs": json.dumps([{"name": "core.timeseries"}]),
            "outputs": json.dumps([{"name": "s3://lake/core/timeseries/thang=2026-11/"}]),
            "facets": json.dumps({"tenant": "tenant-1"}),
        },
    ]

    class FakeConn:
        async def fetch(self, sql, *args):
            return sample_rows

    @asynccontextmanager
    async def fake_db():
        yield FakeConn()

    monkeypatch.setattr("dxos_core.lineage.get_db_connection", fake_db)

    # Khớp core.table_a -> chỉ trả job_a, không trả export_warm_lakehouse
    res = await get_lineage_by_sources(["core.table_a"], tenant="tenant-1")
    assert len(res) == 1
    assert res[0]["job"] == "job_a"

    # Không khớp bảng nào -> trả rỗng
    res_empty = await get_lineage_by_sources(["core.non_existent"], tenant="tenant-1")
    assert res_empty == []

    # sources rỗng -> trả rỗng
    assert await get_lineage_by_sources([]) == []


@pytest.mark.asyncio
async def test_export_warm_ghi_lineage(monkeypatch):
    import importlib.util

    ROOT = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "export_warm_worker", ROOT / "services" / "export-warm" / "worker.py"
    )
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)

    recorded_events = []

    async def fake_record(job, inputs, outputs, facets=None, run_id=None):
        recorded_events.append({"job": job, "inputs": inputs, "outputs": outputs, "facets": facets})
        return "event-id-1"

    monkeypatch.setattr("dxos_core.lineage.record_lineage_event", fake_record)

    async def fake_fetch(tenant, start, end):
        return [{"tenant": tenant, "entity_id": "e1", "metric": "m1", "ts": start, "value": 1.0}]

    written = {}

    def fake_write(key, data):
        written[key] = data

    report = await worker.export_month(["t1"], "2026-11", fake_fetch, fake_write)
    assert len(report) == 1
    assert len(recorded_events) == 1
    ev = recorded_events[0]
    assert ev["job"] == "export_warm_lakehouse"
    assert ev["inputs"] == [{"name": "core.timeseries"}]
    assert ev["outputs"][0]["name"].startswith("s3://lake/core/timeseries/tenant=t1/thang=2026-11/")
    assert ev["facets"]["tenant"] == "t1"
    assert ev["facets"]["thang"] == "2026-11"

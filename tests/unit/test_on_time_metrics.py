# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-25: tỷ lệ cấp phép đúng hạn tính theo ngày cấp giấy phép và giờ Việt Nam."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from services.construction.routers import metrics

ROOT = Path(__file__).resolve().parents[2]


def test_cau_sql_on_time_dung_ngay_cap_va_gio_viet_nam():
    src = (ROOT / "services/construction/routers/metrics.py").read_text(encoding="utf-8")
    assert "app_cap_phep.giay_phep g" in src
    assert "g.ngay_cap <= h.han_tong_at" in src
    assert "date_trunc('month', g.ngay_cap AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = m.thang" in src
    assert "now() AT TIME ZONE 'Asia/Ho_Chi_Minh'" in src
    # Không còn dùng updated_at hay lọc theo trạng thái hồ sơ DA_CAP
    assert "h.updated_at <= h.han_tong_at" not in src
    assert "date_trunc('month', h.updated_at)" not in src


def test_on_time_endpoint_tra_ve_dung_cau_truc(monkeypatch):
    class _Conn:
        async def fetch(self, sql, months):
            assert "g.ngay_cap <= h.han_tong_at" in sql
            assert months == 6
            return [
                {"thang": "2026-06", "da_cap": 0, "dung_han": 0, "ty_le": None},
                {"thang": "2026-11", "da_cap": 28, "dung_han": 28, "ty_le": 100.0},
            ]

    @asynccontextmanager
    async def _db(*_a, **_k):
        yield _Conn()

    claims = SimpleNamespace(tenant="phuong-a", roles=["app:cap-phep:lanh-dao"], sub="s")
    monkeypatch.setattr(metrics, "verify_jwt_token", lambda _a: claims)
    monkeypatch.setattr(metrics, "yeu_cau_can_bo", lambda _c: None)
    monkeypatch.setattr(metrics, "ngu_canh_tong_hop", lambda _c, _t: SimpleNamespace(tenant="phuong-a", roles=claims.roles, sub="s"))
    monkeypatch.setattr(metrics, "get_db_connection", _db)

    res = asyncio.run(metrics.on_time(months=6, tenant=None, authorization="Bearer test"))
    assert res["tenant"] == "phuong-a"
    assert res["months"] == 6
    assert len(res["items"]) == 2
    assert res["items"][0]["thang"] == "2026-06" and res["items"][0]["ty_le"] is None
    assert res["items"][1]["thang"] == "2026-11" and res["items"][1]["ty_le"] == 100.0

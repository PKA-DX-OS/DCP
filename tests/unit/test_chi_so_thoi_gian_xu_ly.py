# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-20: thời gian xử lý tính theo ngày cấp và ngày làm việc, null khi chưa có mẫu; /metrics nhận tháng."""

import asyncio
import importlib.util
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
VN = timezone(timedelta(hours=7))


@pytest.fixture()
def api():
    spec = importlib.util.spec_from_file_location("metrics_api_ky", ROOT / "services/metrics-api/main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _chi_so():
    data = yaml.safe_load((ROOT / "apps/cap-phep/app.yaml").read_text(encoding="utf-8"))
    return {m["code"]: m for m in data["metrics"]}


def test_ky_thang_theo_gio_viet_nam(api):
    assert api.ky_thang(None) == (None, None)
    assert api.ky_thang("2026-11") == (datetime(2026, 11, 1, tzinfo=VN), datetime(2026, 12, 1, tzinfo=VN))
    assert api.ky_thang("2026-12") == (datetime(2026, 12, 1, tzinfo=VN), datetime(2027, 1, 1, tzinfo=VN))
    for sai in ("2026-13", "2026-1", "11-2026", "2026-11-01"):
        with pytest.raises(HTTPException) as e:
            api.ky_thang(sai)
        assert e.value.status_code == 422


def test_kiem_tra_tham_so_ky(api):
    goc = {"code": "x", "name": "x", "unit": "x", "query_type": "transactional"}
    assert api.validate_metric_policy({**goc, "sql": "SELECT 1 WHERE $1 = $1 AND $2 IS NULL"})
    assert api.validate_metric_policy({**goc, "sql": "SELECT 1 WHERE $1 = $1 AND $4 IS NULL"})
    assert api.validate_metric_policy({**goc, "sql": "SELECT 1 WHERE $1 = $1 AND $2 < $3"}) is None


def test_chi_so_thoi_gian_dung_ngay_cap_ngay_lam_viec_va_ky(api):
    m = _chi_so()
    tb = m["thoi_gian_xu_ly_tb"]
    assert "app_cap_phep.so_ngay_lam_viec(h.created_at, g.ngay_cap)" in tb["sql"]
    assert "COALESCE" not in tb["sql"]  # chưa có giấy phép thì null, không phải 0
    assert "ngày làm việc" in tb["name"] and tb["unit"] == "ngày"
    for code in ("thoi_gian_xu_ly_tb", "ty_le_dung_han", "ho_so_moi"):
        assert "$2" in m[code]["sql"] and "$3" in m[code]["sql"]
        assert api.validate_metric_policy({**m[code], "code": code}) is None
    assert "g.ngay_cap <= h.han_tong_at" in m["ty_le_dung_han"]["sql"]


def test_ham_ngay_lam_viec_cung_quy_tac_bao_cao():
    sql = (ROOT / "apps/cap-phep/db/migrations/21-ngay-lam-viec.sql").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION app_cap_phep.so_ngay_lam_viec(p_tu timestamptz, p_den timestamptz)" in sql
    assert "AT TIME ZONE 'Asia/Ho_Chi_Minh'" in sql and "isodow" in sql


def test_api_truyen_ky_va_giu_null(api, monkeypatch):
    goi = []

    class _Conn:
        async def fetch(self, *a):
            return [
                {"policy_key": "dem", "policy_data": {"code": "dem", "name": "Đếm", "unit": "hồ sơ",
                                                      "query_type": "transactional", "sql": "SELECT count(*) FROM t WHERE c = $1"}},
                {"policy_key": "tb", "policy_data": {"code": "tb", "name": "TB", "unit": "ngày",
                                                     "query_type": "hybrid", "sql": "SELECT avg(x) FROM t WHERE c = $1 AND d >= $2 AND d < $3"}},
            ]

        async def fetchval(self, sql, *tham_so):
            goi.append(tham_so)
            return 5 if "count" in sql else None

        @asynccontextmanager
        async def transaction(self):
            yield

    @asynccontextmanager
    async def _db(*_a, **_k):
        yield _Conn()

    monkeypatch.setattr(api, "verify_jwt_token", lambda _a: SimpleNamespace(tenant="dv", roles=[], sub="s"))
    monkeypatch.setattr(api, "ngu_canh_tong_hop", lambda c, t: SimpleNamespace(tenant="dv", roles=[], sub="s"))
    monkeypatch.setattr(api, "get_db_connection", _db)
    res = asyncio.run(api.get_executive_metrics(tenant=None, thang="2026-11", authorization="Bearer x"))
    assert res["thang"] == "2026-11"
    assert goi[0] == ("dv",)
    assert goi[1] == ("dv", datetime(2026, 11, 1, tzinfo=VN), datetime(2026, 12, 1, tzinfo=VN))
    gia_tri = {m["code"]: m for m in res["metrics"]}
    assert gia_tri["dem"]["value"] == 5 and gia_tri["dem"]["theo_ky"] is False
    assert gia_tri["tb"]["value"] is None and gia_tri["tb"]["theo_ky"] is True

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""metrics-api phải đọc được core.app_policies.policy_data khi asyncpg trả jsonb dưới dạng chuỗi.

Trước đây mã gọi .get() thẳng trên chuỗi, lỗi bị get_db_connection quy thành 503
nên GET /api/v1/metrics luôn hỏng trên hệ thống thật.
"""
import importlib.util
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

SERVICES = Path(__file__).resolve().parents[2] / "services"


def _load():
    spec = importlib.util.spec_from_file_location("metrics_api_main", SERVICES / "metrics-api" / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Tx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _Conn:
    def __init__(self, rows):
        self.rows = rows

    def transaction(self):
        return _Tx()

    async def fetch(self, *a):
        return self.rows

    async def fetchval(self, sql, *a):
        return {"SELECT 7": 7, "SELECT 1": 1}.get(sql, 0)


def test_policy_data_accepts_string_and_dict():
    m = _load()
    assert m._policy_data('{"code": "a"}') == {"code": "a"}
    assert m._policy_data({"code": "b"}) == {"code": "b"}
    assert m._policy_data("không phải json") == {}
    assert m._policy_data(None) == {}


def test_metrics_endpoint_with_jsonb_as_string():
    m = _load()
    rows = [
        {"policy_key": "ho_so_moi", "policy_data": json.dumps({"code": "ho_so_moi", "name": "Hồ sơ mới", "unit": "hồ sơ", "sql": "SELECT 7"})},
        {"policy_key": "ho_so_qua_han", "policy_data": json.dumps({"code": "ho_so_qua_han", "name": "Quá hạn", "unit": "hồ sơ", "sql": "SELECT 1"})},
        {"policy_key": "ty_le_dung_han", "policy_data": json.dumps({"code": "ty_le_dung_han", "name": "Đúng hạn", "unit": "%"})},
    ]

    @asynccontextmanager
    async def fake_db(claims=None):
        yield _Conn(rows)

    m.get_db_connection = fake_db
    m.verify_jwt_token = lambda a: SimpleNamespace(tenant="t1", roles=[], sub="u")
    res = TestClient(m.app).get("/api/v1/metrics", headers={"Authorization": "Bearer x"})
    assert res.status_code == 200
    by_code = {x["code"]: x["value"] for x in res.json()["metrics"]}
    assert by_code["ho_so_moi"] == 7
    assert by_code["ho_so_qua_han"] == 1
    assert by_code["ty_le_dung_han"] == round((1 - 1 / 7) * 100, 1)

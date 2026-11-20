# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Kiểm thử cấu hình chỉ số điều hành dạng JSON (C04).

Chỉ số do app khai báo trong apps/cap-phep/app.yaml (lõi không giữ danh sách nghiệp vụ);
test đọc qua hợp đồng app như app_manager. Không cần database: thay get_db_connection
và verify_jwt_token bằng bản giả lập.
"""

import importlib.util
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CODES = [
    "ho_so_moi",
    "ho_so_dang_xu_ly",
    "ho_so_qua_han",
    "thoi_gian_xu_ly_tb",
    "truy_cap_tu_choi",
    "phieu_kiem_tra",
    "canh_bao_cong_truong",
    "ho_so_fail_quy_hoach",
    "ho_so_dang_nghiem_thu",
    "ty_le_dung_han",
    "vi_pham",
]


def _load():
    spec = importlib.util.spec_from_file_location(
        "metrics_api_main", ROOT / "services" / "metrics-api" / "main.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load()

from dxos_core.app_contract import load_app_manifest  # noqa: E402

# Giống app_manager: mỗi chỉ số là model_dump() kèm thu_tu theo thứ tự khai báo
POLICIES = [
    {**d.model_dump(), "thu_tu": i}
    for i, d in enumerate(load_app_manifest(ROOT / "apps" / "cap-phep").metrics, start=1)
]


# ---------- cấu hình JSON ----------

def test_dung_11_chi_so_dung_ma():
    assert [p["code"] for p in POLICIES] == EXPECTED_CODES


def test_moi_chi_so_co_pha_he():
    for p in POLICIES:
        assert p["lineage_job"] and p["bang_nguon"] and p["dieu_kien_loc"], p["code"]


def test_loi_khong_giu_danh_sach_chi_so_nghiep_vu():
    assert not hasattr(m, "METRIC_POLICIES")


def test_moi_cau_hinh_serialize_duoc_thanh_json():
    for p in POLICIES:
        json.dumps(p, ensure_ascii=False)


def test_moi_cau_hinh_hop_le():
    for p in POLICIES:
        assert m.validate_metric_policy(p) is None, p["code"]


def test_sql_chi_la_select_va_co_tham_so_tenant():
    for p in POLICIES:
        sql = p["sql"].strip().lower()
        assert sql.startswith("select"), p["code"]
        assert "$1" in p["sql"], p["code"]
        assert ";" not in p["sql"], p["code"]


@pytest.mark.parametrize("bad_sql", [
    "DELETE FROM app_cap_phep.ho_so WHERE tenant = $1",
    "SELECT count(*) FROM app_cap_phep.ho_so; DROP TABLE x",
    "SELECT count(*) FROM app_cap_phep.ho_so",
    "UPDATE app_cap_phep.ho_so SET x = 1 WHERE tenant = $1",
])
def test_tu_choi_sql_khong_an_toan(bad_sql):
    policy = dict(POLICIES[0], sql=bad_sql)
    assert m.validate_metric_policy(policy) is not None


def test_tu_choi_thieu_truong_va_query_type_la():
    assert m.validate_metric_policy({"code": "x"}) is not None
    policy = dict(POLICIES[0], query_type="khong_co")
    assert m.validate_metric_policy(policy) is not None


def test_policy_data_chap_nhan_chuoi_va_dict():
    assert m._policy_data('{"code": "a"}') == {"code": "a"}
    assert m._policy_data({"code": "b"}) == {"code": "b"}
    assert m._policy_data("không phải json") == {}
    assert m._policy_data(None) == {}


# ---------- endpoint với DB giả lập ----------

class _FakeConn:
    """Ghi lại tenant được truyền vào mỗi câu SQL; có thể cho một câu lỗi."""

    def __init__(self, policy_rows, fail_codes=()):
        self.policy_rows = policy_rows
        self.fail_codes = set(fail_codes)
        self.tenant_args = []

    async def fetch(self, sql, *args):
        return self.policy_rows

    @asynccontextmanager
    async def _tx(self):
        yield

    def transaction(self):
        return self._tx()

    async def fetchval(self, sql, *args):
        self.tenant_args.append(args[0])
        for code in self.fail_codes:
            if code in sql:
                raise RuntimeError("lỗi giả lập")
        return 3


def _rows(codes=EXPECTED_CODES):
    return [
        {"policy_key": p["code"], "policy_data": json.dumps(p, ensure_ascii=False)}
        for p in POLICIES if p["code"] in codes
    ]


def _client(monkeypatch, tenant, conn):
    monkeypatch.setattr(m, "verify_jwt_token",
                        lambda auth: SimpleNamespace(sub="u1", tenant=tenant, roles=[]))

    @asynccontextmanager
    async def fake_db(claims=None):
        yield conn

    monkeypatch.setattr(m, "get_db_connection", fake_db)
    return TestClient(m.app)


def test_endpoint_tra_du_8_chi_so_dung_kieu(monkeypatch):
    conn = _FakeConn(_rows())
    r = _client(monkeypatch, "phuong-a", conn).get("/api/v1/metrics", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    body = r.json()
    assert [x["code"] for x in body["metrics"]] == EXPECTED_CODES
    for x in body["metrics"]:
        assert isinstance(x["value"], int)
        assert x["unit"]


def test_moi_cau_sql_nhan_tenant_tu_token(monkeypatch):
    conn = _FakeConn(_rows())
    _client(monkeypatch, "phuong-a", conn).get("/api/v1/metrics", headers={"Authorization": "Bearer x"})
    assert conn.tenant_args and set(conn.tenant_args) == {"phuong-a"}


def test_tenant_b_khong_nhan_tenant_cua_a(monkeypatch):
    conn = _FakeConn(_rows())
    _client(monkeypatch, "phuong-b", conn).get("/api/v1/metrics", headers={"Authorization": "Bearer x"})
    assert "phuong-a" not in conn.tenant_args


def test_mot_chi_so_loi_khong_lam_hong_ca_phan_hoi(monkeypatch):
    conn = _FakeConn(_rows(), fail_codes=["app_cap_phep.phieu_kiem_tra WHERE tenant = $1 AND ket_luan"])
    r = _client(monkeypatch, "phuong-a", conn).get("/api/v1/metrics", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    by_code = {x["code"]: x for x in r.json()["metrics"]}
    assert by_code["vi_pham"]["value"] is None and by_code["vi_pham"]["error"] == "loi_tinh_toan"
    assert by_code["ho_so_moi"]["value"] == 3


def test_chi_tra_chi_so_da_nap_theo_thu_tu(monkeypatch):
    rows = list(reversed(_rows(codes=EXPECTED_CODES[:7])))
    r = _client(monkeypatch, "phuong-a", _FakeConn(rows)).get("/api/v1/metrics", headers={"Authorization": "Bearer x"})
    assert [x["code"] for x in r.json()["metrics"]] == EXPECTED_CODES[:7]


def test_chua_cai_app_thi_danh_sach_rong(monkeypatch):
    r = _client(monkeypatch, "phuong-a", _FakeConn([])).get("/api/v1/metrics", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200 and r.json()["metrics"] == []


def test_cau_hinh_sai_tra_loi_ro_rang(monkeypatch):
    rows = _rows()
    hong = dict(POLICIES[-1], sql="DELETE FROM x WHERE tenant = $1")
    rows[-1] = {"policy_key": hong["code"], "policy_data": json.dumps(hong, ensure_ascii=False)}
    r = _client(monkeypatch, "phuong-a", _FakeConn(rows)).get("/api/v1/metrics", headers={"Authorization": "Bearer x"})
    by_code = {x["code"]: x for x in r.json()["metrics"]}
    assert by_code["vi_pham"]["value"] is None and by_code["vi_pham"]["error"].startswith("cau_hinh_sai")


def test_pha_he_lay_tu_cau_hinh_va_404_khi_khong_co(monkeypatch):
    async def fake_hist(job, limit=10):
        return [{"job": job, "facets": {"tenant": "phuong-a"}}, {"job": job, "facets": {"tenant": "phuong-b"}}]

    monkeypatch.setattr(m, "get_lineage_history", fake_hist)
    c = _client(monkeypatch, "phuong-a", _FakeConn(_rows()))
    r = c.get("/api/v1/metrics/canh_bao_cong_truong/lineage", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    body = r.json()
    assert body["job"] == "iot_ingest" and body["bang_nguon"] == ["core.outbox"]
    assert len(body["lineage_events"]) == 1
    assert c.get("/api/v1/metrics/khong_co/lineage", headers={"Authorization": "Bearer x"}).status_code == 404

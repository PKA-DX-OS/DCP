# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Kiểm thử không cần Docker cho U-01, U-02, U-03, U-04.

- U-01: không còn đường tải bản gốc công khai; tải bản gốc bắt buộc JWT và quyền theo đối tượng.
- U-02: trang /kiem-tra escape mọi giá trị, có CSP, không nạp script ngoài.
- U-03: kiểu MIME do máy chủ quyết định, tệp không an toàn tải về dạng attachment.
- U-04: mô phỏng cảm biến không tự tạo cảnh báo khi chưa vượt ngưỡng, không gán tenant mặc định.
"""
import importlib.util
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

SERVICES = Path(__file__).resolve().parents[2] / "services"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, SERVICES / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeConn:
    def __init__(self, row=None, fetchval=None, rows=None):
        self.row = row
        self._fetchval = fetchval
        self.rows = rows or []
        self.executed = []

    async def fetchrow(self, *a):
        return self.row

    async def fetchval(self, *a):
        return self._fetchval(*a) if callable(self._fetchval) else self._fetchval

    async def fetch(self, *a):
        return self.rows

    async def execute(self, *a):
        self.executed.append(a)


def _db(conn):
    @asynccontextmanager
    async def _ctx(*_a, **_k):
        yield conn
    return _ctx


SIGNED_ROW = {
    "id": "6f0c2b9e-1111-4c1a-9e0a-000000000001",
    "public_code": "DOC-abcDEF123_xyz",
    "doc_type": "giay-phep-xay-dung",
    "tenant": "phuong-a",
    "status": "valid",
    "issued_at": datetime(2026, 11, 10, tzinfo=timezone.utc),
    "revoked_at": None,
    "sha256": "a" * 64,
    "key_version": "3",
    "algorithm": "Ed25519",
    "signature": "vault:v3:MEUCIQ",
    "signer_sub": "u-lanh-dao",
    "object_key": "phuong-a/2026/x.pdf",
    "object_type": "ho_so",
    "object_id": "8ecddedb-fd24-4847-8a24-775a590a5e1b",
}


@pytest.fixture()
def docsign(monkeypatch):
    mod = _load("docsign_u01", "doc-sign/main.py")
    return mod


def test_U01_khong_con_tai_ban_goc_cong_khai(docsign, monkeypatch):
    monkeypatch.setattr(docsign, "get_db_connection", _db(FakeConn(row=SIGNED_ROW)))
    c = TestClient(docsign.app)
    r = c.get(f"/kiem-tra/{SIGNED_ROW['public_code']}/download")
    assert r.status_code in (404, 405)
    assert not r.content.startswith(b"%PDF")


def test_U01_tai_ban_goc_bat_buoc_token(docsign):
    c = TestClient(docsign.app)
    r = c.get(f"/api/v1/docs/{SIGNED_ROW['id']}/download")
    assert r.status_code == 422 or r.status_code == 401


def test_U01_tai_ban_goc_bi_tu_choi_khi_khong_co_quyen(docsign, monkeypatch):
    claims = SimpleNamespace(sub="u-lan", tenant="phuong-a", roles=["app:cap-phep:chu-dau-tu"])
    monkeypatch.setattr(docsign, "verify_jwt_token", lambda _h: claims)
    monkeypatch.setattr(docsign, "get_db_connection", _db(FakeConn(row=SIGNED_ROW, fetchval=False)))
    audits = []

    async def _audit(**kw):
        audits.append(kw)
    monkeypatch.setattr(docsign, "log_audit_event", _audit)
    c = TestClient(docsign.app)
    r = c.get(f"/api/v1/docs/{SIGNED_ROW['id']}/download", headers={"Authorization": "Bearer x"})
    assert r.status_code == 404
    assert audits and audits[0]["action"] == "access.denied"


def test_U01_tai_ban_goc_khac_dia_ban_bi_tu_choi(docsign, monkeypatch):
    claims = SimpleNamespace(sub="u-b", tenant="phuong-b", roles=["app:cap-phep:lanh-dao"])
    monkeypatch.setattr(docsign, "verify_jwt_token", lambda _h: claims)
    monkeypatch.setattr(docsign, "get_db_connection", _db(FakeConn(row=SIGNED_ROW, fetchval=True)))

    async def _audit(**kw):
        return None
    monkeypatch.setattr(docsign, "log_audit_event", _audit)
    c = TestClient(docsign.app)
    r = c.get(f"/api/v1/docs/{SIGNED_ROW['id']}/download", headers={"Authorization": "Bearer x"})
    assert r.status_code == 404


def test_U01_chu_ho_so_tai_duoc_va_co_audit(docsign, monkeypatch):
    claims = SimpleNamespace(sub="u-minh", tenant="phuong-a", roles=["app:cap-phep:chu-dau-tu"])
    monkeypatch.setattr(docsign, "verify_jwt_token", lambda _h: claims)
    monkeypatch.setattr(docsign, "get_db_connection", _db(FakeConn(row=SIGNED_ROW, fetchval=True)))
    monkeypatch.setattr(docsign.storage_client, "get_object", lambda *_a: b"%PDF-1.4 test")
    audits = []

    async def _audit(**kw):
        audits.append(kw)
    monkeypatch.setattr(docsign, "log_audit_event", _audit)
    c = TestClient(docsign.app)
    r = c.get(f"/api/v1/docs/{SIGNED_ROW['id']}/download", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert [a["action"] for a in audits] == ["doc.download"]


def test_U01_trang_cong_khai_khong_co_du_lieu_ca_nhan(docsign, monkeypatch):
    monkeypatch.setattr(docsign, "get_db_connection", _db(FakeConn(row=SIGNED_ROW)))
    c = TestClient(docsign.app)
    for accept in ("text/html", "application/json"):
        r = c.get(f"/kiem-tra/{SIGNED_ROW['public_code']}", headers={"Accept": accept})
        assert r.status_code == 200
        body = r.text
        for leak in ("cccd", "CCCD", "object_key", SIGNED_ROW["object_id"], "/download"):
            assert leak not in body


def test_U01_ma_cong_khai_moi_du_dai(docsign):
    import re as _re
    import secrets as _s
    code = f"DOC-{_s.token_urlsafe(16)}"
    assert len(code) >= 26 and _re.fullmatch(r"[A-Za-z0-9_-]{6,64}", code)
    src = (SERVICES / "doc-sign/main.py").read_text(encoding="utf-8")
    assert "token_hex(4)" not in src


@pytest.mark.parametrize("payload", [
    "<img src=x onerror=alert(1)>",
    "\"><script>alert(1)</script>",
    "DOC-1'onmouseover='x",
])
def test_U02_trang_404_khong_phan_xa_ma(docsign, monkeypatch, payload):
    monkeypatch.setattr(docsign, "get_db_connection", _db(FakeConn(row=None)))
    c = TestClient(docsign.app)
    r = c.get("/kiem-tra/" + payload, headers={"Accept": "text/html"})
    assert r.status_code == 404
    assert "<img" not in r.text and "<script" not in r.text and "onmouseover" not in r.text
    if "/" not in payload:  # có "/" thì không khớp route, FastAPI trả 404 JSON mặc định
        assert "default-src 'none'" in r.headers.get("content-security-policy", "")


def test_U02_gia_tri_trong_db_duoc_escape(docsign, monkeypatch):
    row = dict(SIGNED_ROW, doc_type="<script>alert(1)</script>", tenant="<b>x</b>")
    monkeypatch.setattr(docsign, "get_db_connection", _db(FakeConn(row=row)))
    c = TestClient(docsign.app)
    r = c.get(f"/kiem-tra/{row['public_code']}", headers={"Accept": "text/html"})
    assert r.status_code == 200
    assert "<script>" not in r.text and "&lt;script&gt;" in r.text and "<b>x</b>" not in r.text
    assert "cdn." not in r.text and "<script" not in r.text
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


@pytest.fixture()
def files_mod():
    return _load("files_u03", "files/main.py")


def test_U03_mime_do_may_chu_quyet_dinh(files_mod):
    assert files_mod.MIME_BY_EXT["txt"].startswith("text/plain")
    src = (SERVICES / "files/main.py").read_text(encoding="utf-8")
    assert "file.content_type" not in src


@pytest.mark.parametrize("stored,expected_type,expected_disp", [
    ("text/html", "application/octet-stream", "attachment"),
    ("text/plain; charset=utf-8", "text/plain; charset=utf-8", "attachment"),
    ("application/pdf", "application/pdf", "inline"),
])
def test_U03_tai_ve_an_toan(files_mod, monkeypatch, stored, expected_type, expected_disp):
    row = {
        "id": "6f0c2b9e-2222-4c1a-9e0a-000000000002", "tenant": "phuong-a", "owner_sub": "u-minh",
        "object_type": "ho_so", "object_id": "x", "object_key": "phuong-a/2026/a\"b<c>.txt",
        "sha256": "0" * 64, "size": 4, "mime": stored, "status": "clean",
    }
    claims = SimpleNamespace(sub="u-minh", tenant="phuong-a", roles=[])
    monkeypatch.setattr(files_mod, "verify_jwt_token", lambda _h: claims)
    monkeypatch.setattr(files_mod, "get_db_connection", _db(FakeConn(row=row)))
    monkeypatch.setattr(files_mod.storage_client, "get_object", lambda *_a: b"<script>alert(1)</script>")
    c = TestClient(files_mod.app)
    r = c.get(f"/api/v1/files/{row['id']}/download", headers={"Authorization": "Bearer x"})
    assert r.status_code == 200
    assert r.headers["content-type"] == expected_type
    assert r.headers["content-disposition"].startswith(expected_disp)
    assert r.headers["x-content-type-options"] == "nosniff"
    assert 'filename="a_b_c_.txt"' in r.headers["content-disposition"]


@pytest.fixture()
def ingest_mod(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    return _load("ingest_u04", "ingest/main.py")


def _ingest_setup(mod, monkeypatch, site_ok=True):
    claims = SimpleNamespace(sub="u-khanh", tenant="phuong-a", roles=["app:cap-phep:trat-tu-xd"])
    monkeypatch.setattr(mod, "verify_jwt_token", lambda _h: claims)
    policy_row = {"policy_data": {"demo_sensor": {"roles": ["app:cap-phep:trat-tu-xd"],
                                                   "site_check": "app_x.kiem_tra"}}}
    conn = FakeConn(rows=[policy_row], fetchval=site_ok)
    monkeypatch.setattr(mod, "get_db_connection", _db(conn))
    events = []

    async def _emit(**kw):
        events.append(kw)
    monkeypatch.setattr(mod, "emit_outbox_event", _emit)
    return conn, events


def test_U04_duoi_nguong_khong_phat_canh_bao(ingest_mod, monkeypatch):
    _, events = _ingest_setup(ingest_mod, monkeypatch)
    monkeypatch.setattr(ingest_mod, "check_threshold_breach", lambda *_a: None)
    c = TestClient(ingest_mod.app)
    r = c.post("/api/v1/ingest/demo-sensor", json={"site_id": "CT-01", "value": 40},
               headers={"Authorization": "Bearer x"})
    assert r.status_code == 200 and r.json()["status"] == "within_limit"
    assert events == []


def test_U04_vi_tri_phuong_khac_bi_tu_choi(ingest_mod, monkeypatch):
    _, events = _ingest_setup(ingest_mod, monkeypatch, site_ok=False)
    c = TestClient(ingest_mod.app)
    r = c.post("/api/v1/ingest/demo-sensor", json={"site_id": "CT-02", "value": 90},
               headers={"Authorization": "Bearer x"})
    assert r.status_code == 404 and events == []


def test_U04_thieu_tenant_bi_tu_choi(ingest_mod, monkeypatch):
    _ingest_setup(ingest_mod, monkeypatch)
    monkeypatch.setattr(ingest_mod, "verify_jwt_token",
                        lambda _h: SimpleNamespace(sub="svc", tenant="", roles=["dx:platform-admin"]))
    c = TestClient(ingest_mod.app)
    r = c.post("/api/v1/ingest/demo-sensor", json={"site_id": "CT-01", "value": 90},
               headers={"Authorization": "Bearer x"})
    assert r.status_code == 400


def test_token_sai_tra_401_khong_phai_500():
    from fastapi import HTTPException
    from dxos_core.jwt import verify_jwt_token
    with pytest.raises(HTTPException) as ei:
        verify_jwt_token("Bearer khong.phai.jwt")
    assert ei.value.status_code == 401


def test_U02_trang_cong_khai_co_doi_soat_khong_script(docsign, monkeypatch):
    """Biểu mẫu đối soát PDF gửi về chính máy chủ, không cần script (CSP chặn mọi script)."""
    monkeypatch.setattr(docsign, "get_db_connection", _db(FakeConn(row=SIGNED_ROW)))
    r = TestClient(docsign.app).get(f"/kiem-tra/{SIGNED_ROW['public_code']}", headers={"Accept": "text/html"})
    assert r.status_code == 200
    assert f'action="/kiem-tra/{SIGNED_ROW["public_code"]}/verify-file"' in r.text
    assert "<script" not in r.text
    assert "script-src" not in r.headers["content-security-policy"]


def test_U02_doi_soat_qua_bieu_mau_tra_trang_ket_qua(docsign, monkeypatch):
    monkeypatch.setattr(docsign, "get_db_connection", _db(FakeConn(row=SIGNED_ROW)))
    monkeypatch.setattr(docsign.openbao_client, "verify", lambda *_a: False)
    r = TestClient(docsign.app).post(
        f"/kiem-tra/{SIGNED_ROW['public_code']}/verify-file",
        headers={"Accept": "text/html"},
        files={"file": ("x.pdf", b"%PDF-1.4 sai", "application/pdf")},
    )
    assert r.status_code == 200
    assert 'id="verify-result"' in r.text and "không khớp" in r.text
    assert "<script" not in r.text


def test_U01_nguoi_ky_tai_lai_van_ban_khong_gan_ho_so(docsign, monkeypatch):
    """Văn bản ký ngoài hồ sơ (không có object): chỉ người đã ký tải lại được."""
    row = dict(SIGNED_ROW, object_type=None, object_id=None, signer_sub="nguoi-ky")
    monkeypatch.setattr(docsign, "get_db_connection", _db(FakeConn(row=row)))
    monkeypatch.setattr(docsign.storage_client, "get_object", lambda *_a: b"%PDF-1.4")
    audits = []

    async def fake_audit(**kw):
        audits.append(kw)

    monkeypatch.setattr(docsign, "log_audit_event", fake_audit)
    c = TestClient(docsign.app)
    monkeypatch.setattr(docsign, "verify_jwt_token", lambda _a: SimpleNamespace(sub="nguoi-ky", tenant="phuong-a", roles=[]))
    assert c.get(f"/api/v1/docs/{row['id']}/download", headers={"Authorization": "Bearer x"}).status_code == 200
    monkeypatch.setattr(docsign, "verify_jwt_token", lambda _a: SimpleNamespace(sub="nguoi-khac", tenant="phuong-a", roles=[]))
    assert c.get(f"/api/v1/docs/{row['id']}/download", headers={"Authorization": "Bearer x"}).status_code == 404

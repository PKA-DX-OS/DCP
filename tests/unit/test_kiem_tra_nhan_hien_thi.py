# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-19: trang tra cứu công khai hiện tên loại văn bản và tên đơn vị đã đăng ký, không hiện mã."""

import importlib.util
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]

ROW = {
    "public_code": "ABCD2345EFGH",
    "doc_type": "loai-van-ban-mau",
    "tenant": "don-vi-mau",
    "status": "valid",
    "issued_at": datetime(2026, 11, 10, tzinfo=timezone.utc),
    "revoked_at": None,
    "sha256": "a" * 64,
    "key_version": "3",
    "algorithm": "Ed25519",
    "signature": "vault:v3:MEUCIQ",
}


@pytest.fixture()
def docsign():
    spec = importlib.util.spec_from_file_location("docsign_nhan", ROOT / "services/doc-sign/main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _db(row):
    class _Conn:
        async def fetchrow(self, *a):
            return row

    @asynccontextmanager
    async def _ctx(*_a, **_k):
        yield _Conn()

    return _ctx


def test_hien_ten_da_dang_ky(docsign, monkeypatch):
    row = {**ROW, "ten_loai_van_ban": "Văn bản mẫu", "ten_don_vi": "Đơn vị mẫu"}
    monkeypatch.setattr(docsign, "get_db_connection", _db(row))
    c = TestClient(docsign.app)
    html = c.get(f"/kiem-tra/{ROW['public_code']}", headers={"Accept": "text/html"}).text
    assert "<dd>Văn bản mẫu</dd>" in html and "<dd>Đơn vị mẫu</dd>" in html
    assert "loai-van-ban-mau" not in html and "don-vi-mau" not in html
    js = c.get(f"/kiem-tra/{ROW['public_code']}", headers={"Accept": "application/json"}).json()
    assert js["doc_type"] == "loai-van-ban-mau" and js["ten_loai_van_ban"] == "Văn bản mẫu"
    assert js["tenant"] == "don-vi-mau" and js["ten_don_vi"] == "Đơn vị mẫu"


def test_chua_dang_ky_thi_dung_ma(docsign, monkeypatch):
    monkeypatch.setattr(docsign, "get_db_connection", _db({**ROW, "ten_loai_van_ban": None, "ten_don_vi": None}))
    html = TestClient(docsign.app).get(f"/kiem-tra/{ROW['public_code']}", headers={"Accept": "text/html"}).text
    assert "<dd>loai-van-ban-mau</dd>" in html and "<dd>don-vi-mau</dd>" in html


def test_truy_van_lay_ten_tu_danh_muc():
    src = (ROOT / "services/doc-sign/main.py").read_text(encoding="utf-8")
    assert "LEFT JOIN core.tenants t ON t.tenant = d.tenant" in src
    assert "p.policy_type = 'doc_templates'" in src
    am = (ROOT / "scripts/app_manager.py").read_text(encoding="utf-8")
    assert "'doc_templates'" in am and "tpl.title" in am

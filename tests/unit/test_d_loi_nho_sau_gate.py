# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Kiểm thử FIX-V11-30: Các lỗi nhỏ Track D sau Gate 1.

1. Handler RequestValidationError ở services/construction và services/ocr trả {code: 'VALIDATION_ERROR', message, details: {fields: [...]}}.
2. Giao vấn đề DQ: assigned_to nhận cả sub lẫn username trong cùng phường; không tìm thấy trả 422 DQ_ASSIGNEE_NOT_FOUND.
3. POST /api/v1/ocr/extract ghi audit ocr.requested (không ghi fields).
4. confirm/reject OCR: kiểm bản ghi tồn tại theo phường trước khi kiểm body, không có thì 404 NOT_FOUND.
5. /api/v1/metrics/{code}/lineage trả job: null thay vì "".
"""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

import ocr.main as ocr_module
from ocr.main import app as ocr_app
from construction.main import app as construction_app
import construction.routers.data_quality as dq_router
from tests.integration._auth import get_token


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


def _h(user: str, idem: str = None) -> dict:
    headers = {"Authorization": f"Bearer {get_token(user)}"}
    if idem:
        headers["Idempotency-Key"] = idem
    return headers


# --- 1. Test RequestValidationError handler cho cả 2 dịch vụ ---

@pytest.mark.asyncio
async def test_construction_validation_error_format():
    transport = ASGITransport(app=construction_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Gửi body sai tới /api/v1/data-quality/issues/{id}/assign (thiếu assigned_to)
        r = await client.post(
            f"/api/v1/data-quality/issues/{uuid.uuid4()}/assign",
            headers=_h("ld.hoa", idem="idem-test-1234"),
            json={"sai_truong": "abc"},
        )
        assert r.status_code == 422
        data = r.json()
        assert data["code"] == "VALIDATION_ERROR"
        assert data["message"] == "Dữ liệu không hợp lệ"
        assert "fields" in data["details"]
        fields = [f["field"] for f in data["details"]["fields"]]
        assert "assigned_to" in fields


@pytest.mark.asyncio
async def test_ocr_validation_error_format():
    ocr_module.DH_OCR_ENABLED = True
    transport = ASGITransport(app=ocr_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Gửi body thiếu doc_type hoặc doc_type sai
        r = await client.post(
            "/api/v1/ocr/extract",
            headers=_h("mc.thu", idem="idem-test-ocr-val"),
            json={"file_id": str(uuid.uuid4()), "doc_type": "loai_sai"},
        )
        assert r.status_code == 422
        data = r.json()
        assert data["code"] == "VALIDATION_ERROR"
        assert data["message"] == "Dữ liệu không hợp lệ"
        assert "fields" in data["details"]
        fields = [f["field"] for f in data["details"]["fields"]]
        assert "doc_type" in fields


# --- 2. Test DQ Assign: nhận cả sub lẫn username, 422 DQ_ASSIGNEE_NOT_FOUND khi không thấy ---

@pytest.mark.asyncio
async def test_dq_assign_username_and_sub(monkeypatch):
    issue_id = uuid.uuid4()
    steward_sub = str(uuid.uuid4())
    fake_user_dir = {
        # sub -> username
        steward_sub: {"sub": steward_sub, "username": "mc.thu"},
        "mc.thu": {"sub": steward_sub, "username": "mc.thu"},
    }

    audit_logs = []
    notifications = []
    db_issue = {
        "id": issue_id,
        "tenant": "phuong-a",
        "rule_code": "R_TEST",
        "domain": "ho_so",
        "entity_type": "ho_so",
        "entity_id": "HS-01",
        "field": "ngay_sinh",
        "severity": "warn",
        "status": "open",
        "assigned_to": None,
        "note": None,
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
        "dossier_id": None,
    }

    class MockDQConn:
        @asynccontextmanager
        async def transaction(self):
            yield self

        async def fetchrow(self, query, *args):
            if "FROM core.data_quality_issues" in query:
                return FakeRecord(db_issue)
            if "FROM core.users_directory" in query:
                param = args[0]
                user = fake_user_dir.get(param)
                if user:
                    return FakeRecord({"sub": user["sub"], "username": user["username"]})
                return None
            if "UPDATE core.data_quality_issues SET status = 'in_progress'" in query:
                db_issue["status"] = "in_progress"
                db_issue["assigned_to"] = args[1]
                db_issue["note"] = args[2]
                return FakeRecord(db_issue)
            return None

        async def fetchval(self, query, *args):
            return None

        async def execute(self, query, *args):
            if "core.notifications" in query:
                notifications.append(args)
            return "OK"

    @asynccontextmanager
    async def fake_get_db(claims=None):
        yield MockDQConn()

    async def fake_log_audit(**kwargs):
        audit_logs.append(kwargs)

    monkeypatch.setattr(dq_router, "get_db_connection", fake_get_db)
    monkeypatch.setattr(dq_router, "log_audit_event", fake_log_audit)

    transport = ASGITransport(app=construction_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 2a. Giao bằng username "mc.thu"
        r1 = await client.post(
            f"/api/v1/data-quality/issues/{issue_id}/assign",
            headers=_h("ld.hoa", idem="idem-assign-user"),
            json={"assigned_to": "mc.thu", "note": "Giao xu ly"},
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["assigned_to"] == steward_sub
        assert db_issue["assigned_to"] == steward_sub

        # 2b. Giao bằng sub UUID
        db_issue["status"] = "open"
        r2 = await client.post(
            f"/api/v1/data-quality/issues/{issue_id}/assign",
            headers=_h("ld.hoa", idem="idem-assign-sub"),
            json={"assigned_to": steward_sub, "note": "Giao bang sub"},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["assigned_to"] == steward_sub

        # 2c. Không tìm thấy người nhận trong phường -> 422 DQ_ASSIGNEE_NOT_FOUND
        r3 = await client.post(
            f"/api/v1/data-quality/issues/{issue_id}/assign",
            headers=_h("ld.hoa", idem="idem-assign-notfound"),
            json={"assigned_to": "nguoi_la_mat", "note": "Thu giao"},
        )
        assert r3.status_code == 422
        res3 = r3.json()
        assert res3["code"] == "DQ_ASSIGNEE_NOT_FOUND"
        assert res3["message"] == "Không tìm thấy người nhận trong phường"


# --- 3, 4. Test OCR audit requested và 404 trước khi kiểm body ---

@pytest.mark.asyncio
async def test_ocr_requested_audit_and_cross_tenant_404(monkeypatch):
    ocr_module.DH_OCR_ENABLED = True
    file_id = str(uuid.uuid4())
    extraction_id = str(uuid.uuid4())

    state = {
        "files": {
            (file_id, "phuong-a"): {
                "id": uuid.UUID(file_id),
                "tenant": "phuong-a",
                "object_type": "ho_so",
                "object_id": str(uuid.uuid4()),
                "status": "clean",
                "owner_sub": "demo_sub",
            }
        },
        "extractions": {
            extraction_id: {
                "id": uuid.UUID(extraction_id),
                "tenant": "phuong-a",
                "file_id": uuid.UUID(file_id),
                "dossier_id": None,
                "doc_type": "cccd",
                "status": "needs_review",
                "confidence": 0.85,
                "fields": [],
                "reviewed_by": None,
                "reviewed_at": None,
                "reject_reason": None,
                "error": None,
                "idempotency_key": "idem-111",
                "created_at": datetime.now(timezone.utc),
            }
        },
        "audit_logs": [],
    }

    class MockConn:
        async def fetchrow(self, query, *args):
            if "FROM core.files" in query:
                f_id, tenant = args[0], args[1]
                f = state["files"].get((str(f_id), tenant))
                return FakeRecord(f) if f else None
            if "FROM app_cap_phep.ocr_extractions" in query and "idempotency_key = $2" in query:
                return None
            if "INSERT INTO app_cap_phep.ocr_extractions" in query:
                new_id = uuid.uuid4()
                rec = {
                    "id": new_id,
                    "tenant": args[0],
                    "file_id": args[1],
                    "dossier_id": args[2],
                    "doc_type": args[3],
                    "status": "queued",
                    "confidence": None,
                    "fields": [],
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "reject_reason": None,
                    "error": None,
                    "idempotency_key": args[4],
                    "created_at": datetime.now(timezone.utc),
                }
                state["extractions"][str(new_id)] = rec
                return FakeRecord(rec)
            if "FROM app_cap_phep.ocr_extractions" in query and "WHERE id = $1 AND tenant = $2" in query:
                rec_id, tenant = args[0], args[1]
                ext = state["extractions"].get(str(rec_id))
                if ext and ext["tenant"] == tenant:
                    return FakeRecord(ext)
                return None
            return None

        async def execute(self, query, *args):
            if "core.record_audit" in query:
                action_name = "unknown"
                for act in ("ocr.requested", "ocr.read", "ocr.confirmed", "ocr.rejected"):
                    if act in query:
                        action_name = act
                        break
                state["audit_logs"].append({
                    "tenant": args[0],
                    "sub": args[1],
                    "action": action_name,
                    "entity_id": args[2],
                    "detail": json.loads(args[3]),
                })
            return "OK"

    @asynccontextmanager
    async def fake_get_db(claims=None):
        yield MockConn()

    monkeypatch.setattr(ocr_module, "get_db_connection", fake_get_db)

    transport = ASGITransport(app=ocr_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 3. POST /api/v1/ocr/extract ghi audit ocr.requested (không ghi fields)
        r_ext = await client.post(
            "/api/v1/ocr/extract",
            headers=_h("mc.thu", idem="idem-req-audit-test"),
            json={"file_id": file_id, "doc_type": "cccd"},
        )
        assert r_ext.status_code == 202
        new_id = r_ext.json()["id"]

        audits = [a for a in state["audit_logs"] if a["action"] == "ocr.requested" and a["entity_id"] == new_id]
        assert len(audits) == 1
        assert "fields" not in audits[0]["detail"]
        assert audits[0]["detail"]["doc_type"] == "cccd"
        assert audits[0]["detail"]["file_id"] == file_id

        # 4. Phường B gọi confirm/reject tới bản ghi phường A:
        # Dù body SAI (rỗng hoặc không khớp schema), vẫn nhận 404 NOT_FOUND thay vì 422
        r_conf_b = await client.post(
            f"/api/v1/ocr/{extraction_id}/confirm",
            headers=_h("mc.phuongb", idem="idem-b-conf"),
            json={"invalid_body": True},
        )
        assert r_conf_b.status_code == 404
        assert r_conf_b.json()["code"] == "NOT_FOUND"

        r_rej_b = await client.post(
            f"/api/v1/ocr/{extraction_id}/reject",
            headers=_h("mc.phuongb", idem="idem-b-rej"),
            json={},  # Thiếu reason
        )
        assert r_rej_b.status_code == 404
        assert r_rej_b.json()["code"] == "NOT_FOUND"

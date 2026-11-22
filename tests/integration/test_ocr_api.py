# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""D-OCR: Test tích hợp toàn diện API OCR và hàng chờ duyệt (Gate 3)."""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

import ocr.main as ocr_module
from ocr.main import app
from tests.integration._auth import get_token


class FakeRecord(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


class MockDBConn:
    def __init__(self, state):
        self.state = state

    @asynccontextmanager
    async def transaction(self):
        yield self

    async def fetchrow(self, query, *args):
        # 1. Tra cứu tệp trong core.files
        if "FROM core.files" in query:
            file_id, tenant = args[0], args[1]
            f = self.state["files"].get((str(file_id), tenant))
            if not f:
                return None
            return FakeRecord(f)

        # 2. Tra cứu idempotency trong ocr_extractions
        if "FROM app_cap_phep.ocr_extractions" in query and "idempotency_key = $2" in query:
            tenant, idem = args[0], args[1]
            for ext in self.state["extractions"].values():
                if ext["tenant"] == tenant and ext.get("idempotency_key") == idem:
                    return FakeRecord(ext)
            return None

        # 3. Tra cứu chi tiết ocr_extractions theo id và tenant
        if "FROM app_cap_phep.ocr_extractions" in query and "WHERE id = $1 AND tenant = $2" in query:
            rec_id, tenant = args[0], args[1]
            ext = self.state["extractions"].get(str(rec_id))
            if ext and ext["tenant"] == tenant:
                return FakeRecord(ext)
            return None

        # 4. INSERT vào ocr_extractions
        if "INSERT INTO app_cap_phep.ocr_extractions" in query:
            tenant, file_id, dossier_id, doc_type, idem_key = args[0], args[1], args[2], args[3], args[4]
            new_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            rec = {
                "id": new_id,
                "tenant": tenant,
                "file_id": file_id,
                "dossier_id": dossier_id,
                "doc_type": doc_type,
                "status": "queued",
                "confidence": None,
                "fields": [],
                "reviewed_by": None,
                "reviewed_at": None,
                "reject_reason": None,
                "error": None,
                "idempotency_key": idem_key,
                "created_at": now,
            }
            self.state["extractions"][str(new_id)] = rec
            return FakeRecord(rec)

        # 5. UPDATE confirm
        if "UPDATE app_cap_phep.ocr_extractions" in query and "SET status = 'confirmed'" in query:
            fields_json, reviewed_by, rec_id, tenant = args[0], args[1], args[2], args[3]
            ext = self.state["extractions"].get(str(rec_id))
            if ext and ext["tenant"] == tenant:
                ext["status"] = "confirmed"
                ext["fields"] = json.loads(fields_json)
                ext["reviewed_by"] = reviewed_by
                ext["reviewed_at"] = datetime.now(timezone.utc)
                return FakeRecord(ext)
            return None

        # 6. UPDATE reject
        if "UPDATE app_cap_phep.ocr_extractions" in query and "SET status = 'rejected'" in query:
            reason, reviewed_by, rec_id, tenant = args[0], args[1], args[2], args[3]
            ext = self.state["extractions"].get(str(rec_id))
            if ext and ext["tenant"] == tenant:
                ext["status"] = "rejected"
                ext["reject_reason"] = reason
                ext["reviewed_by"] = reviewed_by
                ext["reviewed_at"] = datetime.now(timezone.utc)
                return FakeRecord(ext)
            return None

        return None

    async def fetchval(self, query, *args):
        if "SELECT count(*) FROM app_cap_phep.ocr_extractions" in query:
            tenant = args[0]
            count = sum(1 for e in self.state["extractions"].values() if e["tenant"] == tenant)
            return count
        return 0

    async def fetch(self, query, *args):
        if "FROM app_cap_phep.ocr_extractions" in query:
            tenant = args[0]
            # TUYỆT ĐỐI KHÔNG trả trường fields
            res = []
            for e in self.state["extractions"].values():
                if e["tenant"] == tenant:
                    res.append(FakeRecord({
                        "id": e["id"],
                        "file_id": e["file_id"],
                        "dossier_id": e["dossier_id"],
                        "doc_type": e["doc_type"],
                        "status": e["status"],
                        "confidence": e["confidence"],
                        "created_at": e["created_at"],
                    }))
            return res
        return []

    async def execute(self, query, *args):
        if "core.record_audit" in query:
            action_name = "unknown"
            for act in ("ocr.requested", "ocr.read", "ocr.confirmed", "ocr.rejected"):
                if act in query:
                    action_name = act
                    break
            self.state["audit_logs"].append({
                "tenant": args[0],
                "sub": args[1],
                "action": action_name,
                "entity_id": args[2],
                "detail": json.loads(args[3]),
            })
            return "RECORD"
        return "OK"


def _h(user: str, idem: str = None) -> dict:
    headers = {"Authorization": f"Bearer {get_token(user)}"}
    if idem:
        headers["Idempotency-Key"] = idem
    return headers


@pytest.mark.asyncio
async def test_ocr_api_when_disabled():
    # 1. Kiểm tra khi DH_OCR tắt (mặc định) -> 503 OCR_DISABLED
    ocr_module.DH_OCR_ENABLED = False
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r_ext = await client.post(
            "/api/v1/ocr/extract",
            headers=_h("mc.thu", idem="idem-test-12345"),
            json={"file_id": str(uuid.uuid4()), "doc_type": "cccd"},
        )
        assert r_ext.status_code == 503
        data = r_ext.json()
        assert data["code"] == "OCR_DISABLED"
        assert "DH_OCR=false" in data["message"]

        r_list = await client.get("/api/v1/ocr", headers=_h("mc.thu"))
        assert r_list.status_code == 503

        r_health = await client.get("/healthz")
        assert r_health.status_code == 200
        assert r_health.json()["dh_ocr"] is False


@pytest.mark.asyncio
async def test_ocr_api_full_workflow(monkeypatch):
    # 2. Bật cờ DH_OCR = True
    ocr_module.DH_OCR_ENABLED = True
    transport = ASGITransport(app=app)

    file_id = str(uuid.uuid4())
    infected_file_id = str(uuid.uuid4())
    idem_key = f"idem-ocr-{uuid.uuid4().hex[:16]}"

    # Mock DB State
    db_state = {
        "files": {
            (file_id, "phuong-a"): {
                "id": uuid.UUID(file_id),
                "tenant": "phuong-a",
                "object_type": "ho_so",
                "object_id": str(uuid.uuid4()),
                "status": "clean",
                "owner_sub": "demo_sub",
            },
            (infected_file_id, "phuong-a"): {
                "id": uuid.UUID(infected_file_id),
                "tenant": "phuong-a",
                "object_type": "generic",
                "object_id": None,
                "status": "infected",
                "owner_sub": "demo_sub",
            },
        },
        "extractions": {},
        "audit_logs": [],
    }

    @asynccontextmanager
    async def mock_get_db_connection(claims=None):
        yield MockDBConn(db_state)

    monkeypatch.setattr(ocr_module, "get_db_connection", mock_get_db_connection)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 2.1 Thiếu Idempotency-Key -> 422
        r_no_idem = await client.post(
            "/api/v1/ocr/extract",
            headers=_h("mc.thu"),
            json={"file_id": file_id, "doc_type": "cccd"},
        )
        assert r_no_idem.status_code == 422

        # 2.1b Body sai trường -> 422 VALIDATION_ERROR theo hop dong (Mục 1)
        r_val_err = await client.post(
            "/api/v1/ocr/extract",
            headers=_h("mc.thu", idem="idem-test-val-err"),
            json={"doc_type": "khong_hop_le"},
        )
        assert r_val_err.status_code == 422
        val_data = r_val_err.json()
        assert val_data["code"] == "VALIDATION_ERROR"
        assert "fields" in val_data["details"]
        assert len(val_data["details"]["fields"]) >= 1

        # 2.2 Tệp bị nhiễm hoặc chưa quét -> 409
        r_infected = await client.post(
            "/api/v1/ocr/extract",
            headers=_h("mc.thu", idem=idem_key),
            json={"file_id": infected_file_id, "doc_type": "cccd"},
        )
        assert r_infected.status_code == 409
        assert r_infected.json()["code"] == "FILE_NOT_CLEAN"

        # 2.3 Gửi yêu cầu trích xuất hợp lệ -> 202
        r_ext = await client.post(
            "/api/v1/ocr/extract",
            headers=_h("mc.thu", idem=idem_key),
            json={"file_id": file_id, "doc_type": "cccd"},
        )
        assert r_ext.status_code == 202, r_ext.text
        ext_data = r_ext.json()
        assert ext_data["file_id"] == file_id
        assert ext_data["doc_type"] == "cccd"
        assert ext_data["status"] == "queued"
        extraction_id = ext_data["id"]

        # 2.3b Kiểm tra audit ocr.requested đã được ghi (Mục 3)
        req_audit = next((log for log in db_state["audit_logs"] if log.get("action") == "ocr.requested" and log["entity_id"] == extraction_id), None)
        assert req_audit is not None
        assert "fields" not in req_audit["detail"]
        assert req_audit["detail"]["doc_type"] == "cccd"
        assert req_audit["detail"]["file_id"] == file_id

        # Idempotency: Gửi lại cùng Idempotency-Key trả đúng bản ghi đã tạo
        r_ext_dup = await client.post(
            "/api/v1/ocr/extract",
            headers=_h("mc.thu", idem=idem_key),
            json={"file_id": file_id, "doc_type": "cccd"},
        )
        assert r_ext_dup.status_code == 202
        assert r_ext_dup.json()["id"] == extraction_id

        # Giả lập worker đã trích xuất xong -> chuyển trạng thái needs_review
        db_state["extractions"][extraction_id]["status"] = "needs_review"
        db_state["extractions"][extraction_id]["confidence"] = 0.895
        db_state["extractions"][extraction_id]["fields"] = [
            {"name": "so_cccd", "value": "001099001234", "confidence": 0.95, "edited": False},
            {"name": "ho_ten", "value": "Nguyen Van A", "confidence": 0.90, "edited": False},
        ]

        # 2.4 Hàng chờ: GET /api/v1/ocr
        r_list = await client.get("/api/v1/ocr?status=needs_review", headers=_h("mc.thu"))
        assert r_list.status_code == 200
        list_data = r_list.json()
        assert list_data["total"] >= 1
        # QUAN TRỌNG: Danh sách hàng chờ không trả fields (Yêu cầu 5 PII)
        found = next((item for item in list_data["items"] if item["id"] == extraction_id), None)
        assert found is not None
        assert "fields" not in found
        assert found["confidence"] == 0.895

        # Cách ly phường: Cán bộ phường B không thấy bản ghi phường A
        r_list_b = await client.get("/api/v1/ocr", headers=_h("mc.phuongb"))
        assert r_list_b.status_code == 200
        found_b = next((item for item in r_list_b.json()["items"] if item["id"] == extraction_id), None)
        assert found_b is None

        # 2.5 Chi tiết: GET /api/v1/ocr/{id}
        r_detail = await client.get(f"/api/v1/ocr/{extraction_id}", headers=_h("mc.thu"))
        assert r_detail.status_code == 200
        detail_data = r_detail.json()
        assert "fields" in detail_data
        assert len(detail_data["fields"]) == 2
        assert detail_data["fields"][0]["name"] == "so_cccd"

        # 2.6 Xác nhận: POST /api/v1/ocr/{id}/confirm
        # Cán bộ sửa lại tên thành NGUYỄN VĂN AN (hoa)
        confirm_idem = f"idem-conf-{uuid.uuid4().hex[:12]}"
        r_conf = await client.post(
            f"/api/v1/ocr/{extraction_id}/confirm",
            headers=_h("mc.thu", idem=confirm_idem),
            json={
                "fields": [
                    {"name": "so_cccd", "value": "001099001234"},
                    {"name": "ho_ten", "value": "NGUYỄN VĂN AN"},
                ]
            },
        )
        assert r_conf.status_code == 200
        conf_data = r_conf.json()
        assert conf_data["status"] == "confirmed"
        f_hoten = next(f for f in conf_data["fields"] if f["name"] == "ho_ten")
        assert f_hoten["value"] == "NGUYỄN VĂN AN"
        assert f_hoten["edited"] is True
        f_cccd = next(f for f in conf_data["fields"] if f["name"] == "so_cccd")
        assert f_cccd["edited"] is False

        # 2.7 Kiểm tra audit log: KHÔNG ghi fields
        audit_entries = [log for log in db_state["audit_logs"] if log["entity_id"] == extraction_id]
        assert len(audit_entries) >= 1
        last_audit = audit_entries[-1]["detail"]
        assert "NGUYỄN VĂN AN" not in str(last_audit)  # Không lộ PII trong audit log
        assert "edited_count" in last_audit

        # 2.8 Kiểm tra từ chối trên bản ghi khác
        ext_rej_id = str(uuid.uuid4())
        db_state["extractions"][ext_rej_id] = {
            "id": uuid.UUID(ext_rej_id),
            "tenant": "phuong-a",
            "file_id": uuid.UUID(file_id),
            "dossier_id": None,
            "doc_type": "cccd",
            "status": "needs_review",
            "confidence": 0.5,
            "fields": [],
            "reviewed_by": None,
            "reviewed_at": None,
            "reject_reason": None,
            "error": None,
            "idempotency_key": "rej-idem-1",
            "created_at": datetime.now(timezone.utc),
        }

        # 2.9 Mục 4: confirm/reject bản ghi phường khác trả 404 kể cả khi body sai
        r_conf_other_tenant = await client.post(
            f"/api/v1/ocr/{ext_rej_id}/confirm",
            headers=_h("mc.phuongb", idem="idem-conf-phuongb"),
            json={"body_sai": 123},  # body hoàn toàn sai schema
        )
        assert r_conf_other_tenant.status_code == 404
        assert r_conf_other_tenant.json()["code"] == "NOT_FOUND"

        r_rej_other_tenant = await client.post(
            f"/api/v1/ocr/{ext_rej_id}/reject",
            headers=_h("mc.phuongb", idem="idem-rej-phuongb"),
            json={"sai_field": "test"},  # body thiếu reason
        )
        assert r_rej_other_tenant.status_code == 404
        assert r_rej_other_tenant.json()["code"] == "NOT_FOUND"

        # Bản ghi đúng phường nhưng body sai -> 422 VALIDATION_ERROR
        r_rej_bad_body = await client.post(
            f"/api/v1/ocr/{ext_rej_id}/reject",
            headers=_h("mc.thu", idem="idem-rej-bad-body"),
            json={"reason": "ab"},  # min_length 3 -> lỗi
        )
        assert r_rej_bad_body.status_code == 422
        assert r_rej_bad_body.json()["code"] == "VALIDATION_ERROR"
        assert "fields" in r_rej_bad_body.json()["details"]

        r_rej = await client.post(
            f"/api/v1/ocr/{ext_rej_id}/reject",
            headers=_h("mc.thu", idem="idem-rej-12345"),
            json={"reason": "Hình ảnh quá mờ không đọc được thông tin"},
        )
        assert r_rej.status_code == 200
        rej_data = r_rej.json()
        assert rej_data["status"] == "rejected"
        assert rej_data["reject_reason"] == "Hình ảnh quá mờ không đọc được thông tin"

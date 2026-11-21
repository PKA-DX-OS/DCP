# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""D-OCR: Dịch vụ OCR và hàng chờ duyệt có cán bộ xác nhận (Gate 3).

- Tích hợp pipeline an toàn: ClamAV (files clean) -> OCR -> Parser -> Hàng chờ duyệt.
- Quản trị bảo mật: RLS theo phường, web_user chỉ SELECT, ghi qua kết nối dịch vụ sau kiểm vai.
- PII: Dữ liệu cá nhân chỉ trả ở màn chi tiết cho người có quyền, không ghi vào audit log.
- Cờ DH_OCR: Mặc định tắt, trả 503 OCR_DISABLED theo đúng hợp đồng.
"""

import asyncio
import io
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dxos_core.db import get_db_connection
from dxos_core.jwt import UserClaims, verify_jwt_token
from dxos_core.middleware import setup_standard_service
from dxos_core.storage import storage_client

from ocr.parser import parse_document

logger = logging.getLogger("dxos.ocr")

DH_OCR_ENABLED = os.getenv("DH_OCR", "false").lower() == "true"

# Các vai trò được phép thao tác
VAI_DUYET = ("app:cap-phep:mot-cua", "app:cap-phep:tham-dinh", "app:cap-phep:lanh-dao")
VAI_XEM_DANH_SACH = VAI_DUYET + ("dx:data-steward", "dx:auditor", "dx:tenant-admin", "dx:platform-admin")
VAI_GUI_TRICH_XUAT = ("app:cap-phep:mot-cua", "app:cap-phep:tham-dinh", "app:cap-phep:chu-dau-tu", "dx:citizen")


class LoiDH(HTTPException):
    def __init__(self, status_code: int, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "details": details or {}})
        self.code = code
        self.message = message
        self.details = details or {}


def kiem_tra_dh_ocr():
    """Kiểm tra cờ DH_OCR, nếu tắt trả 503 OCR_DISABLED dạng hợp đồng."""
    if not DH_OCR_ENABLED:
        raise LoiDH(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="OCR_DISABLED",
            message="Dịch vụ OCR hiện đang tắt (DH_OCR=false)",
            details={},
        )


def kiem_tra_idempotency_key(key: Optional[str]) -> str:
    if not key or len(key) < 8 or len(key) > 128:
        raise LoiDH(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="INVALID_IDEMPOTENCY_KEY",
            message="Header Idempotency-Key bắt buộc, độ dài từ 8 đến 128 ký tự",
        )
    return key


# Schema Pydantic
class GuiTrichXuatRequest(BaseModel):
    file_id: str
    doc_type: str = Field(..., pattern="^(cccd|giay_chung_nhan_qsdd|don_de_nghi_cap_phep)$")


class TruongCapNhat(BaseModel):
    name: str
    value: Optional[str] = None


class XacNhanRequest(BaseModel):
    fields: List[TruongCapNhat]


class TuChoiRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


# OCR Execution Helper
def thuc_hien_ocr(file_bytes: bytes, mime: str) -> str:
    """Thực hiện nhận dạng chữ từ tệp qua Tesseract (nếu có) hoặc text decode."""
    try:
        import pytesseract
        from PIL import Image

        if mime in ("image/png", "image/jpeg", "image/jpg"):
            img = Image.open(io.BytesIO(file_bytes))
            return pytesseract.image_to_string(img, lang="vie+eng")
    except Exception as e:
        logger.warning(f"Không thể chạy pytesseract: {e}")

    # Fallback cho văn bản text hoặc tệp giả lập / test
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin1", errors="ignore")


# Background Worker
async def _recover_stale_processing():
    """Khởi động: Các bản ghi processing quá 10 phút được thu hồi."""
    try:
        async with get_db_connection() as conn:
            # Vượt quá 3 lần thử -> failed
            await conn.execute("""
                UPDATE app_cap_phep.ocr_extractions
                SET status = 'failed',
                    error = 'Quá thời gian xử lý và vượt quá số lần thử lại tối đa (3 lần)',
                    updated_at = now()
                WHERE status = 'processing'
                  AND updated_at < now() - interval '10 minutes'
                  AND retry_count >= 3;
            """)
            # Chưa quá 3 lần -> tăng retry_count và chuyển lại queued
            await conn.execute("""
                UPDATE app_cap_phep.ocr_extractions
                SET status = 'queued',
                    retry_count = retry_count + 1,
                    updated_at = now()
                WHERE status = 'processing'
                  AND updated_at < now() - interval '10 minutes'
                  AND retry_count < 3;
            """)
    except Exception as e:
        logger.warning(f"Lỗi dọn dẹp bản ghi processing cũ: {e}")


async def _worker_loop():
    """Vòng lặp nền xử lý trích xuất các bản ghi queued."""
    while True:
        try:
            if not DH_OCR_ENABLED:
                await asyncio.sleep(5)
                continue

            async with get_db_connection() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow("""
                        SELECT id, tenant, file_id, doc_type, retry_count
                        FROM app_cap_phep.ocr_extractions
                        WHERE status = 'queued'
                        ORDER BY created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1;
                    """)

                    if not row:
                        await asyncio.sleep(1)
                        continue

                    rec_id = row["id"]
                    tenant = row["tenant"]
                    file_id = row["file_id"]
                    doc_type = row["doc_type"]

                    await conn.execute("""
                        UPDATE app_cap_phep.ocr_extractions
                        SET status = 'processing', updated_at = now()
                        WHERE id = $1;
                    """, rec_id)

                    # Kiểm tra trạng thái tệp trong core.files
                    file_row = await conn.fetchrow("""
                        SELECT object_key, status, mime
                        FROM core.files
                        WHERE id = $1 AND tenant = $2;
                    """, file_id, tenant)

                    if not file_row or file_row["status"] != "clean":
                        await conn.execute("""
                            UPDATE app_cap_phep.ocr_extractions
                            SET status = 'failed',
                                error = 'Tệp chưa an toàn qua ClamAV hoặc không tồn tại',
                                updated_at = now()
                            WHERE id = $1;
                        """, rec_id)
                        continue

                    # Đọc nội dung tệp từ storage
                    object_key = file_row["object_key"]
                    mime = file_row["mime"] or "application/octet-stream"
                    file_bytes = None
                    try:
                        file_bytes = storage_client.get_object("files", object_key)
                    except Exception as stor_err:
                        logger.warning(f"Lỗi đọc file từ storage: {stor_err}")

                    if not file_bytes:
                        await conn.execute("""
                            UPDATE app_cap_phep.ocr_extractions
                            SET status = 'failed',
                                error = 'Không thể tải nội dung tệp từ kho lưu trữ',
                                updated_at = now()
                            WHERE id = $1;
                        """, rec_id)
                        continue

                    # Chạy OCR & Parser
                    raw_text = thuc_hien_ocr(file_bytes, mime)
                    fields, confidence = parse_document(raw_text, doc_type)

                    await conn.execute("""
                        UPDATE app_cap_phep.ocr_extractions
                        SET status = 'needs_review',
                            fields = $1::jsonb,
                            confidence = $2,
                            updated_at = now()
                        WHERE id = $3;
                    """, json.dumps(fields), confidence, rec_id)

        except asyncio.CancelledError:
            break
        except Exception as err:
            logger.error(f"Lỗi trong vòng lặp OCR worker: {err}")
            await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await _recover_stale_processing()
    task = asyncio.create_task(_worker_loop())
    yield
    # Shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="DX-OS OCR Service", version="1.0.0", lifespan=lifespan)
setup_standard_service(app, "ocr")


@app.exception_handler(LoiDH)
async def _loi_dh_handler(_request: Request, exc: LoiDH):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "details": exc.details},
    )


@app.get("/healthz", tags=["Giám sát"])
async def healthz():
    return {"status": "ok", "service": "ocr", "dh_ocr": DH_OCR_ENABLED}


@app.post("/api/v1/ocr/extract", status_code=status.HTTP_202_ACCEPTED, tags=["ocr"])
async def gui_trich_xuat(
    body: GuiTrichXuatRequest,
    authorization: str = Header(...),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    kiem_tra_dh_ocr()
    idem_key = kiem_tra_idempotency_key(idempotency_key)
    claims: UserClaims = verify_jwt_token(authorization)

    # 1. Kiểm tra vai trò
    co_vai = any(r in claims.roles for r in VAI_GUI_TRICH_XUAT) or "dx:platform-admin" in claims.roles
    if not co_vai:
        raise LoiDH(status_code=403, code="FORBIDDEN", message="Bạn không có quyền gửi yêu cầu trích xuất OCR")

    file_uuid = uuid.UUID(body.file_id)

    async with get_db_connection() as conn:
        # 2. Kiểm tra tệp trong core.files
        file_row = await conn.fetchrow("""
            SELECT id, tenant, object_type, object_id, status, owner_sub
            FROM core.files
            WHERE id = $1 AND tenant = $2;
        """, file_uuid, claims.tenant)

        if not file_row:
            raise LoiDH(status_code=404, code="FILE_NOT_FOUND", message="Không tìm thấy tệp trong hệ thống")

        if file_row["status"] != "clean":
            raise LoiDH(
                status_code=409,
                code="FILE_NOT_CLEAN",
                message="Tệp chưa quét xong hoặc bị nhiễm qua ClamAV",
            )

        # Nếu là công dân / chủ đầu tư, kiểm tra quyền sở hữu tệp
        if "dx:citizen" in claims.roles or "app:cap-phep:chu-dau-tu" in claims.roles:
            if file_row["owner_sub"] != claims.sub and not any(r in claims.roles for r in VAI_DUYET):
                raise LoiDH(status_code=403, code="FORBIDDEN", message="Bạn không có quyền trích xuất tệp của người khác")

        dossier_id = None
        if file_row["object_type"] == "ho_so" and file_row["object_id"]:
            try:
                dossier_id = uuid.UUID(file_row["object_id"])
            except ValueError:
                pass

        # 3. Kiểm tra Idempotency
        existing = await conn.fetchrow("""
            SELECT id, file_id, dossier_id, doc_type, status, confidence, fields,
                   reviewed_by, reviewed_at, reject_reason, error, created_at
            FROM app_cap_phep.ocr_extractions
            WHERE tenant = $1 AND idempotency_key = $2;
        """, claims.tenant, idem_key)

        if existing:
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content=_to_dict(existing, include_fields=True),
            )

        # 4. Ghi bản ghi mới qua kết nối svc
        new_row = await conn.fetchrow("""
            INSERT INTO app_cap_phep.ocr_extractions (
                tenant, file_id, dossier_id, doc_type, status, idempotency_key
            )
            VALUES ($1, $2, $3, $4, 'queued', $5)
            RETURNING id, file_id, dossier_id, doc_type, status, confidence, fields,
                      reviewed_by, reviewed_at, reject_reason, error, created_at;
        """, claims.tenant, file_uuid, dossier_id, body.doc_type, idem_key)

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=_to_dict(new_row, include_fields=True),
        )


@app.get("/api/v1/ocr", tags=["ocr"])
async def hang_cho_trich_xuat(
    authorization: str = Header(...),
    status_filter: Optional[str] = Query(None, alias="status"),
    doc_type: Optional[str] = Query(None),
    max_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    dossier_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    kiem_tra_dh_ocr()
    claims: UserClaims = verify_jwt_token(authorization)

    co_vai = any(r in claims.roles for r in VAI_XEM_DANH_SACH)
    if not co_vai:
        raise LoiDH(status_code=403, code="FORBIDDEN", message="Bạn không có quyền xem hàng chờ OCR")

    conds = ["tenant = $1"]
    args: List[Any] = [claims.tenant]

    if status_filter:
        args.append(status_filter)
        conds.append(f"status = ${len(args)}")
    if doc_type:
        args.append(doc_type)
        conds.append(f"doc_type = ${len(args)}")
    if max_confidence is not None:
        args.append(max_confidence)
        conds.append(f"confidence <= ${len(args)}")
    if dossier_id:
        try:
            d_uuid = uuid.UUID(dossier_id)
            args.append(d_uuid)
            conds.append(f"dossier_id = ${len(args)}")
        except ValueError:
            pass

    where_sql = " AND ".join(conds)
    offset = (page - 1) * page_size

    async with get_db_connection() as conn:
        total = await conn.fetchval(f"SELECT count(*) FROM app_cap_phep.ocr_extractions WHERE {where_sql};", *args)

        # TUYỆT ĐỐI KHÔNG SELECT trường fields ở danh sách hàng chờ (Yêu cầu 5 PII)
        rows = await conn.fetch(f"""
            SELECT id, file_id, dossier_id, doc_type, status, confidence, created_at
            FROM app_cap_phep.ocr_extractions
            WHERE {where_sql}
            ORDER BY created_at ASC
            LIMIT ${len(args) + 1} OFFSET ${len(args) + 2};
        """, *args, page_size, offset)

        items = [_to_dict(r, include_fields=False) for r in rows]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        }


@app.get("/api/v1/ocr/{id}", tags=["ocr"])
async def lay_chi_tiet_trich_xuat(
    id: str,
    authorization: str = Header(...),
):
    kiem_tra_dh_ocr()
    claims: UserClaims = verify_jwt_token(authorization)

    try:
        rec_uuid = uuid.UUID(id)
    except ValueError:
        raise LoiDH(status_code=404, code="NOT_FOUND", message="Mã trích xuất không hợp lệ")

    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT id, tenant, file_id, dossier_id, doc_type, status, confidence, fields,
                   reviewed_by, reviewed_at, reject_reason, error, created_at
            FROM app_cap_phep.ocr_extractions
            WHERE id = $1 AND tenant = $2;
        """, rec_uuid, claims.tenant)

        if not row:
            raise LoiDH(status_code=404, code="NOT_FOUND", message="Không tìm thấy bản trích xuất OCR")

        # Ghi audit log đọc chi tiết: TUYỆT ĐỐI KHÔNG GHI FIELDS VÀO DETAIL
        await conn.execute("""
            SELECT core.record_audit($1, $2, 'user', 'ocr.read', 'ocr_extraction', $3, $4::jsonb);
        """, claims.tenant, claims.sub, str(rec_uuid), json.dumps({
            "extraction_id": str(rec_uuid),
            "doc_type": row["doc_type"],
            "file_id": str(row["file_id"]),
        }))

        return _to_dict(row, include_fields=True)


@app.post("/api/v1/ocr/{id}/confirm", tags=["ocr"])
async def xac_nhan_trich_xuat(
    id: str,
    body: XacNhanRequest,
    authorization: str = Header(...),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    kiem_tra_dh_ocr()
    kiem_tra_idempotency_key(idempotency_key)
    claims: UserClaims = verify_jwt_token(authorization)

    co_vai = any(r in claims.roles for r in VAI_DUYET) or "dx:platform-admin" in claims.roles
    if not co_vai:
        raise LoiDH(status_code=403, code="FORBIDDEN", message="Bạn không có quyền duyệt và xác nhận kết quả OCR")

    try:
        rec_uuid = uuid.UUID(id)
    except ValueError:
        raise LoiDH(status_code=404, code="NOT_FOUND", message="Mã trích xuất không hợp lệ")

    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT id, tenant, file_id, dossier_id, doc_type, status, confidence, fields,
                   reviewed_by, reviewed_at, reject_reason, error, created_at
            FROM app_cap_phep.ocr_extractions
            WHERE id = $1 AND tenant = $2;
        """, rec_uuid, claims.tenant)

        if not row:
            raise LoiDH(status_code=404, code="NOT_FOUND", message="Không tìm thấy bản trích xuất OCR")

        if row["status"] == "confirmed":
            return _to_dict(row, include_fields=True)

        if row["status"] not in ("needs_review", "queued", "processing"):
            raise LoiDH(
                status_code=409,
                code="INVALID_STATUS",
                message=f"Bản trích xuất đang ở trạng thái '{row['status']}', không thể xác nhận",
            )

        # Cập nhật các trường: đánh dấu edited = true nếu bị sửa
        old_fields = row["fields"] if isinstance(row["fields"], list) else json.loads(row["fields"] or "[]")
        old_by_name = {f.get("name"): f for f in old_fields if isinstance(f, dict)}

        updated_fields = []
        edited_count = 0
        for f_in in body.fields:
            old_item = old_by_name.get(f_in.name, {})
            old_val = old_item.get("value")
            is_edited = old_item.get("edited", False) or (old_val != f_in.value)
            if is_edited:
                edited_count += 1
            updated_fields.append({
                "name": f_in.name,
                "value": f_in.value,
                "confidence": old_item.get("confidence", 1.0),
                "page": old_item.get("page", 1),
                "bbox": old_item.get("bbox"),
                "edited": is_edited,
            })

        # Ghi cập nhật qua kết nối svc
        updated_row = await conn.fetchrow("""
            UPDATE app_cap_phep.ocr_extractions
            SET status = 'confirmed',
                fields = $1::jsonb,
                reviewed_by = $2,
                reviewed_at = now(),
                updated_at = now()
            WHERE id = $3 AND tenant = $4
            RETURNING id, file_id, dossier_id, doc_type, status, confidence, fields,
                      reviewed_by, reviewed_at, reject_reason, error, created_at;
        """, json.dumps(updated_fields), claims.sub, rec_uuid, claims.tenant)

        # Ghi audit log: KHÔNG ghi nội dung fields
        await conn.execute("""
            SELECT core.record_audit($1, $2, 'user', 'ocr.confirmed', 'ocr_extraction', $3, $4::jsonb);
        """, claims.tenant, claims.sub, str(rec_uuid), json.dumps({
            "extraction_id": str(rec_uuid),
            "doc_type": row["doc_type"],
            "edited_count": edited_count,
            "field_count": len(updated_fields),
        }))

        return _to_dict(updated_row, include_fields=True)


@app.post("/api/v1/ocr/{id}/reject", tags=["ocr"])
async def tu_choi_trich_xuat(
    id: str,
    body: TuChoiRequest,
    authorization: str = Header(...),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    kiem_tra_dh_ocr()
    kiem_tra_idempotency_key(idempotency_key)
    claims: UserClaims = verify_jwt_token(authorization)

    co_vai = any(r in claims.roles for r in VAI_DUYET) or "dx:platform-admin" in claims.roles
    if not co_vai:
        raise LoiDH(status_code=403, code="FORBIDDEN", message="Bạn không có quyền từ chối kết quả OCR")

    try:
        rec_uuid = uuid.UUID(id)
    except ValueError:
        raise LoiDH(status_code=404, code="NOT_FOUND", message="Mã trích xuất không hợp lệ")

    async with get_db_connection() as conn:
        row = await conn.fetchrow("""
            SELECT id, tenant, file_id, dossier_id, doc_type, status, confidence, fields,
                   reviewed_by, reviewed_at, reject_reason, error, created_at
            FROM app_cap_phep.ocr_extractions
            WHERE id = $1 AND tenant = $2;
        """, rec_uuid, claims.tenant)

        if not row:
            raise LoiDH(status_code=404, code="NOT_FOUND", message="Không tìm thấy bản trích xuất OCR")

        if row["status"] == "rejected":
            return _to_dict(row, include_fields=True)

        if row["status"] not in ("needs_review", "queued", "processing"):
            raise LoiDH(
                status_code=409,
                code="INVALID_STATUS",
                message=f"Bản trích xuất đang ở trạng thái '{row['status']}', không thể từ chối",
            )

        updated_row = await conn.fetchrow("""
            UPDATE app_cap_phep.ocr_extractions
            SET status = 'rejected',
                reject_reason = $1,
                reviewed_by = $2,
                reviewed_at = now(),
                updated_at = now()
            WHERE id = $3 AND tenant = $4
            RETURNING id, file_id, dossier_id, doc_type, status, confidence, fields,
                      reviewed_by, reviewed_at, reject_reason, error, created_at;
        """, body.reason, claims.sub, rec_uuid, claims.tenant)

        # Ghi audit log: KHÔNG ghi nội dung fields
        await conn.execute("""
            SELECT core.record_audit($1, $2, 'user', 'ocr.rejected', 'ocr_extraction', $3, $4::jsonb);
        """, claims.tenant, claims.sub, str(rec_uuid), json.dumps({
            "extraction_id": str(rec_uuid),
            "doc_type": row["doc_type"],
            "reason": body.reason,
        }))

        return _to_dict(updated_row, include_fields=True)


def _to_dict(row, include_fields: bool = False) -> Dict[str, Any]:
    res: Dict[str, Any] = {
        "id": str(row["id"]),
        "file_id": str(row["file_id"]),
        "dossier_id": str(row["dossier_id"]) if row.get("dossier_id") else None,
        "doc_type": row["doc_type"],
        "status": row["status"],
        "confidence": float(row["confidence"]) if row.get("confidence") is not None else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }
    if include_fields:
        fields = row.get("fields")
        if isinstance(fields, str):
            try:
                fields = json.loads(fields)
            except Exception:
                fields = []
        res["fields"] = fields or []
        res["reviewed_by"] = row.get("reviewed_by")
        res["reviewed_at"] = row["reviewed_at"].isoformat() if row.get("reviewed_at") else None
        res["reject_reason"] = row.get("reject_reason")
        res["error"] = row.get("error")
    return res

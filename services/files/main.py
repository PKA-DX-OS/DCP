# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import logging
import re
from urllib.parse import quote
import hashlib
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, status, Response
from fastapi.responses import JSONResponse
from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.db import get_db_connection
from dxos_core.storage import storage_client
from dxos_core.clamav import clamav_client
from dxos_core.audit import log_audit_event

logger = logging.getLogger("dxos.files")

app = FastAPI(title="DX-OS Files Service", version="1.0.0")
setup_standard_service(app, "files")

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "dwg", "dxf", "txt"}

# U-03: kiểu MIME do máy chủ quyết định theo phần mở rộng đã kiểm magic bytes, không tin Content-Type của client
MIME_BY_EXT = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "dwg": "application/acad",
    "dxf": "application/dxf",
    "txt": "text/plain; charset=utf-8",
}
SAFE_MIMES = set(MIME_BY_EXT.values())
INLINE_MIMES = {"application/pdf", "image/png", "image/jpeg"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def validate_magic_bytes(data: bytes, ext: str) -> bool:
    """Kiểm tra tính hợp lệ của phần đầu tệp (magic bytes) theo định dạng khai báo."""
    if ext == "pdf" and data.startswith(b"%PDF"):
        return True
    if ext == "png" and data.startswith(b"\x89PNG"):
        return True
    if ext in ("jpg", "jpeg") and data.startswith(b"\xff\xd8\xff"):
        return True
    if ext == "dwg" and data.startswith(b"AC"):
        return True
    if ext == "dxf" and (b"HEADER" in data[:1024] or b"SECTION" in data[:1024]):
        return True
    if ext == "txt":
        return True
    return False


@app.on_event("startup")
async def startup_event():
    try:
        storage_client.ensure_buckets()
    except Exception as e:
        logger.warning(f"Lỗi kiểm tra buckets khởi động: {e}")


@app.post("/api/v1/files", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    object_type: str = Form(...),
    object_id: str = Form(...),
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"loi": "Kích thước tệp vượt quá giới hạn cho phép (tối đa 20MB)"},
        )

    filename = file.filename or "unknown"
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"loi": f"Định dạng tệp không được hỗ trợ: .{ext}"},
        )

    if not validate_magic_bytes(file_bytes, ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"loi": "Nội dung tệp không khớp với phần mở rộng đã khai báo"},
        )

    file_uuid = str(uuid.uuid4())
    staging_key = f"{claims.tenant}/{file_uuid}"

    # S-02: Kiểm tra quyền truy cập object qua core.can_access (V2-08)
    # Tiền tố "draft." cho phép chủ thể tải tệp trước khi đối tượng được tạo
    # (ví dụ tạo hồ sơ một bước); quyền sở hữu vẫn được kiểm tra lại khi tạo đối tượng.
    if object_type and object_type != "generic" and not object_type.startswith("draft."):
        is_admin = "dx:platform-admin" in claims.roles or "dx:service" in claims.roles
        if not is_admin:
            async with get_db_connection(claims) as conn:
                can_acc = await conn.fetchval(
                    "SELECT core.can_access($1, $2, 'write')",
                    object_type,
                    str(object_id) if object_id else "",
                )
                if not can_acc:
                    try:
                        async with get_db_connection() as audit_conn:
                            await audit_conn.execute(
                                """
                                SELECT core.record_audit($1, $2, 'user', 'access.denied', $3, $4, $5::jsonb)
                                """,
                                claims.tenant,
                                claims.sub,
                                object_type,
                                str(object_id) if object_id else file_uuid,
                                json.dumps({
                                    "action": "upload",
                                    "reason": "unauthorized",
                                    "object_type": object_type,
                                    "object_id": str(object_id) if object_id else "",
                                }),
                            )
                    except Exception as audit_err:
                        logger.error(f"Lỗi ghi audit access.denied: {audit_err}")

                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={"loi": "Bạn không có quyền tải tệp lên đối tượng chỉ định"},
                    )

    storage_client.put_object("staging", staging_key, file_bytes, MIME_BY_EXT[ext])

    # Quét mã độc qua ClamAV INSTREAM (Fail-Closed)
    scan_status, scan_detail = clamav_client.scan_stream(file_bytes)

    if scan_status == "scan_failed":
        try:
            storage_client.delete_object("staging", staging_key)
        except Exception as e:
            logger.warning(f"Không thể xóa tệp staging sau khi kiểm dịch thất bại: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"loi": "Dịch vụ kiểm dịch tệp hiện tại không sẵn sàng", "chi_tiet": scan_detail},
            headers={"Retry-After": "10"},
        )

    if scan_status == "infected":
        quarantine_key = f"quarantine/{claims.tenant}/{file_uuid}"
        storage_client.copy_object("staging", staging_key, "staging", quarantine_key)
        storage_client.delete_object("staging", staging_key)

        await log_audit_event(
            tenant=claims.tenant,
            action="file.infected",
            actor_sub=claims.sub,
            object_type=object_type,
            object_id=object_id,
            detail={"filename": filename, "virus": scan_detail},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"loi": "Tệp chứa mã độc", "virus": scan_detail},
        )

    # Tệp an toàn: chuyển sang bucket files chính thức
    current_year = datetime.now(timezone.utc).year
    final_key = f"{claims.tenant}/{current_year}/{file_uuid}.{ext}"
    storage_client.copy_object("staging", staging_key, "files", final_key)
    storage_client.delete_object("staging", staging_key)

    file_sha256 = hashlib.sha256(file_bytes).hexdigest()

    # Ghi nhận core.files, core.audit_log và core.outbox trong cùng MỘT transaction duy nhất
    async with get_db_connection(claims) as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO core.files (id, tenant, owner_sub, object_type, object_id, object_key, sha256, size, mime, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'clean')
                """,
                uuid.UUID(file_uuid),
                claims.tenant,
                claims.sub,
                object_type or "generic",
                str(object_id) if object_id else None,
                final_key,
                file_sha256,
                file_size,
                MIME_BY_EXT[ext],
            )

    async with get_db_connection() as svc_conn:
        await svc_conn.execute(
            """
            SELECT core.record_audit($1, $2, 'user', 'file.uploaded', $3, $4, $5::jsonb)
            """,
            claims.tenant,
            claims.sub,
            object_type or "generic",
            str(object_id) if object_id else None,
            json.dumps({"file_id": file_uuid, "sha256": file_sha256, "size": file_size}),
        )

        await svc_conn.execute(
            """
            INSERT INTO core.outbox (tenant, topic, payload)
            VALUES ($1, 'file.uploaded', $2::jsonb)
            """,
            claims.tenant,
            json.dumps({"file_id": file_uuid, "sha256": file_sha256, "tenant": claims.tenant}),
        )

    return {
        "file_id": file_uuid,
        "object_key": final_key,
        "sha256": file_sha256,
        "size": file_size,
        "status": "clean",
    }


@app.get("/api/v1/files")
async def list_files(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id, tenant, owner_sub, object_key, sha256, size, mime, status
            FROM core.files
            WHERE tenant = $1
            ORDER BY created_at DESC
            LIMIT 50
            """,
            claims.tenant,
        )
    return [
        {
            "id": str(r["id"]),
            "tenant": r["tenant"],
            "object_key": r["object_key"],
            "sha256": r["sha256"],
            "size": r["size"],
            "mime": r["mime"],
            "status": r["status"],
        }
        for r in rows
    ]


@app.get("/api/v1/files/{file_id}")
async def get_file_download_url(
    file_id: str,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, tenant, owner_sub, object_type, object_id, object_key, sha256, size, mime, status
            FROM core.files
            WHERE id = $1
            """,
            uuid.UUID(file_id),
        )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"loi": "Không tìm thấy tệp hoặc không có quyền truy cập"},
        )

    # V2-08: Kiểm tra quyền truy cập: chủ tệp, platform-admin/service, hoặc core.can_access
    is_owner = (str(row["owner_sub"]) == str(claims.sub))
    is_admin = "dx:platform-admin" in claims.roles or "dx:service" in claims.roles

    has_access = is_owner or is_admin
    if not has_access:
        obj_type = row.get("object_type")
        obj_id = row.get("object_id")
        if obj_type and obj_id and obj_type != "generic":
            async with get_db_connection(claims) as conn:
                can_acc = await conn.fetchval(
                    "SELECT core.can_access($1, $2, 'read')",
                    obj_type,
                    str(obj_id),
                )
                if can_acc:
                    has_access = True

    if not has_access:
        try:
            async with get_db_connection() as audit_conn:
                await audit_conn.execute(
                    """
                    SELECT core.record_audit($1, $2, 'user', 'access.denied', $3, $4, $5::jsonb)
                    """,
                    claims.tenant or str(row["tenant"]),
                    claims.sub,
                    row.get("object_type") or "file",
                    str(row["id"]),
                    json.dumps({
                        "file_id": str(row["id"]),
                        "object_type": row.get("object_type"),
                        "object_id": str(row.get("object_id")),
                        "action": "download",
                        "reason": "unauthorized",
                    }),
                )
        except Exception as audit_err:
            logger.error(f"Lỗi ghi audit access.denied: {audit_err}")

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Bạn không có quyền truy cập hoặc tải tệp này"},
        )

    download_url = storage_client.generate_presigned_url("files", row["object_key"], expires_in=300)
    return {
        "file_id": str(row["id"]),
        "download_url": download_url,
        "sha256": row["sha256"],
        "size": row["size"],
        "mime": row["mime"],
    }


@app.get("/api/v1/files/{file_id}/download")
async def download_file(
    file_id: str,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, tenant, owner_sub, object_type, object_id, object_key, sha256, size, mime, status
            FROM core.files
            WHERE id = $1
            """,
            uuid.UUID(file_id),
        )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"loi": "Không tìm thấy tệp hoặc không có quyền truy cập"},
        )

    is_owner = (str(row["owner_sub"]) == str(claims.sub))
    is_admin = "dx:platform-admin" in claims.roles or "dx:service" in claims.roles

    has_access = is_owner or is_admin
    if not has_access:
        obj_type = row.get("object_type")
        obj_id = row.get("object_id")
        if obj_type and obj_id and obj_type != "generic":
            async with get_db_connection(claims) as conn:
                can_acc = await conn.fetchval(
                    "SELECT core.can_access($1, $2, 'read')",
                    obj_type,
                    str(obj_id),
                )
                if can_acc:
                    has_access = True

    if not has_access:
        try:
            async with get_db_connection() as audit_conn:
                await audit_conn.execute(
                    """
                    SELECT core.record_audit($1, $2, 'user', 'access.denied', $3, $4, $5::jsonb)
                    """,
                    claims.tenant or str(row["tenant"]),
                    claims.sub,
                    row.get("object_type") or "file",
                    str(row["id"]),
                    json.dumps({
                        "file_id": str(row["id"]),
                        "object_type": row.get("object_type"),
                        "object_id": str(row.get("object_id")),
                        "action": "download",
                        "reason": "unauthorized",
                    }),
                )
        except Exception as audit_err:
            logger.error(f"Lỗi ghi audit access.denied: {audit_err}")

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Bạn không có quyền truy cập hoặc tải tệp này"},
        )

    # Ghi audit log file.read khi tải tệp thành công (T-01)
    try:
        async with get_db_connection() as audit_conn:
            await audit_conn.execute(
                """
                SELECT core.record_audit($1, $2, 'user', 'file.read', $3, $4, $5::jsonb)
                """,
                claims.tenant or str(row["tenant"]),
                claims.sub,
                row.get("object_type") or "file",
                str(row["id"]),
                json.dumps({
                    "file_id": str(row["id"]),
                    "object_type": row.get("object_type"),
                    "object_id": str(row.get("object_id")),
                    "action": "download",
                    "mime": row["mime"],
                    "size": row["size"],
                }),
            )
    except Exception as audit_err:
        logger.error(f"Lỗi ghi audit file.read: {audit_err}")

    file_bytes = storage_client.get_object("files", row["object_key"])
    # U-03: chỉ trả kiểu MIME trong danh sách an toàn; chỉ hiển thị trực tiếp PDF và ảnh
    mime = row["mime"] if row["mime"] in SAFE_MIMES else "application/octet-stream"
    disposition = "inline" if mime in INLINE_MIMES else "attachment"
    filename = re.sub(r"[^A-Za-z0-9._-]", "_", row["object_key"].split("/")[-1])[:100] or "tep"
    return Response(
        content=file_bytes,
        media_type=mime,
        headers={
            "Content-Disposition": f"{disposition}; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )

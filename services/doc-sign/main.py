# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import io
import json
import hashlib
import uuid
import secrets
import logging
import os
import re
import asyncio
import html
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException, status, UploadFile, File, Request, Response, Query
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import qrcode
import pkcs11
from asn1crypto import pem, x509
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import pkcs11 as pyhanko_pkcs11
from pyhanko.sign import signers
from pyhanko.sign.fields import SigSeedSubFilter
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.db import get_db_connection
from dxos_core.storage import storage_client
from dxos_core.openbao import openbao_client
from dxos_core.audit import log_audit_event
from dxos_core.config import settings

app = FastAPI(title="DX-OS Doc Sign & Public Verification Service", version="1.0.0")
setup_standard_service(app, "doc-sign")
logger = logging.getLogger("doc-sign")


def _find_softhsm_lib() -> str:
    candidates = [
        settings.softhsm_lib,
        "/usr/lib/softhsm/libsofthsm2.so",
        "/usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    raise RuntimeError("Không tìm thấy libsofthsm2.so")


def _pades_sign(pdf_bytes: bytes) -> bytes:
    """Ký PAdES bằng khóa trong SoftHSM/PKCS#11."""
    lib = pkcs11.lib(_find_softhsm_lib())
    token = lib.get_token(token_label=settings.softhsm_token)
    session = token.open(user_pin=settings.softhsm_pin)
    try:
        signer = pyhanko_pkcs11.PKCS11Signer(
            pkcs11_session=session,
            cert_label=settings.softhsm_cert_label,
            key_label=settings.softhsm_key_label,
        )
        writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
        output = io.BytesIO()
        signers.sign_pdf(
            writer,
            signers.PdfSignatureMetadata(
                field_name="Signature1",
                reason="DX-OS demo",
                location="Viet Nam",
                subfilter=SigSeedSubFilter.PADES,
            ),
            signer,
            output=output,
        )
        return output.getvalue()
    finally:
        session.close()


def _pades_verify(pdf_bytes: bytes) -> bool:
    """Xác minh chữ ký PAdES với test CA."""
    ca_path = settings.test_ca_cert
    if not os.path.exists(ca_path):
        return False
    try:
        with open(ca_path, "rb") as fh:
            raw = fh.read()
        if pem.detect(raw):
            _, _, der = pem.unarmor(raw)
        else:
            der = raw
        trust_root = x509.Certificate.load(der)
        vc = ValidationContext(trust_roots=[trust_root])
        reader = PdfFileReader(io.BytesIO(pdf_bytes))
        if not reader.embedded_signatures:
            return False
        result = validate_pdf_signature(
            reader.embedded_signatures[0],
            signer_validation_context=vc,
        )
        return bool(result.bottom_line and result.trusted)
    except Exception as exc:
        logger.warning("PAdES verify lỗi: %s", exc)
        return False


@app.get("/health", tags=["Giám sát"])
async def doc_sign_health():
    """Kiểm tra sức khỏe dịch vụ và báo cáo trạng thái KMS OpenBao (R-01)."""
    from dxos_core.db import check_db_health
    db_ok = await check_db_health()
    kms_stat = openbao_client.get_status()
    kms_status = kms_stat.get("status", "unknown")
    content = {
        "status": "healthy" if db_ok else "unhealthy",
        "service": "doc-sign",
        "db": "ok" if db_ok else "unhealthy",
        "kms_status": kms_status,
        "kms": kms_stat,
        "signing_mode": settings.signing_mode,
    }
    status_code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=content)


class SignRequest(BaseModel):
    doc_type: str
    template_name: Optional[str] = None
    data: Dict[str, Any]
    # Đối tượng nghiệp vụ mà văn bản thuộc về; quyền tải bản gốc kiểm theo đối tượng này (U-01)
    object_type: Optional[str] = None
    object_id: Optional[str] = None


def _sign_algorithm() -> str:
    """Tên thuật toán lưu cùng văn bản để trang tra cứu và chi tiết hồ sơ hiển thị đúng."""
    return "PAdES (PKCS#11)" if settings.signing_mode == "pkcs11" else "Ed25519"


class RevokeRequest(BaseModel):
    ly_do: str


def generate_document_pdf(public_code: str, doc_type: str, data: Dict[str, Any]) -> bytes:
    """Sinh tệp PDF chứa mã QR xác minh công khai và nội dung tài liệu."""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Tiêu đề
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2.0, height - 60, "CONG HOA XA HOI CHU NGHIA VIET NAM")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2.0, height - 80, "Doc lap - Tu do - Hanh phuc")
    p.line(180, height - 88, width - 180, height - 88)

    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2.0, height - 130, "VAN BAN DIEN TU")
    p.setFont("Helvetica", 10)
    p.drawCentredString(width / 2.0, height - 148, f"Ma dinh danh: {public_code}")

    # Nội dung các trường
    p.setFont("Helvetica", 11)
    y = height - 190
    p.drawString(60, y, f"Loai tai lieu: {doc_type}")
    y -= 25

    for k, v in data.items():
        if y < 150:
            break
        p.drawString(60, y, f"{k}: {v}")
        y -= 22

    # Môi trường thử nghiệm: văn bản sinh ra luôn ghi rõ không có giá trị pháp lý
    if settings.demo_mode:
        p.setFont("Helvetica-Oblique", 9)
        p.drawString(60, 60, "Van ban sinh tu moi truong thu nghiem - Khong co gia tri phap ly.")

    # Mã QR công khai dẫn tới cổng kiểm tra
    qr_url = f"{settings.public_base_url}/kiem-tra/{public_code}"
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    p.drawImage(ImageReader(img_buffer), width - 180, 50, width=110, height=110)
    p.setFont("Helvetica", 8)
    p.drawCentredString(width - 125, 40, "Quet QR de kiem tra")

    p.showPage()
    p.save()
    return buffer.getvalue()


async def get_doc_sign_roles(doc_type: str, action: str = "sign") -> set:
    """Đọc cấu hình vai trò được phép ký/thu hồi từ core.app_policies theo hợp đồng ứng dụng (V2-08)."""
    roles = {"dx:service", "dx:platform-admin"}
    keys_to_check = [doc_type]
    if "_" in doc_type:
        keys_to_check.append(doc_type.replace("_", "-"))

    try:
        async with get_db_connection() as conn:
            for k in keys_to_check:
                row = await conn.fetchrow(
                    """
                    SELECT policy_data
                    FROM core.app_policies
                    WHERE policy_type = 'doc_signers' AND policy_key = $1
                    LIMIT 1
                    """,
                    k,
                )
                if row and row["policy_data"]:
                    data = json.loads(row["policy_data"]) if isinstance(row["policy_data"], str) else row["policy_data"]
                    target_key = "sign_roles" if action == "sign" else "revoke_roles"
                    for r in data.get(target_key, []):
                        roles.add(r)
                    break
    except Exception as e:
        logger.warning(f"Lỗi truy vấn chính sách ký cho doc_type={doc_type}: {e}")
    return roles


@app.post("/api/v1/docs/sign", status_code=status.HTTP_201_CREATED)
async def sign_document(
    req: SignRequest,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)

    # V2-08: Kiểm tra vai trò được phép ký tài liệu theo core.app_policies
    allowed_sign_roles = await get_doc_sign_roles(req.doc_type, "sign")
    if not any(r in allowed_sign_roles for r in claims.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Bạn không có quyền ký số và phát hành văn bản điện tử"},
        )

    # Lấy tenant trực tiếp từ token, không nhận từ client request
    tenant = claims.tenant
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"loi": "Token không chứa định danh tenant hợp lệ"},
        )

    # 128 bit ngẫu nhiên, không dò được (U-01)
    public_code = _new_public_code()

    # Sinh nội dung PDF
    pdf_bytes = generate_document_pdf(public_code, req.doc_type, req.data)

    # Ký số: PAdES qua SoftHSM/PKCS#11 (khuyến nghị) hoặc OpenBao Transit legacy
    if settings.signing_mode == "pkcs11":
        pdf_bytes = await asyncio.to_thread(_pades_sign, pdf_bytes)
        signature = "pades-pkcs11"
        key_version = "PAdES"
    else:
        signature, key_version = openbao_client.sign("doc-sign", pdf_bytes)
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    # Lưu tệp PDF vào S3 bucket files
    year = datetime.now(timezone.utc).year
    doc_id = str(uuid.uuid4())
    object_key = f"{tenant}/{year}/{doc_id}.pdf"
    storage_client.put_object("files", object_key, pdf_bytes, "application/pdf")

    # Lưu bản ghi vào bảng core.signed_docs trong PostgreSQL (dxos_svc có quyền INSERT/UPDATE)
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO core.signed_docs (id, tenant, doc_type, public_code, object_key, sha256, signature, key_version,
                                          status, signer_sub, algorithm, object_type, object_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'valid', $9, $10, $11, $12)
            """,
            uuid.UUID(doc_id),
            tenant,
            req.doc_type,
            public_code,
            object_key,
            pdf_sha256,
            signature,
            str(key_version),
            claims.sub,
            _sign_algorithm(),
            req.object_type,
            str(req.object_id) if req.object_id else None,
        )

    await log_audit_event(
        tenant=tenant,
        action="doc.signed",
        actor_sub=claims.sub,
        object_type="signed_doc",
        object_id=doc_id,
        detail={"public_code": public_code, "sha256": pdf_sha256, "doc_type": req.doc_type, "key_version": key_version},
    )

    return {
        "doc_id": doc_id,
        "public_code": public_code,
        "object_key": object_key,
        "sha256": pdf_sha256,
        "signature": signature,
        "key_version": key_version,
        "status": "valid",
        "verify_url": f"{settings.public_base_url}/kiem-tra/{public_code}",
    }


@app.post("/api/v1/docs/{doc_id}/revoke")
async def revoke_document(
    doc_id: str,
    req: RevokeRequest,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)

    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, tenant, doc_type, public_code, status
            FROM core.signed_docs
            WHERE id = $1
            """,
            uuid.UUID(doc_id),
        )

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"loi": "Không tìm thấy văn bản để thu hồi"},
            )

        # V2-08: Kiểm tra vai trò thu hồi theo core.app_policies
        allowed_revoke_roles = await get_doc_sign_roles(row["doc_type"], "revoke")
        if not any(r in allowed_revoke_roles for r in claims.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"loi": "Bạn không có quyền thu hồi văn bản"},
            )

        # Kiểm tra tenant cách ly
        if "dx:platform-admin" not in claims.roles and "dx:service" not in claims.roles and row["tenant"] != claims.tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"loi": "Không thể thu hồi văn bản thuộc địa bàn/phường khác"},
            )

        pub_code = row["public_code"]
        tenant = row["tenant"]

        await conn.execute(
            """
            UPDATE core.signed_docs
            SET status = 'revoked', revoked_at = now(), revoke_reason = $1
            WHERE id = $2
            """,
            req.ly_do,
            uuid.UUID(doc_id),
        )

    await log_audit_event(
        tenant=tenant,
        action="doc.revoked",
        actor_sub=claims.sub,
        object_type="signed_doc",
        object_id=doc_id,
        detail={"public_code": pub_code, "ly_do": req.ly_do},
    )

    return {"status": "revoked", "doc_id": doc_id, "public_code": pub_code}


PUBLIC_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
# Tệp đối soát tối đa 25 MB; trang công khai không cần nhận tệp lớn hơn
VERIFY_MAX_BYTES = 25 * 1024 * 1024
# Trang công khai không chạy script; biểu mẫu đối soát gửi thẳng về chính máy chủ (U-02)
PUBLIC_PAGE_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Cache-Control": "no-store",
}
PUBLIC_PAGE_CSS = """
:root{color-scheme:dark;--nen:#0b1322;--g1:rgba(51,81,122,.6);--g2:rgba(228,184,99,.22);--g3:rgba(124,156,196,.18);
--mat:rgba(255,255,255,.08);--mat-noi:rgba(255,255,255,.14);--vien:rgba(255,255,255,.15);--vien-noi:rgba(255,255,255,.3);--vien-nhat:rgba(255,255,255,.08);
--chu:#f0f4fa;--phu:#7c9cc4;--cham:#e4b863;--cham-nen:#e4b863;--xanh:#7dd3aa;--xanh-nen:rgba(125,211,170,.14);--do:#f08a7e;--do-nen:rgba(240,138,126,.15);
--bong:0 16px 40px rgba(3,7,18,.5),inset 0 1px 0 rgba(255,255,255,.22),inset 0 -1px 0 rgba(2,6,16,.35);--em:cubic-bezier(.16,1,.3,1)}
@media (prefers-color-scheme:light){:root{color-scheme:light;--nen:#e4eaf4;--g1:rgba(124,156,196,.55);--g2:rgba(228,184,99,.35);--g3:rgba(169,196,232,.5);
--mat:rgba(255,255,255,.55);--mat-noi:rgba(255,255,255,.8);--vien:rgba(255,255,255,.75);--vien-noi:rgba(124,156,196,.6);--vien-nhat:rgba(11,19,34,.08);
--chu:#0b1322;--phu:#485d7c;--cham:#a0701e;--xanh:#187a4e;--xanh-nen:rgba(24,122,78,.1);--do:#be3c30;--do-nen:rgba(190,60,48,.1);
--bong:0 16px 40px rgba(28,46,78,.14),inset 0 1px 0 rgba(255,255,255,.9),inset 0 -1px 0 rgba(20,40,70,.08)}}
*{box-sizing:border-box}html{background:var(--nen)}
body{margin:0;min-height:100vh;color:var(--chu);font:14px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
background:radial-gradient(40rem 40rem at 12% 6%,var(--g1),transparent 70%),radial-gradient(34rem 34rem at 90% 24%,var(--g2),transparent 70%),
radial-gradient(46rem 38rem at 55% 100%,var(--g3),transparent 70%),var(--nen);background-attachment:fixed;-webkit-font-smoothing:antialiased}
header{height:72px;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:0 24px;font-weight:500;font-size:16px;background:rgba(255,255,255,.04);
border-bottom:1px solid var(--vien-nhat);-webkit-backdrop-filter:blur(20px) saturate(180%);backdrop-filter:blur(20px) saturate(180%)}
header a{color:var(--phu);font-size:14px;font-weight:400;text-decoration:none;transition:color .5s var(--em)}header a:hover{color:var(--chu)}
main{max-width:680px;margin:48px auto;padding:0 16px}
.the{background:var(--mat);border:1px solid var(--vien);border-radius:32px;padding:32px;box-shadow:var(--bong);
-webkit-backdrop-filter:blur(40px) saturate(180%);backdrop-filter:blur(40px) saturate(180%);
animation:hien .7s var(--em) backwards;transition:border-color .5s var(--em),transform .5s var(--em)}
.the:hover{border-color:var(--vien-noi);transform:translateY(-2px)}
@keyframes hien{from{opacity:0;transform:translateY(16px) scale(.985)}}
h1{font-size:24px;font-weight:600;line-height:1.3;margin:0 0 6px;letter-spacing:-.01em}h2{font-size:16px;font-weight:600;margin:0 0 4px}
p{margin:0;color:var(--phu)}
.tt{display:inline-flex;align-items:center;gap:6px;margin:20px 0 4px;padding:4px 12px;border-radius:999px;font-weight:500;font-size:13px;
animation:hien .7s .25s var(--em) backwards}
.tt::before{content:"";width:6px;height:6px;border-radius:999px;background:currentColor}
.tt.ok{color:var(--xanh);background:var(--xanh-nen)}.tt.no{color:var(--do);background:var(--do-nen)}
dl{display:grid;grid-template-columns:170px 1fr;gap:0;margin:16px 0 0}
dt,dd{padding:10px 0;border-top:1px solid var(--vien-nhat)}dt{color:var(--phu);padding-right:16px}dd{margin:0;overflow-wrap:anywhere}
#val-public-code{color:var(--cham);font-weight:600}
.doi-soat{margin-top:28px;padding-top:24px;border-top:1px solid var(--vien-nhat)}
form{display:flex;gap:12px;flex-wrap:wrap;margin-top:14px}
input[type=file],.ma-input{flex:1;min-width:220px;color:var(--chu);font:inherit;font-size:13px;border:1px solid var(--vien);border-radius:14px;padding:10px 12px;background:transparent;
transition:border-color .5s var(--em)}input[type=file]:hover,.ma-input:hover{border-color:var(--vien-noi)}
.ma-input{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.02em}
input[type=file]::file-selector-button{font:inherit;color:var(--chu);background:var(--mat-noi);border:1px solid var(--vien);border-radius:999px;padding:4px 12px;margin-right:10px;cursor:pointer}
button{font:inherit;font-weight:500;color:#060a13;background:var(--cham-nen);border:0;border-radius:999px;padding:10px 24px;cursor:pointer;
transition:transform .5s var(--em),box-shadow .5s var(--em)}
button:hover{transform:translateY(-1px);box-shadow:0 12px 32px rgba(228,184,99,.25)}
button:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--cham);outline-offset:2px}
.ket-qua{margin-top:16px;padding:12px 16px;border-radius:16px;font-size:13px}.ket-qua.ok{color:var(--xanh);background:var(--xanh-nen)}.ket-qua.no{color:var(--do);background:var(--do-nen)}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
@media (max-width:520px){main{margin:24px auto}.the{padding:24px;border-radius:24px}dl{grid-template-columns:1fr}dd{border-top:0;padding-top:0}header a{display:none}}
"""


def _public_page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    page = (
        "<!DOCTYPE html><html lang=\"vi\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{html.escape(title)}</title><style>{PUBLIC_PAGE_CSS}</style></head>"
        "<body><header><span>Tra cứu văn bản điện tử</span><a href=\"/\">Về trang cấp phép</a></header>"
        f"<main><div class=\"the\">{body}</div></main></body></html>"
    )
    return HTMLResponse(content=page, status_code=status_code, headers=PUBLIC_PAGE_HEADERS)


def _not_found(is_html: bool):
    if is_html:
        return _public_page(
            "Không tìm thấy văn bản",
            "<h1>Không tìm thấy văn bản</h1><p>Mã tra cứu không đúng hoặc văn bản không tồn tại. "
            "Kiểm tra lại mã in trên văn bản hoặc quét lại mã QR.</p>",
            status.HTTP_404_NOT_FOUND,
        )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"trang_thai": "Khong_ton_tai", "thong_bao": "Không tìm thấy văn bản trong hệ thống"},
        headers=PUBLIC_PAGE_HEADERS,
    )


def _signature_type(row) -> str:
    return "pades" if (row["signature"] or "").startswith("pades") else "openbao"


def _algorithm_label(row) -> str:
    """Nhãn chữ ký số; văn bản cũ chưa có cột algorithm thì suy ra từ kiểu chữ ký."""
    if _signature_type(row) == "pades":
        return row["algorithm"] or "PAdES (PKCS#11)"
    return f"{row['algorithm'] or 'Ed25519'}, khóa phiên bản {row['key_version']}"


def _verify_form(code: str, ket_qua: str = "") -> str:
    return (
        "<div class=\"doi-soat\"><h2>Đối soát tệp PDF</h2>"
        "<p>Nếu bạn đang giữ bản PDF của văn bản này, tải lên để kiểm tra mã băm SHA-256 và chữ ký số. "
        "Tệp chỉ dùng để so khớp, không được lưu lại.</p>"
        f"<form method=\"post\" action=\"/kiem-tra/{code}/verify-file\" enctype=\"multipart/form-data\">"
        "<input id=\"verify-file\" name=\"file\" type=\"file\" accept=\"application/pdf\" required>"
        "<button type=\"submit\" id=\"btn-verify-file\">Kiểm tra tệp</button></form>"
        f"{ket_qua}</div>"
    )


def _result_body(row, ket_qua: str = "") -> str:
    e = html.escape
    is_valid = row["status"] == "valid"
    issued = row["issued_at"]
    issued_str = issued.strftime("%d/%m/%Y") if hasattr(issued, "strftime") else str(issued)
    revoked = ""
    if not is_valid and row["revoked_at"] is not None:
        revoked = f"<dt>Ngày thu hồi</dt><dd>{e(row['revoked_at'].strftime('%d/%m/%Y'))}</dd>"
    code = e(row["public_code"])
    return (
        "<h1>Kết quả xác minh</h1>"
        "<p>Thông tin dưới đây do hệ thống ký số của đơn vị ban hành cung cấp, không chứa dữ liệu cá nhân.</p>"
        f"<span class=\"tt {'ok' if is_valid else 'no'}\">{'Hợp lệ' if is_valid else 'Đã thu hồi'}</span>"
        "<dl>"
        f"<dt>Mã tra cứu</dt><dd id=\"val-public-code\">{code}</dd>"
        f"<dt>Loại văn bản</dt><dd>{e(str(row['doc_type']))}</dd>"
        f"<dt>Đơn vị ban hành</dt><dd>{e(str(row['tenant']))}</dd>"
        f"<dt>Ngày ký</dt><dd>{e(issued_str)}</dd>{revoked}"
        f"<dt>Chữ ký số</dt><dd>{e(_algorithm_label(row))}</dd>"
        f"<dt>Mã băm SHA-256</dt><dd>{e(str(row['sha256']))}</dd>"
        "</dl>"
        + _verify_form(code, ket_qua)
    )


PUBLIC_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _new_public_code() -> str:
    """Mã không dùng I, O, 0, 1 để tránh nhầm khi đọc/QR."""
    return "DOC-" + "".join(secrets.choice(PUBLIC_CODE_ALPHABET) for _ in range(24))


def _ma_tra_cuu_sach(code: str) -> str:
    """Bỏ khoảng trắng; giữ nguyên chữ hoa/thường vì mã cũ phân biệt."""
    return re.sub(r"\s+", "", str(code or ""))


async def _fetch_public_row(public_code: str):
    code = _ma_tra_cuu_sach(public_code)
    ung_vien = [code]
    # Người dùng hay nhầm l/I với 1; thử thêm biến thể nhưng luôn ưu tiên mã gốc.
    for a, b in (("l", "1"), ("I", "1"), ("1", "l"), ("1", "I")):
        if a in code:
            ung_vien.append(code.replace(a, b))
    async with get_db_connection() as conn:
        for ma in dict.fromkeys(ung_vien):
            row = await conn.fetchrow(
                """
                SELECT public_code, doc_type, tenant, status, issued_at, revoked_at, sha256, signature, key_version, algorithm
                FROM core.signed_docs
                WHERE public_code = $1
                """,
                ma,
            )
            if row:
                return row
    return None


@app.get("/kiem-tra/")
async def public_landing():
    """Landing tra cứu công khai, có form nhập mã (B-UX-02)."""
    vi_du = ""
    try:
        async with get_db_connection() as conn:
            row = await conn.fetchrow(
                "SELECT public_code FROM core.signed_docs WHERE status = 'valid' ORDER BY issued_at DESC LIMIT 1"
            )
        if row:
            vi_du = row["public_code"]
    except Exception:
        vi_du = ""
    vi_du_html = (
        f'<p>Ví dụ: <a href="/kiem-tra/{html.escape(vi_du)}"><code>{html.escape(vi_du)}</code></a></p>'
        if vi_du
        else ""
    )
    body = (
        "<h1>Tra cứu văn bản điện tử</h1>"
        "<p>Nhập mã in trên văn bản hoặc quét mã QR để xem trạng thái, chữ ký số và đối soát tệp PDF.</p>"
        '<form method="get" action="/kiem-tra/tra">'
        '<input id="ma-tra-cuu" name="ma" type="text" class="ma-input" '
        'placeholder="DOC-XXXXXXXX" autocomplete="off" required autofocus>'
        '<button type="submit">Tra cứu</button></form>'
        f"{vi_du_html}"
        "<p>Hệ thống không yêu cầu đăng nhập và không hiển thị dữ liệu cá nhân.</p>"
    )
    return _public_page("Tra cứu văn bản điện tử", body)


@app.get("/kiem-tra/tra")
async def public_lookup_redirect(ma: str = Query(default="")):
    code = _ma_tra_cuu_sach(ma)
    if not code:
        return RedirectResponse("/kiem-tra/", status_code=status.HTTP_303_SEE_OTHER)
    from urllib.parse import quote

    return RedirectResponse(f"/kiem-tra/{quote(code, safe='')}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/kiem-tra/{public_code}")
async def public_check(public_code: str, request: Request):
    """
    Trang tra cứu công khai (không cần đăng nhập).
    Chỉ trả thông tin xác thực văn bản, không có dữ liệu cá nhân và không cho tải bản gốc (U-01).
    Mọi giá trị đưa vào HTML đều được escape, trang không chạy script (U-02).
    """
    is_html_request = "text/html" in request.headers.get("accept", "").lower()
    public_code = _ma_tra_cuu_sach(public_code)
    if not PUBLIC_CODE_RE.fullmatch(public_code or ""):
        return _not_found(is_html_request)
    row = await _fetch_public_row(public_code)
    if not row:
        return _not_found(is_html_request)

    if is_html_request:
        return _public_page(f"Xác minh văn bản {row['public_code']}", _result_body(row))

    is_valid = row["status"] == "valid"
    issued = row["issued_at"]
    return JSONResponse(
        headers=PUBLIC_PAGE_HEADERS,
        content={
            "public_code": row["public_code"],
            "doc_type": row["doc_type"],
            "tenant": row["tenant"],
            "trang_thai": "Hop_le" if is_valid else "Da_thu_hoi",
            "issued_at": issued.isoformat() if hasattr(issued, "isoformat") else str(issued),
            "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] is not None else None,
            "sha256": row["sha256"],
            "algorithm": row["algorithm"] or ("PAdES (PKCS#11)" if _signature_type(row) == "pades" else "Ed25519"),
            "key_version": str(row["key_version"]),
            "signature_type": _signature_type(row),
        },
    )


@app.get("/api/v1/docs/{doc_id}/download")
async def download_signed_document(doc_id: str, authorization: str = Header(...)):
    """
    Tải bản gốc văn bản đã ký (U-01). Bắt buộc JWT; quyền đọc theo đối tượng gắn với văn bản
    (core.can_access, ủy quyền cho hàm của app), cùng địa bàn, có ghi audit.
    """
    claims = verify_jwt_token(authorization)
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"loi": "Không tìm thấy văn bản"})

    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, tenant, public_code, object_key, object_type, object_id, status, signer_sub FROM core.signed_docs WHERE id = $1",
            doc_uuid,
        )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"loi": "Không tìm thấy văn bản"})
    is_admin = "dx:platform-admin" in claims.roles
    allowed = False
    if is_admin or row["tenant"] == claims.tenant:
        if is_admin:
            allowed = True
        elif row["signer_sub"] and row["signer_sub"] == claims.sub:
            # Người đã ký luôn tải lại được văn bản của chính mình (kể cả văn bản không gắn hồ sơ)
            allowed = True
        elif row["object_type"] and row["object_id"]:
            async with get_db_connection(claims) as uconn:
                allowed = bool(await uconn.fetchval(
                    "SELECT core.can_access($1, $2, 'read')", row["object_type"], row["object_id"]
                ))
    if not allowed:
        await log_audit_event(
            tenant=claims.tenant or row["tenant"],
            action="access.denied",
            actor_sub=claims.sub,
            object_type="signed_doc",
            object_id=str(row["id"]),
            detail={"action": "download"},
        )
        # Không tiết lộ văn bản có tồn tại hay không
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"loi": "Không tìm thấy văn bản"})

    pdf_bytes = storage_client.get_object("files", row["object_key"])
    await log_audit_event(
        tenant=row["tenant"],
        action="doc.download",
        actor_sub=claims.sub,
        object_type="signed_doc",
        object_id=str(row["id"]),
        detail={"public_code": row["public_code"], "status": row["status"]},
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{row["public_code"]}.pdf"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@app.post("/kiem-tra/{public_code}/verify-file")
async def verify_uploaded_file(
    public_code: str,
    request: Request,
    file: UploadFile = File(...),
):
    """
    Đối soát tệp PDF người dân đang giữ với mã băm và chữ ký số đã lưu (không cần đăng nhập).
    Trình duyệt gửi biểu mẫu thì nhận lại trang kết quả; gọi API thì nhận JSON.
    """
    is_html_request = "text/html" in request.headers.get("accept", "").lower()
    if not PUBLIC_CODE_RE.fullmatch(public_code or ""):
        return _not_found(is_html_request) if is_html_request else JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"valid": False, "thong_bao": "Không tìm thấy mã tài liệu để đối soát"},
        )
    row = await _fetch_public_row(public_code)
    if not row:
        return _not_found(is_html_request) if is_html_request else JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"valid": False, "thong_bao": "Không tìm thấy mã tài liệu để đối soát"},
        )

    file_bytes = await file.read(VERIFY_MAX_BYTES + 1)
    if len(file_bytes) > VERIFY_MAX_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"valid": False, "thong_bao": "Tệp quá lớn để đối soát (tối đa 25 MB)"},
        )
    computed_sha256 = hashlib.sha256(file_bytes).hexdigest()

    hash_match = computed_sha256 == row["sha256"]
    signature_type = _signature_type(row)
    if signature_type == "pades":
        signature_valid = await asyncio.to_thread(_pades_verify, file_bytes)
    else:
        signature_valid = openbao_client.verify("doc-sign", file_bytes, row["signature"])

    is_valid = hash_match and signature_valid and (row["status"] == "valid")
    thong_bao = "Tài liệu hợp lệ" if is_valid else "Tài liệu không hợp lệ hoặc đã bị chỉnh sửa!"

    if is_html_request:
        chi_tiet = (
            f"Mã băm SHA-256 {'khớp' if hash_match else 'không khớp'}, "
            f"chữ ký số {'hợp lệ' if signature_valid else 'không hợp lệ'}"
            + ("" if row["status"] == "valid" else ", văn bản đã bị thu hồi")
        )
        ket_qua = (
            f"<div class=\"ket-qua {'ok' if is_valid else 'no'}\" id=\"verify-result\">"
            f"{'Tệp khớp với văn bản đã ký.' if is_valid else 'Tệp không khớp với văn bản đã ký.'} {html.escape(chi_tiet)}.</div>"
        )
        return _public_page(f"Đối soát văn bản {row['public_code']}", _result_body(row, ket_qua))

    return {
        "valid": is_valid,
        "signature_type": signature_type,
        "trang_thai_tai_lieu": row["status"],
        "hash_match": hash_match,
        "signature_valid": signature_valid,
        "computed_sha256": computed_sha256,
        "stored_sha256": row["sha256"],
        "thong_bao": thong_bao,
    }

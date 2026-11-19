# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-DATA-03: xuất Excel/PDF có kiểm soát quyền và ghi audit."""

import io
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from dxos_core.audit import log_audit_event
from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

from construction.deps import la_auditor, yeu_cau_can_bo

router = APIRouter(prefix="/api/v1/export", tags=["Xuất báo cáo"])


def _khong_dau(text: str) -> str:
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii")


def _xlsx_response(wb: Workbook, filename: str) -> StreamingResponse:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _style_header(ws) -> None:
    fill = PatternFill("solid", fgColor="0F2A43")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
    ws.freeze_panes = "A2"


@router.get("/dossiers.xlsx")
async def xuat_ho_so(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT ma_ho_so, ho_ten, cccd, dia_chi_cong_trinh, thua_dat, so_tang,
                   dien_tich_san_m2, trang_thai, buoc, created_at, han_tong_at, qua_han,
                   doi_tuong, loai_cong_trinh, cap_cong_trinh, ma_dinh_danh_dia_diem
            FROM app_cap_phep.ho_so
            WHERE tenant = core.jwt_tenant()
            ORDER BY created_at DESC
            LIMIT 5000
            """
        )
    wb = Workbook()
    ws = wb.active
    ws.title = "Ho so"
    headers = [
        "Mã hồ sơ", "Chủ đầu tư", "CCCD", "Địa chỉ", "Thửa đất", "Số tầng",
        "Diện tích sàn", "Trạng thái", "Bước", "Ngày tạo", "Hạn", "Quá hạn",
        "Đối tượng", "Loại công trình", "Cấp công trình", "Mã định danh địa điểm",
    ]
    ws.append(headers)
    for r in rows:
        ws.append([
            r["ma_ho_so"], r["ho_ten"], r["cccd"], r["dia_chi_cong_trinh"], r["thua_dat"],
            r["so_tang"], r["dien_tich_san_m2"], r["trang_thai"], r["buoc"],
            r["created_at"].isoformat() if r["created_at"] else "",
            r["han_tong_at"].isoformat() if r["han_tong_at"] else "",
            "Có" if r["qua_han"] else "Không",
            r["doi_tuong"], r["loai_cong_trinh"], r["cap_cong_trinh"] or "",
            r["ma_dinh_danh_dia_diem"] or "",
        ])
    _style_header(ws)
    for col, width in zip("ABCDEFGHIJKLMNOP", [16, 24, 14, 34, 18, 9, 13, 14, 14, 20, 20, 9, 18, 18, 12, 18]):
        ws.column_dimensions[col].width = width

    await log_audit_event(
        tenant=claims.tenant,
        action="export.dossiers",
        actor_sub=claims.sub,
        object_type="export",
        object_id="dossiers.xlsx",
        detail={"so_dong": len(rows)},
    )
    return _xlsx_response(wb, f"ho-so-{claims.tenant}-{datetime.now(timezone.utc):%Y%m%d}.xlsx")


@router.get("/audit.xlsx")
async def xuat_audit(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    if not la_auditor(claims):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"loi": "Chỉ kiểm toán viên được xuất nhật ký kiểm toán"})
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id, at, actor_sub, actor_type, action, object_type, object_id,
                   detail, prev_hash, hash
            FROM core.audit_log
            WHERE tenant = core.jwt_tenant()
            ORDER BY id DESC
            LIMIT 5000
            """
        )
    wb = Workbook()
    ws = wb.active
    ws.title = "Audit"
    ws.append(["ID", "Thời gian", "Người thực hiện", "Loại", "Hành động", "Đối tượng", "Mã đối tượng", "Chi tiết", "Hash trước", "Hash"])
    for r in rows:
        ws.append([
            r["id"],
            r["at"].isoformat() if r["at"] else "",
            r["actor_sub"] or "",
            r["actor_type"],
            r["action"],
            r["object_type"] or "",
            r["object_id"] or "",
            str(r["detail"]),
            bytes(r["prev_hash"]).hex() if r["prev_hash"] else "",
            bytes(r["hash"]).hex() if r["hash"] else "",
        ])
    _style_header(ws)
    for col, width in zip("ABCDEFGHIJ", [10, 24, 28, 10, 28, 16, 30, 50, 20, 20]):
        ws.column_dimensions[col].width = width

    await log_audit_event(
        tenant=claims.tenant,
        action="export.audit",
        actor_sub=claims.sub,
        object_type="export",
        object_id="audit.xlsx",
        detail={"so_dong": len(rows)},
    )
    return _xlsx_response(wb, f"audit-{claims.tenant}-{datetime.now(timezone.utc):%Y%m%d}.xlsx")


@router.get("/metrics.pdf")
async def xuat_metrics_pdf(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    yeu_cau_can_bo(claims)
    async with get_db_connection(claims) as conn:
        tong = await conn.fetchval("SELECT count(*) FROM app_cap_phep.ho_so WHERE tenant = core.jwt_tenant()")
        theo_trang_thai = await conn.fetch(
            """
            SELECT trang_thai, count(*) AS so_luong
            FROM app_cap_phep.ho_so
            WHERE tenant = core.jwt_tenant()
            GROUP BY trang_thai
            ORDER BY so_luong DESC
            """
        )
        quy_hoach_fail = await conn.fetchval(
            """
            SELECT count(*) FROM app_construction.ket_qua_kiem_tra_quy_hoach
            WHERE tenant = core.jwt_tenant() AND pass = false
            """
        )
        nghiem_thu = await conn.fetch(
            """
            SELECT loai_moc, ket_qua, count(*) AS so_luong
            FROM app_construction.moc_nghiem_thu
            WHERE tenant = core.jwt_tenant()
            GROUP BY loai_moc, ket_qua
            ORDER BY loai_moc, ket_qua
            """
        )

    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 50
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(50, y, _khong_dau("BAO CAO TONG HOP CAP PHEP XAY DUNG"))
    y -= 22
    pdf.setFont("Helvetica", 9)
    pdf.drawString(50, y, f"Tenant: {claims.tenant} | Xuat luc: {datetime.now(timezone.utc).isoformat()}")
    y -= 28
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Tong so ho so: {tong}")
    y -= 22
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, _khong_dau("Theo trang thai"))
    y -= 16
    pdf.setFont("Helvetica", 10)
    for r in theo_trang_thai:
        pdf.drawString(60, y, f"{r['trang_thai']}: {r['so_luong']}")
        y -= 14
    y -= 10
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, f"Ho so khong dat quy hoach: {quy_hoach_fail}")
    y -= 20
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, _khong_dau("Tien do nghiem thu"))
    y -= 16
    pdf.setFont("Helvetica", 10)
    for r in nghiem_thu:
        pdf.drawString(60, y, f"{r['loai_moc']} / {r['ket_qua']}: {r['so_luong']}")
        y -= 14
    pdf.showPage()
    pdf.save()
    buf.seek(0)

    await log_audit_event(
        tenant=claims.tenant,
        action="export.metrics",
        actor_sub=claims.sub,
        object_type="export",
        object_id="metrics.pdf",
        detail={"tong_ho_so": tong, "quy_hoach_fail": quy_hoach_fail},
    )
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="metrics-{claims.tenant}.pdf"'},
    )

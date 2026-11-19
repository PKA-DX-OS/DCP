# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
API kích hoạt xuất kho ấm (C05). Chỉ quản trị viên hoặc dịch vụ được gọi.

- POST /api/v1/export-warm/run?month=YYYY-MM[&tenant=...] : chạy worker, trả báo cáo
"""

from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException, Query, status

from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from worker import export_month, make_db_access, make_s3_writer, parse_month

app = FastAPI(title="DX-OS Export Warm Service", version="1.0.0")
setup_standard_service(app, "export-warm")


@app.post("/api/v1/export-warm/run")
async def run_export(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    tenant: Optional[str] = Query(None, max_length=63),
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    if not (claims.has_role("dx:platform-admin") or claims.has_role("dx:service")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"loi": "Cần vai trò quản trị hoặc dịch vụ"})

    fetch, list_tenants = await make_db_access()
    start, end = parse_month(month)
    tenants: List[str] = [tenant] if tenant else await list_tenants(start, end)
    report = await export_month(tenants, month, fetch, make_s3_writer())
    return {"month": month, "so_tenant": len(report), "report": report}
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Dịch vụ Track A — lõi nghiệp vụ xây dựng (quy hoạch, nghiệm thu, pháp lý)."""

import importlib
import pkgutil
import logging

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dxos_core.db import check_db_health
from dxos_core.middleware import setup_standard_service

from construction.dh import LoiDH

logger = logging.getLogger("dxos.construction")

app = FastAPI(title="DX-OS Construction Core API", version="1.0.0")
setup_standard_service(app, "construction")


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(_request, exc: RequestValidationError):
    """Lỗi validation trả đúng hợp đồng: {code: 'VALIDATION_ERROR', message, details: {fields: [...]}}."""
    fields = []
    for err in exc.errors():
        loc = err.get("loc", ())
        field_name = ".".join(str(x) for x in loc[1:]) if len(loc) > 1 else ".".join(str(x) for x in loc)
        fields.append({
            "field": field_name,
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        })
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Dữ liệu không hợp lệ",
            "details": {"fields": fields},
        },
    )


@app.exception_handler(LoiDH)
async def _loi_dh(_request, exc: LoiDH):
    """API Track D trả lỗi đúng hợp đồng contracts/dh: {code, message, details}."""
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.get("/ready", tags=["Giám sát"])
async def ready():
    if not await check_db_health():
        return JSONResponse(status_code=503, content={"status": "not_ready", "service": "construction"})
    return {"status": "ready", "service": "construction"}


def _include_routers() -> None:
    """Tự phát hiện router trong construction/routers để thêm file không phải sửa main."""
    from construction import routers as routers_pkg
    for mod in sorted(pkgutil.iter_modules(routers_pkg.__path__), key=lambda m: m.name):
        if mod.name.startswith("_"):
            continue
        module = importlib.import_module(f"construction.routers.{mod.name}")
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
            logger.info("Đã nạp router construction.routers.%s", mod.name)


_include_routers()

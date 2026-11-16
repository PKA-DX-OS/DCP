# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import time
import uuid
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

HTTP_REQUESTS_TOTAL = Counter(
    "dxos_http_requests_total",
    "Tổng số lượng HTTP requests",
    ["service", "method", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "dxos_http_request_duration_seconds",
    "Thời gian xử lý HTTP request",
    ["service", "method"],
)


def setup_standard_service(app: FastAPI, service_name: str):
    """
    Cài đặt middleware tiêu chuẩn cho một dịch vụ mỏng:
    - X-Request-ID
    - Prometheus /metrics
    - /health endpoint
    """
    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = req_id
        start_time = time.time()

        try:
            response: Response = await call_next(request)
        except HTTPException as he:
            HTTP_REQUESTS_TOTAL.labels(service=service_name, method=request.method, status_code=str(he.status_code)).inc()
            headers = {"X-Request-ID": req_id}
            if he.headers:
                headers.update(he.headers)
            return JSONResponse(
                status_code=he.status_code,
                content={"loi": he.detail, "request_id": req_id},
                headers=headers,
            )
        except Exception as e:
            HTTP_REQUESTS_TOTAL.labels(service=service_name, method=request.method, status_code="500").inc()
            return JSONResponse(
                status_code=500,
                content={"loi": "Lỗi nội bộ hệ thống", "chi_tiet": str(e), "request_id": req_id},
                headers={"X-Request-ID": req_id},
            )

        duration = time.time() - start_time
        HTTP_REQUESTS_TOTAL.labels(service=service_name, method=request.method, status_code=str(response.status_code)).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(service=service_name, method=request.method).observe(duration)
        response.headers["X-Request-ID"] = req_id
        return response

    @app.get("/health", tags=["Giám sát"])
    async def health_check():
        from dxos_core.db import check_db_health
        is_healthy = await check_db_health()
        if not is_healthy:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "service": service_name, "error": "Cơ sở dữ liệu không thể kết nối"},
            )
        return {"status": "healthy", "service": service_name}

    @app.get("/metrics", tags=["Giám sát"])
    async def get_metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

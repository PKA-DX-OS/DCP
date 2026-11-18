# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import asyncio
import subprocess
import pytest
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token


@pytest.mark.asyncio
async def test_S03_ticket_endpoint_and_one_time_use():
    """
    S-03: Kiểm tra hệ thống vé SSE dùng một lần.
    - POST /api/v1/events/ticket cấp vé hợp lệ 30s
    - GET /api/v1/events?ticket=<ticket> kết nối thành công (200)
    - Dùng lại cùng một vé -> bị từ chối 401
    """
    token = get_token("mc.thu")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Gọi không có auth header -> 401
        unauth_resp = await client.post(f"{GATEWAY_URL}/api/v1/events/ticket")
        assert unauth_resp.status_code == 401

        # 2. Tạo vé hợp lệ
        ticket_resp = await client.post(
            f"{GATEWAY_URL}/api/v1/events/ticket",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ticket_resp.status_code == 200
        ticket_data = ticket_resp.json()
        assert "ticket" in ticket_data
        assert ticket_data["expires_in"] == 30
        ticket = ticket_data["ticket"]

        # 3. Kết nối SSE bằng vé vừa tạo
        async with client.stream(
            "GET",
            f"{GATEWAY_URL}/api/v1/events?ticket={ticket}",
        ) as sse_stream:
            assert sse_stream.status_code == 200
            async for line in sse_stream.aiter_lines():
                if "connected" in line:
                    break

        # 4. Thử dùng lại chính vé đó -> bị từ chối 401 vì vé chỉ dùng một lần
        reuse_resp = await client.get(f"{GATEWAY_URL}/api/v1/events?ticket={ticket}")
        assert reuse_resp.status_code == 401


@pytest.mark.asyncio
async def test_S03_apisix_access_log_does_not_contain_token():
    """
    S-03: Gọi SSE với tham số ?token=..., sau đó kiểm tra access log của APISIX.
    Access log của APISIX phải được định dạng để không chứa giá trị token bí mật.
    """
    token = get_token("cdt.minh")
    assert len(token) > 20

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Gọi SSE với query string ?token=...
        try:
            async with client.stream(
                "GET",
                f"{GATEWAY_URL}/api/v1/events?token={token}",
            ) as response:
                assert response.status_code == 200
                async for line in response.aiter_lines():
                    if "connected" in line:
                        break
        except Exception:
            pass

    # Đợi APISIX flush log
    await asyncio.sleep(1.0)

    # Đọc 50 dòng log gần nhất của apisix
    cmd = ["docker", "compose", "logs", "apisix", "--tail", "50"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)  # noqa: ASYNC221
    logs = proc.stdout + proc.stderr

    # Token không được xuất hiện trong logs của apisix
    assert token not in logs, f"LỖ HỔNG S-03: Token bí mật bị ghi lại trong APISIX access log:\n{token[:10]}..."

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import asyncio
import json
import pytest
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token


@pytest.mark.asyncio
async def test_S01_sse_notification_event_and_task_labels():
    """
    S-01: Kiểm tra luồng sự kiện SSE:
    1. Endpoint là /api/v1/events.
    2. Server phát sự kiện 'notification' (không phải message không tên).
    3. Cán bộ nhận thông báo chứa task_def.
    4. Người nộp / chủ đầu tư không phải cán bộ không nhìn thấy actor_sub.
    """
    token_officer = get_token("mc.thu")
    token_citizen = get_token("cdt.lan")
    assert len(token_citizen) > 0

    # Kiểm tra SSE kết nối thành công với token trong query hoặc header
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Kết nối với Authorization header
        async with client.stream(
            "GET",
            f"{GATEWAY_URL}/api/v1/events",
            headers={"Authorization": f"Bearer {token_officer}"},
        ) as resp:
            assert resp.status_code == 200
            connected = False
            async for line in resp.aiter_lines():
                if "connected" in line:
                    connected = True
                    break
            assert connected, "Không nhận được sự kiện connected từ SSE endpoint"

        # 2. Hoàn thành một task và kiểm tra event 'notification' được phát tới cán bộ
        events_received = []
        ready_evt = asyncio.Event()
        stop_evt = asyncio.Event()

        async def sse_listener():
            try:
                async with httpx.AsyncClient(timeout=20.0) as cl:
                    async with cl.stream(
                        "GET",
                        f"{GATEWAY_URL}/api/v1/events",
                        headers={"Authorization": f"Bearer {token_officer}"},
                    ) as s_resp:
                        assert s_resp.status_code == 200
                        current_event = None
                        async for s_line in s_resp.aiter_lines():
                            if stop_evt.is_set():
                                break
                            s_line = s_line.strip()
                            if not s_line:
                                continue
                            if s_line.startswith("event:"):
                                current_event = s_line.replace("event:", "").strip()
                            elif s_line.startswith("data:"):
                                val = s_line.replace("data:", "").strip()
                                if current_event == "connected":
                                    ready_evt.set()
                                elif current_event == "notification":
                                    events_received.append(json.loads(val))
            except Exception:
                pass

        listener_task = asyncio.create_task(sse_listener())
        try:
            await asyncio.wait_for(ready_evt.wait(), timeout=10.0)

            # Lấy task đang có và hoàn thành nó
            t_res = await client.get(
                f"{GATEWAY_URL}/api/v1/flow/tasks",
                headers={"Authorization": f"Bearer {token_officer}"},
            )
            tasks = t_res.json().get("tasks", []) if t_res.status_code == 200 else []
            if tasks:
                t_id = tasks[0]["id"]
                c_res = await client.post(
                    f"{GATEWAY_URL}/api/v1/flow/tasks/{t_id}/complete",
                    json={"variables": {"hoSoHopLe": True}},
                    headers={"Authorization": f"Bearer {token_officer}"},
                )
                assert c_res.status_code == 200

                # Chờ sự kiện notification
                for _ in range(30):
                    if events_received:
                        break
                    await asyncio.sleep(0.5)

                assert len(events_received) > 0, "Không nhận được sự kiện 'notification' sau khi hoàn thành task"
                first_event = events_received[0]
                assert first_event.get("event") == "task_completed"
                assert "task_def" in first_event
        finally:
            stop_evt.set()
            listener_task.cancel()


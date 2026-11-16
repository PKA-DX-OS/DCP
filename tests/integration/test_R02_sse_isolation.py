# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import asyncio
import json
import time
import pytest
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token, submit_dossier_async


async def sse_worker(username: str, received_events: list, ready_event: asyncio.Event, stop_event: asyncio.Event):
    token = get_token(username)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            async with client.stream(
                "GET",
                f"{GATEWAY_URL}/api/v1/events",
                headers={"Authorization": f"Bearer {token}"},
            ) as response:
                assert response.status_code == 200, f"SSE connection failed for {username}: {response.status_code}"
                current_event = None
                async for line in response.aiter_lines():
                    if stop_event.is_set():
                        break
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        current_event = line.replace("event:", "").strip()
                    elif line.startswith("data:"):
                        data_val = line.replace("data:", "").strip()
                        if current_event == "connected":
                            ready_event.set()
                        received_events.append({"event": current_event, "data": data_val})
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


@pytest.mark.asyncio
async def test_R02_sse_isolation_three_clients():
    """
    R-02: Mở 3 kết nối SSE:
    1. cdt.lan: Chủ đầu tư phường A (không sở hữu hồ sơ này)
    2. td.binh: Cán bộ thẩm định phường A
    3. td.phuongb: Cán bộ phường B
    Hoàn thành nhiệm vụ ở phường A.
    Kỳ vọng:
    - Chỉ cán bộ phường A nhận sự kiện task_completed.
    - Hai kết nối còn lại chỉ nhận connected / ping (không nhận task_completed).
    """
    # 1. Tạo một hồ sơ mới thuộc cdt.minh ở phường A và bắt đầu quy trình
    cdt_token = get_token("cdt.minh")
    mc_token = get_token("mc.thu")
    unique_suffix = f"R02_{int(time.time())}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await submit_dossier_async(client, cdt_token, {
                "ho_ten": f"Tran Van R02 {unique_suffix}",
                "cccd": "001200998877",
                "dien_thoai": "0911223344",
                "dia_chi_cong_trinh": "123 Pho SSE Phuong A",
                "thua_dat": "Thua SSE-01",
                "so_tang": 1,
                "dien_tich_san_m2": 80.0,
                "khu_quan_ly_kien_truc": True,
            }, tag_prefix="R02_sse_isolation")
        assert resp.status_code == 200, f"Nop ho so that bai: {resp.text}"
        hs_data = resp.json()
        hs_id = hs_data["id"]
        ma_hs = hs_data["ma_ho_so"]
        proc_id = hs_data.get("process_instance_id")

    if not proc_id:
        async with httpx.AsyncClient(timeout=10.0) as client:
            wf_resp = await client.post(
                f"{GATEWAY_URL}/api/v1/flow/processes/start",
                headers={"Authorization": f"Bearer {cdt_token}"},
                json={
                    "process_key": "cap-phep",
                    "business_key": ma_hs,
                    "variables": {
                        "ho_so_id": hs_id,
                        "object_id": hs_id,
                        "p_object_id": hs_id,
                        "cdt_sub": "cdt.minh",
                        "tenant": "phuong-a",
                    },
                },
            )
            assert wf_resp.status_code == 200, f"Start process that bai: {wf_resp.text}"
            proc_id = wf_resp.json()["process_id"]

    # Tìm task đầu tiên của quy trình: taskKiemTraHopLe
    task_id = None
    for _ in range(15):
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{GATEWAY_URL}/api/v1/flow/tasks",
                headers={"Authorization": f"Bearer {mc_token}"},
            )
            if r.status_code == 200:
                data = r.json()
                task_list = data.get("tasks", []) if isinstance(data, dict) else data
                for t in task_list:
                    if t.get("processInstanceId") == proc_id:
                        task_id = t["id"]
                        break
        if task_id:
            break
        await asyncio.sleep(1)

    assert task_id, f"Khong tim thay task cho process {proc_id}"

    # 2. Mở 3 kết nối SSE
    events_cdt_a = []
    events_cb_a = []
    events_cb_b = []

    ready_cdt_a = asyncio.Event()
    ready_cb_a = asyncio.Event()
    ready_cb_b = asyncio.Event()
    stop_event = asyncio.Event()

    task_cdt_a = asyncio.create_task(sse_worker("cdt.lan", events_cdt_a, ready_cdt_a, stop_event))
    task_cb_a = asyncio.create_task(sse_worker("td.binh", events_cb_a, ready_cb_a, stop_event))
    task_cb_b = asyncio.create_task(sse_worker("td.phuongb", events_cb_b, ready_cb_b, stop_event))

    # Chờ cả 3 kết nối sẵn sàng (nhận event 'connected')
    await asyncio.wait_for(
        asyncio.gather(ready_cdt_a.wait(), ready_cb_a.wait(), ready_cb_b.wait()),
        timeout=15.0,
    )
    await asyncio.sleep(0.5)

    # 3. Cán bộ một cửa phường A hoàn thành nhiệm vụ
    async with httpx.AsyncClient(timeout=10.0) as client:
        r_comp = await client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{task_id}/complete",
            headers={"Authorization": f"Bearer {mc_token}"},
            json={"variables": {"hoSoHopLe": True}},
        )
        assert r_comp.status_code == 200, f"Complete task that bai: {r_comp.text}"

    # Chờ 2 giây để SSE phát tán sự kiện
    await asyncio.sleep(2.0)

    # Dừng các kết nối SSE
    stop_event.set()
    task_cdt_a.cancel()
    task_cb_a.cancel()
    task_cb_b.cancel()
    await asyncio.gather(task_cdt_a, task_cb_a, task_cb_b, return_exceptions=True)

    # 4. Kiểm tra phân phối sự kiện
    # 4a. Cán bộ phường A (td.binh) PHẢI nhận được sự kiện task_completed
    cb_a_notifications = [
        e for e in events_cb_a
        if e.get("event") == "notification" and "task_completed" in e.get("data", "")
    ]
    assert len(cb_a_notifications) >= 1, f"Can bo phuong A phai nhan su kien task_completed, thuc te nhan: {events_cb_a}"
    cb_payload = json.loads(cb_a_notifications[0]["data"])
    assert cb_payload.get("event") == "task_completed"
    assert "actor_sub" in cb_payload, "Payload gui can bo phuong A phai chua actor_sub"

    # 4b. Cán bộ phường B (td.phuongb) KHÔNG ĐƯỢC nhận sự kiện task_completed
    cb_b_notifications = [
        e for e in events_cb_b
        if e.get("event") == "notification" and "task_completed" in e.get("data", "")
    ]
    assert len(cb_b_notifications) == 0, f"Can bo phuong B khong duoc nhan su kien cua phuong A, thuc te nhan: {events_cb_b}"

    # 4c. Chủ đầu tư cdt.lan (phường A nhưng không sở hữu hồ sơ này) KHÔNG ĐƯỢC nhận sự kiện
    cdt_a_notifications = [
        e for e in events_cdt_a
        if e.get("event") == "notification" and "task_completed" in e.get("data", "")
    ]
    assert len(cdt_a_notifications) == 0, f"Chu dau tu khong so huu ho so khong duoc nhan su kien, thuc te nhan: {events_cdt_a}"


@pytest.mark.asyncio
async def test_R02_sse_owner_delivery_without_actor_sub():
    """
    R-02 (bổ sung): Chủ sở hữu hồ sơ (cdt.minh) nhận được sự kiện,
    nhưng payload bị LOẠI BỎ trường actor_sub để bảo vệ thông tin nội bộ cán bộ.
    """
    cdt_token = get_token("cdt.minh")
    mc_token = get_token("mc.thu")
    unique_suffix = f"R02_owner_{int(time.time())}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await submit_dossier_async(client, cdt_token, {
                "ho_ten": f"Chu So Huu {unique_suffix}",
                "cccd": "001200998811",
                "dien_thoai": "0911223344",
                "dia_chi_cong_trinh": "456 Pho Chu So Huu",
                "thua_dat": "Thua SSE-02",
                "so_tang": 1,
                "dien_tich_san_m2": 90.0,
                "khu_quan_ly_kien_truc": True,
            }, tag_prefix="R02_sse_isolation")
        assert resp.status_code == 200
        hs_data = resp.json()
        hs_id = hs_data["id"]
        ma_hs = hs_data["ma_ho_so"]
        proc_id = hs_data.get("process_instance_id")

    if not proc_id:
        async with httpx.AsyncClient(timeout=10.0) as client:
            wf_resp = await client.post(
                f"{GATEWAY_URL}/api/v1/flow/processes/start",
                headers={"Authorization": f"Bearer {cdt_token}"},
                json={
                    "process_key": "cap-phep",
                    "business_key": ma_hs,
                    "variables": {
                        "ho_so_id": hs_id,
                        "object_id": hs_id,
                        "p_object_id": hs_id,
                        "cdt_sub": "cdt.minh",
                        "tenant": "phuong-a",
                    },
                },
            )
            assert wf_resp.status_code == 200
            proc_id = wf_resp.json()["process_id"]

    task_id = None
    for _ in range(15):
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{GATEWAY_URL}/api/v1/flow/tasks",
                headers={"Authorization": f"Bearer {mc_token}"},
            )
            if r.status_code == 200:
                data = r.json()
                task_list = data.get("tasks", []) if isinstance(data, dict) else data
                for t in task_list:
                    if t.get("processInstanceId") == proc_id:
                        task_id = t["id"]
                        break
        if task_id:
            break
        await asyncio.sleep(1)

    assert task_id

    events_owner = []
    ready_owner = asyncio.Event()
    stop_event = asyncio.Event()

    task_owner = asyncio.create_task(sse_worker("cdt.minh", events_owner, ready_owner, stop_event))
    await asyncio.wait_for(ready_owner.wait(), timeout=15.0)
    await asyncio.sleep(0.5)

    # Hoàn thành task
    async with httpx.AsyncClient(timeout=10.0) as client:
        r_comp = await client.post(
            f"{GATEWAY_URL}/api/v1/flow/tasks/{task_id}/complete",
            headers={"Authorization": f"Bearer {mc_token}"},
            json={"variables": {"hoSoHopLe": True}},
        )
        assert r_comp.status_code == 200

    await asyncio.sleep(2.0)
    stop_event.set()
    task_owner.cancel()
    await asyncio.gather(task_owner, return_exceptions=True)

    # Chủ sở hữu nhận được sự kiện, nhưng actor_sub bị xóa
    owner_notifications = [
        e for e in events_owner
        if e.get("event") == "notification" and "task_completed" in e.get("data", "")
    ]
    assert len(owner_notifications) >= 1, f"Chu ho so phai nhan su kien, nhan: {events_owner}"
    payload = json.loads(owner_notifications[0]["data"])
    assert payload.get("event") == "task_completed"
    assert "actor_sub" not in payload, f"actor_sub phai bi xoa khoi payload gui chu dau tu: {payload}"


# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import httpx
from tests.integration.conftest import GATEWAY_URL, get_token


def test_T05_sse_token_query_rejected():
    """
    T-05: Kiểm tra /api/v1/events từ chối token trong query string (401).
    """
    token_mc = get_token("mc.thu")
    with httpx.Client(timeout=10.0) as client:
        # Gọi trực tiếp qua URL chứa query param ?token=
        res = client.get(f"{GATEWAY_URL}/api/v1/events?token={token_mc}")
        assert res.status_code == 401, f"Kỳ vọng 401 khi truyền token qua query, nhận: {res.status_code}"
        data = res.json()
        assert "detail" in data, f"Phải có trường detail trong phản hồi lỗi: {data}"


def test_T05_sse_ticket_workflow():
    """
    T-05: Kiểm tra quy trình lấy vé một lần và kết nối SSE qua ?ticket=:
    1. POST /api/v1/events/ticket lấy vé thành công (200).
    2. GET /api/v1/events?ticket=<ticket> kết nối thành công (200).
    3. Tái sử dụng cùng vé đó bị từ chối 401 (vé một lần).
    4. Vé không hợp lệ bị từ chối 401.
    5. Header Authorization trực tiếp vẫn hoạt động bình thường (200).
    """
    token_ld = get_token("ld.hoa")

    with httpx.Client(timeout=10.0) as client:
        # 1. Xin vé SSE
        res_ticket = client.post(
            f"{GATEWAY_URL}/api/v1/events/ticket",
            headers={"Authorization": f"Bearer {token_ld}"},
        )
        assert res_ticket.status_code == 200, f"Lỗi lấy vé SSE: {res_ticket.status_code} - {res_ticket.text}"
        ticket_data = res_ticket.json()
        assert "ticket" in ticket_data
        assert ticket_data["expires_in"] == 30
        ticket = ticket_data["ticket"]

        # 2. Kết nối bằng vé
        with client.stream("GET", f"{GATEWAY_URL}/api/v1/events?ticket={ticket}") as stream_res:
            assert stream_res.status_code == 200, f"Kỳ vọng 200 khi kết nối bằng vé, nhận: {stream_res.status_code}"

        # 3. Tái sử dụng cùng vé -> 401
        res_reuse = client.get(f"{GATEWAY_URL}/api/v1/events?ticket={ticket}")
        assert res_reuse.status_code == 401, f"Kỳ vọng 401 khi tái sử dụng vé, nhận: {res_reuse.status_code}"

        # 4. Vé sai / giả mạo -> 401
        res_invalid = client.get(f"{GATEWAY_URL}/api/v1/events?ticket=fake-ticket-1234567890")
        assert res_invalid.status_code == 401, f"Kỳ vọng 401 với vé không hợp lệ, nhận: {res_invalid.status_code}"

        # 5. Kết nối trực tiếp bằng Authorization header -> 200
        with client.stream("GET", f"{GATEWAY_URL}/api/v1/events", headers={"Authorization": f"Bearer {token_ld}"}) as stream_auth:
            assert stream_auth.status_code == 200, f"Kỳ vọng 200 khi dùng header Authorization, nhận: {stream_auth.status_code}"

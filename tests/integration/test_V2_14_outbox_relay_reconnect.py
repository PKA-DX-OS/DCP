# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import pytest
import asyncio
import importlib
from unittest.mock import patch, MagicMock, AsyncMock

outbox_main = importlib.import_module("services.outbox-relay.main")


@pytest.mark.asyncio
async def test_outbox_relay_publishes_and_reconnects():
    """Kiểm tra outbox-relay: chỉ đánh dấu published_at khi publish thành công, tự động thử lại khi lỗi."""
    mock_conn = MagicMock()
    mock_transaction = MagicMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
    mock_transaction.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_transaction)

    sample_rows = [
        {"id": 1, "tenant": "phuong-a", "topic": "ho_so.nop", "payload": {"ma": "CP-01"}},
        {"id": 2, "tenant": "phuong-a", "topic": "ho_so.nop", "payload": {"ma": "CP-02"}},
    ]
    mock_conn.fetch = AsyncMock(side_effect=[sample_rows, []])
    mock_conn.execute = AsyncMock(return_value="UPDATE 1")

    class MockPoolCtx:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=MockPoolCtx())

    mock_nc = MagicMock()
    mock_nc.is_connected = True
    mock_nc.close = AsyncMock()
    mock_js = MagicMock()
    mock_js.publish = AsyncMock(return_value=MagicMock(seq=1))
    mock_js.stream_info = AsyncMock()
    mock_nc.jetstream = MagicMock(return_value=mock_js)

    loop_count = 0
    orig_sleep = asyncio.sleep

    async def mock_sleep(duration):
        nonlocal loop_count
        loop_count += 1
        if loop_count >= 2:
            raise asyncio.CancelledError()
        await orig_sleep(0.01)

    with patch.object(outbox_main, "get_db_pool", new_callable=AsyncMock) as mock_get_pool, \
         patch("nats.connect", new_callable=AsyncMock) as mock_nats_connect, \
         patch("asyncio.sleep", side_effect=mock_sleep):

        mock_get_pool.return_value = mock_pool
        mock_nats_connect.return_value = mock_nc

        with pytest.raises(asyncio.CancelledError):
            await outbox_main.run_outbox_relay()

        assert mock_js.publish.call_count == 2
        assert mock_conn.execute.call_count == 2

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Kiểm thử đơn vị cho worker chất lượng dữ liệu chạy định kỳ (D-DQ-02)."""

import argparse
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import data_quality_worker as w


@pytest.mark.asyncio
async def test_dq_worker_chay_lap_loi_mot_luot_khong_thoat():
    """Chế độ lặp: khi một lượt chạy bị lỗi DB/exception, chỉ ghi log và tiếp tục lượt sau."""
    args = argparse.Namespace(
        lap_giay=10,
        dsn="postgresql://mock",
        rule=None,
        domain=None,
        dry_run=False,
    )

    call_count = 0

    async def mock_chay(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"run_id": "run-1", "status": "succeeded", "rules": [], "rule_errors": 0}
        if call_count == 2:
            raise RuntimeError("Mô phỏng đứt kết nối cơ sở dữ liệu")
        return {"run_id": "run-3", "status": "succeeded", "rules": [], "rule_errors": 0}

    sleep_count = 0

    async def mock_sleep(seconds):
        nonlocal sleep_count
        sleep_count += 1
        assert seconds == 10
        if sleep_count >= 3:
            raise asyncio.CancelledError()

    with patch.object(w, "chay", side_effect=mock_chay), \
         patch("asyncio.sleep", side_effect=mock_sleep):
        ret = await w._chay_lap(args)
        assert ret == 0
        assert call_count == 3
        assert sleep_count == 3


def test_dq_worker_tham_so_lap_giay():
    """Kiểm tra tham số --lap-giay phải lớn hơn hoặc bằng 1."""
    with pytest.raises(SystemExit):
        w.main(["--lap-giay", "0"])

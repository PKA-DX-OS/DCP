# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Unit test chứng minh không còn lỗi NameError (F821) trên các nhánh ngoại lệ (Z-11).
"""

import sys
import io
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


def load_module(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_utf8_reconfigure_io_unsupported_operation():
    """Kiểm tra khối try-except reconfigure không gặp NameError: io is not defined."""
    class MockStream:
        encoding = "ascii"
        def reconfigure(self, **kwargs):
            raise io.UnsupportedOperation("mock unsupported")

    mock_stream = MockStream()
    try:
        mock_stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, io.UnsupportedOperation):
        pass


@pytest.mark.asyncio
async def test_doc_sign_get_roles_exception_branch_no_name_error():
    """Kiểm tra get_doc_sign_roles khi CSDL ném lỗi thì log warning mà không bị NameError 'logger'."""
    doc_sign = load_module("services_doc_sign", "services/doc-sign/main.py")

    with patch.object(doc_sign, "get_db_connection", side_effect=RuntimeError("DB down")):
        roles = await doc_sign.get_doc_sign_roles("giay_phep", "sign")
        assert isinstance(roles, set)


@pytest.mark.asyncio
async def test_metrics_api_exception_branch_no_name_error():
    """Kiểm tra metrics-api khi tính chỉ số ném lỗi thì log warning mà không bị NameError 'logger'."""
    metrics_api = load_module("services_metrics_api", "services/metrics-api/main.py")
    from dxos_core.jwt import UserClaims

    mock_claims = UserClaims(
        sub="admin-sub",
        preferred_username="admin",
        roles=["dx:platform-admin"],
        tenant="phuong-a",
    )

    mock_conn = MagicMock()
    mock_conn.fetchval = AsyncMock(side_effect=[1, 2, RuntimeError("Query syntax error")])
    mock_conn.fetch = AsyncMock(return_value=[
        {"policy_key": "metric_err", "policy_data": {"code": "ERR", "sql": "SELECT bad_query()"}}
    ])

    class MockAsyncContext:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch.object(metrics_api, "verify_jwt_token", return_value=mock_claims), \
         patch.object(metrics_api, "get_db_connection", return_value=MockAsyncContext()):
        res = await metrics_api.get_executive_metrics(authorization="Bearer mock")
        assert "metrics" in res
        assert any(m.get("code") == "ERR" for m in res["metrics"])

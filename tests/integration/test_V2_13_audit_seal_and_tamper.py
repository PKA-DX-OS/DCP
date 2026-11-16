# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
from dxos_core.jwt import UserClaims
from services.audit.main import seal_audit_head


@pytest.mark.asyncio
async def test_seal_audit_head_unauthorized():
    """Người dùng không có vai trò kiểm toán hoặc admin phải bị từ chối 403."""
    user_claims = UserClaims(
        sub="user-01",
        preferred_username="user1",
        tenant="phuong-a",
        roles=["app:cap-phep:chuyen-vien"],
    )

    with patch("services.audit.main.verify_jwt_token", return_value=user_claims):
        with pytest.raises(HTTPException) as exc_info:
            await seal_audit_head("Bearer token")
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_seal_audit_head_tampered_returns_409():
    """Khi chuỗi kiểm toán bị sửa lén/sai lệch, API phải trả về 409 Conflict thay vì 503."""
    auditor_claims = UserClaims(
        sub="auditor-01",
        preferred_username="kt.an",
        tenant="phuong-a",
        roles=["dx:auditor"],
    )

    mock_invalid_verification = {
        "valid": False,
        "tampered_id": 5,
        "reason": "Mã băm không khớp tại bản ghi 5! Dữ liệu nội dung đã bị can thiệp trái phép.",
        "index": 4,
    }

    with patch("services.audit.main.verify_jwt_token", return_value=auditor_claims), \
         patch("services.audit.main.verify_audit_chain", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = mock_invalid_verification

        with pytest.raises(HTTPException) as exc_info:
            await seal_audit_head("Bearer token")

        assert exc_info.value.status_code == 409
        assert "không thể niêm phong chuỗi kiểm toán đang bị sai lệch" in exc_info.value.detail["loi"].lower()
        assert exc_info.value.detail["chi_tiet"]["tampered_id"] == 5


@pytest.mark.asyncio
async def test_seal_audit_head_valid_returns_200():
    """Khi chuỗi hợp lệ, tiến hành niêm phong S3 WORM và ghi nhận vào core.audit_seal."""
    auditor_claims = UserClaims(
        sub="auditor-01",
        preferred_username="kt.an",
        tenant="phuong-a",
        roles=["dx:auditor"],
    )

    mock_valid_verification = {
        "valid": True,
        "count": 10,
        "head_hash": "a" * 64,
        "last_id": 10,
    }

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

    class MockDbCtx:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("services.audit.main.verify_jwt_token", return_value=auditor_claims), \
         patch("services.audit.main.verify_audit_chain", new_callable=AsyncMock) as mock_verify, \
         patch("services.audit.main.storage_client") as mock_storage, \
         patch("services.audit.main.get_db_connection", return_value=MockDbCtx()):

        mock_verify.return_value = mock_valid_verification
        mock_storage.put_object = MagicMock(return_value="key")

        resp = await seal_audit_head("Bearer token")
        assert resp["status"] == "sealed"
        assert resp["tenant"] == "phuong-a"
        assert resp["last_audit_id"] == 10
        assert resp["head_hash"] == "a" * 64
        assert "phuong-a/" in resp["object_key"]
        mock_storage.put_object.assert_called_once()
        mock_conn.execute.assert_called_once()

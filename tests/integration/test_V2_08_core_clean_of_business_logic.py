# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import pytest
from .grep_utils import grep_repo
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import UploadFile
from dxos_core.jwt import UserClaims
from services.files.main import upload_file, get_file_download_url


def test_core_and_services_clean_of_business_terms():
    """Kiểm tra tĩnh: Tầng lõi core và services không chứa bất kỳ từ khóa nghiệp vụ nào."""
    pattern = r"cap\.phep|giay\.phep|cong_trinh|xay_dung|qcvn|tham-dinh|lanh-dao|mot-cua|nguoiThamDinh|taskPhanCong"
    output = grep_repo(pattern)
    assert output.strip() == "", f"Phát hiện rò rỉ nghiệp vụ vào core/services:\n{output}"


@pytest.mark.asyncio
async def test_upload_and_download_generic_file():
    """Tải lên và tải xuống tệp với object_type=generic hoạt động bình thường kể cả khi không có app nào cài đặt."""
    claims = UserClaims(
        sub="user-random-01",
        preferred_username="testuser",
        tenant="phuong-a",
        roles=["dx:standard-user"],
    )

    mock_conn = MagicMock()
    mock_transaction = MagicMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
    mock_transaction.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_transaction)
    mock_conn.execute = AsyncMock(return_value="INSERT 0 1")

    class MockDbCtx:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_upload = MagicMock(spec=UploadFile)
    mock_upload.filename = "document.pdf"
    mock_upload.content_type = "application/pdf"
    mock_upload.read = AsyncMock(return_value=b"%PDF-1.4 test generic content")

    with patch("services.files.main.verify_jwt_token", return_value=claims), \
         patch("services.files.main.storage_client") as mock_storage, \
         patch("services.files.main.clamav_client") as mock_clamav, \
         patch("services.files.main.get_db_connection", return_value=MockDbCtx()):

        mock_clamav.scan_stream.return_value = ("clean", "OK")
        mock_storage.put_object.return_value = "staging_key"
        mock_storage.copy_object.return_value = "final_key"

        res = await upload_file(
            file=mock_upload,
            object_type="generic",
            object_id="00000000-0000-0000-0000-000000000999",
            authorization="Bearer token",
        )
        assert "file_id" in res
        assert res["sha256"] != ""

        # Test download generic
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": res["file_id"],
            "tenant": "phuong-a",
            "owner_sub": "user-random-01",
            "object_type": "generic",
            "object_id": "00000000-0000-0000-0000-000000000999",
            "object_key": res["object_key"],
            "sha256": res["sha256"],
            "size": res["size"],
            "mime": "application/pdf",
            "status": "clean",
        })
        mock_storage.generate_presigned_url.return_value = "http://seaweedfs:8333/files/download-link"

        down_res = await get_file_download_url(res["file_id"], authorization="Bearer token")
        assert down_res["download_url"] == "http://seaweedfs:8333/files/download-link"

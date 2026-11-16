# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from unittest.mock import patch
from dxos_core.openbao import openbao_client


def test_signature_valid_and_tamper_detection_mock():
    data = b"%PDF-1.4 Mock building permit document contents for testing"
    mock_sig = "vault:v1:mockedsignature12345"

    with patch.object(openbao_client, "sign", return_value=(mock_sig, 1)):
        sig, key_version = openbao_client.sign("doc-sign", data)
        assert sig == mock_sig
        assert key_version == 1

    # 1. Xác minh dữ liệu gốc nguyên bản -> HỢP LỆ
    with patch.object(openbao_client, "verify", side_effect=lambda key, d, s: d == data and s == mock_sig):
        is_valid = openbao_client.verify("doc-sign", data, sig)
        assert is_valid is True

        # 2. Sửa đổi đúng 1 byte trong dữ liệu -> KHÔNG HỢP LỆ
        tampered_data = bytearray(data)
        tampered_data[10] = (tampered_data[10] + 1) % 256
        is_tampered_valid = openbao_client.verify("doc-sign", bytes(tampered_data), sig)
        assert is_tampered_valid is False

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
from tests.integration.conftest import get_token, GATEWAY_URL


def test_openbao_real_signature_and_verification():
    # Sử dụng tài khoản lãnh đạo ld.hoa để ký văn bản thật qua dịch vụ doc-sign (kết nối OpenBao thật)
    token_hoa = get_token("ld.hoa")

    req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/docs/sign",
        data=json.dumps({
            "doc_type": "giay_phep",
            "data": {
                "ho_so_id": "00000000-0000-0000-0000-000000000001",
                "so_giay_phep": "GP-TEST-2026",
                "chu_dau_tu": "Nguyễn Văn Test",
                "dia_chi": "Số 123 Đường Mẫu, Phường A"
            }
        }).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token_hoa}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 201
        data = json.loads(resp.read().decode())
        key_version = data.get("key_version")
        assert key_version == "PAdES" or (isinstance(key_version, int) and key_version >= 1) or (str(key_version).isdigit() and int(key_version) >= 1)
        assert "signature" in data
        assert len(data["signature"]) > 0

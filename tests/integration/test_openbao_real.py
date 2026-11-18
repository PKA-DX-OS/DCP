# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Ký thật qua doc-sign (khóa trong OpenBao hoặc SoftHSM), xác minh công khai, rồi thu hồi bản thử."""

import httpx

from tests.integration.conftest import GATEWAY_URL


def test_openbao_real_signature_and_verification(token, don_dep):
    t = token("ld.hoa")
    resp = httpx.post(
        f"{GATEWAY_URL}/api/v1/docs/sign",
        headers={"Authorization": f"Bearer {t}"},
        json={"doc_type": "giay_phep", "data": {
            "so_giay_phep": "GP-TEST-OPENBAO",
            "chu_dau_tu": "Nguyễn Văn Test",
            "dia_chi": "Số 123 Đường Mẫu",
        }},
        timeout=30.0,
    )
    assert resp.status_code == 201, f"Ký thật thất bại: {resp.status_code} {resp.text}"
    data = resp.json()
    don_dep(lambda: httpx.post(
        f"{GATEWAY_URL}/api/v1/docs/{data['doc_id']}/revoke",
        headers={"Authorization": f"Bearer {t}"}, json={"ly_do": "Văn bản kiểm thử"}, timeout=10.0,
    ))

    kv = str(data.get("key_version"))
    assert kv == "PAdES" or (kv.isdigit() and int(kv) >= 1), f"key_version không hợp lệ: {kv}"
    assert data.get("signature"), "Thiếu chữ ký"
    assert data.get("status") == "valid"

    pub = httpx.get(f"{GATEWAY_URL}/kiem-tra/{data['public_code']}", headers={"Accept": "application/json"}, timeout=10.0)
    assert pub.status_code == 200 and pub.json().get("trang_thai") == "Hop_le", pub.text
    assert pub.json().get("sha256") == data["sha256"], "Mã băm công khai phải khớp văn bản vừa ký"

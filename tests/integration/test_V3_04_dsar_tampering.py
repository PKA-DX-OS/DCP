# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V3-04: người dân không tự sửa trạng thái/hạn DSAR, không chèn đồng ý trực tiếp vào bảng."""

import httpx

from tests.integration.conftest import GATEWAY_URL, run_psql


def test_V3_04_citizen_cannot_patch_dsar_or_insert_consents_directly(token, don_dep):
    h = {"Authorization": f"Bearer {token('cdt.minh')}"}
    r = httpx.post(f"{GATEWAY_URL}/api/v1/rest/rpc/gui_yeu_cau_dsar", headers=h,
                   json={"p_type": "access", "p_legal_basis_note": "Kiểm thử V3-04"}, timeout=10.0)
    assert r.status_code == 200, r.text
    dsar_id = r.json()["id"]
    don_dep(lambda: run_psql(f"DELETE FROM core.dsar_requests WHERE id = '{dsar_id}';"))

    patch = httpx.patch(f"{GATEWAY_URL}/api/v1/rest/dsar_requests?id=eq.{dsar_id}", headers=h,
                        json={"status": "closed", "due_at": "2020-01-01T00:00:00Z"}, timeout=10.0)
    assert patch.status_code in (401, 403, 404, 405) or (patch.status_code in (200, 204) and not patch.content.strip(b"[]")), \
        f"Người dân PATCH được dsar_requests: HTTP {patch.status_code} {patch.text}"

    rows = httpx.get(f"{GATEWAY_URL}/api/v1/rest/dsar_requests?id=eq.{dsar_id}", headers=h, timeout=10.0).json()
    assert len(rows) == 1
    assert rows[0]["status"] == "received", f"Trạng thái DSAR bị đổi: {rows[0]['status']}"
    assert not str(rows[0]["due_at"]).startswith("2020-01-01"), f"Hạn DSAR bị đổi: {rows[0]['due_at']}"

    ins = httpx.post(f"{GATEWAY_URL}/api/v1/rest/consents", headers=h,
                     json={"purpose": "qa_v3_04", "text_version": "x"}, timeout=10.0)
    assert ins.status_code in (401, 403, 404, 405), f"Người dân chèn thẳng được consents: HTTP {ins.status_code}"

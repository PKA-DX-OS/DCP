# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""D-GOV-02: Test tích hợp quyền riêng tư DSAR xuất và xóa dữ liệu MDM."""

import uuid
import httpx
import pytest

from tests.integration._auth import GATEWAY_URL, get_token


def _h(user: str, **them) -> dict:
    return {"Authorization": f"Bearer {get_token(user)}"} | them


def test_dsar_mdm_export_va_erase():
    import subprocess
    dossier_id = "8847bab8-33ef-4847-8e3d-50420b4c602a"

    # Reset liên kết trước để đảm bảo trạng thái sạch
    subprocess.run([
        "docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c",
        f"DELETE FROM core.mdm_dossier_link WHERE dossier_id = '{dossier_id}';"
    ], capture_output=True)

    # 1. Đảm bảo hồ sơ mẫu được liên kết MDM (gọi /links với cán bộ một cửa)
    r_link = httpx.get(
        f"{GATEWAY_URL}/api/v1/mdm/dossiers/{dossier_id}/links",
        headers=_h("mc.thu"),
        timeout=20.0,
    )
    assert r_link.status_code == 200, r_link.text
    link_data = r_link.json()
    assert link_data["subject"] is not None
    subject_id = link_data["subject"]["id"]

    try:
        # Thêm 1 bản ghi external_refs để kiểm tra xuất và xóa theo retention
        subprocess.run([
            "docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c",
            f"INSERT INTO core.external_refs (tenant, entity_type, entity_id, system, external_id) "
            f"VALUES ('phuong-a', 'subject', '{subject_id}', 'csdl_dan_cu', 'EXT-TEST-001') ON CONFLICT DO NOTHING;"
        ], capture_output=True)

        # 2. Xuất dữ liệu cá nhân DSAR qua API (/api/v1/mdm/dsar/export)
        # 2.1 Cán bộ có quyền DSAR (mc.thu / ld.hoa) xuất theo so_dinh_danh
        r_exp = httpx.get(
            f"{GATEWAY_URL}/api/v1/mdm/dsar/export?so_dinh_danh=001099001234",
            headers=_h("mc.thu"),
            timeout=20.0,
        )
        assert r_exp.status_code == 200, r_exp.text
        exp_data = r_exp.json()
        assert exp_data["tenant"] == "phuong-a"
        assert exp_data["subject"]["subject_id"] == subject_id
        assert "cccd_hmac" not in r_exp.text  # Tuyệt đối không trả HMAC thô
        assert len(exp_data["dossier_links"]) >= 1
        assert len(exp_data["external_refs"]) >= 1

        # 2.2 Chủ thể tự tra cứu với số định danh của mình
        r_exp_cdt = httpx.get(
            f"{GATEWAY_URL}/api/v1/mdm/dsar/export?so_dinh_danh=001099001234",
            headers=_h("cdt.minh"),
            timeout=20.0,
        )
        assert r_exp_cdt.status_code == 200, r_exp_cdt.text
        assert r_exp_cdt.json()["subject"]["subject_id"] == subject_id

        # 3. Phân quyền: Cán bộ không có vai xuất hoặc sai phường bị chặn
        r_phuongb = httpx.get(
            f"{GATEWAY_URL}/api/v1/mdm/dsar/export?so_dinh_danh=001099001234",
            headers=_h("mc.phuongb"),
            timeout=20.0,
        )
        assert r_phuongb.status_code == 200
        assert r_phuongb.json()["subject"] is None  # Cách ly địa bàn: không tìm thấy người phường A

        # 4. Yêu cầu xóa dữ liệu MDM theo DSAR (/api/v1/mdm/dsar/erase)
        # Cán bộ không đủ vai (tt.khanh) -> 403
        r_erase_forbidden = httpx.post(
            f"{GATEWAY_URL}/api/v1/mdm/dsar/erase",
            headers=_h("tt.khanh", **{"Idempotency-Key": uuid.uuid4().hex}),
            json={"so_dinh_danh": "001099001234", "reason": "Xóa thử sai quyền"},
            timeout=20.0,
        )
        assert r_erase_forbidden.status_code == 403

        # Cán bộ xử lý DSAR hợp lệ (ld.hoa) thực hiện xóa/ẩn danh
        r_erase = httpx.post(
            f"{GATEWAY_URL}/api/v1/mdm/dsar/erase",
            headers=_h("ld.hoa", **{"Idempotency-Key": uuid.uuid4().hex}),
            json={"so_dinh_danh": "001099001234", "reason": "Người dùng yêu cầu xóa dữ liệu cá nhân theo DSAR"},
            timeout=20.0,
        )
        assert r_erase.status_code == 200, r_erase.text
        erase_data = r_erase.json()
        assert erase_data["status"] == "success"
        assert erase_data["anonymized"] is True
        assert erase_data["subject_id"] == subject_id
        assert erase_data["deleted_external_refs"] >= 1
        assert erase_data["retained_dossier_links"] >= 1

        # 5. Kiểm tra sau khi xóa:
        # Tra cứu lại bằng CCCD đó sẽ không còn tìm thấy (vì cccd_hmac đã bị ẩn danh NULL)
        r_exp_after = httpx.get(
            f"{GATEWAY_URL}/api/v1/mdm/dsar/export?so_dinh_danh=001099001234",
            headers=_h("mc.thu"),
            timeout=20.0,
        )
        assert r_exp_after.status_code == 200
        assert r_exp_after.json()["subject"] is None

    finally:
        # Dọn dẹp bản ghi test và khôi phục liên kết hồ sơ
        subprocess.run([
            "docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c",
            f"DELETE FROM core.mdm_dossier_link WHERE dossier_id = '{dossier_id}'; "
            f"DELETE FROM core.mdm_subject WHERE subject_id = '{subject_id}';"
        ], capture_output=True)
        # Nạp lại liên kết ban đầu
        httpx.get(
            f"{GATEWAY_URL}/api/v1/mdm/dossiers/{dossier_id}/links",
            headers=_h("mc.thu"),
            timeout=20.0,
        )

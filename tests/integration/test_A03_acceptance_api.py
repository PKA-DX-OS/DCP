# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-ACC-02/A-ACC-05: API nghiệm thu, biên bản, bản vẽ hoàn công."""

import httpx

from tests.integration._auth import GATEWAY_URL, get_token
from tests.integration._ho_so import make_pdf, run_sql


def _h(username: str) -> dict:
    return {"Authorization": f"Bearer {get_token(username)}"}


def _tao_ho_so() -> str:
    # Dùng hồ sơ có sẵn của phuong-a; mc.thu (một cửa) được xem toàn địa bàn.
    rows = run_sql(
        "SELECT id FROM app_cap_phep.ho_so WHERE tenant = 'phuong-a' "
        "ORDER BY created_at DESC LIMIT 1;"
    )
    assert rows, "Cần ít nhất một hồ sơ demo"
    return rows.splitlines()[0]


def test_A02_tong_quan_va_moc_nghiem_thu():
    ho_so_id = _tao_ho_so()
    resp = httpx.get(f"{GATEWAY_URL}/api/v1/acceptance/{ho_so_id}", headers=_h("mc.thu"), timeout=20.0)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ho_so"]["id"] == ho_so_id
    assert data["tien_do"]["tong"] == 4
    assert data["moc_tiep_theo"] in {"mong", "ket_cau", "hoan_thien", "hoan_cong", None}


def test_A02_mong_fail_roi_dat_va_bien_ban():
    ho_so_id = _tao_ho_so()
    fail = httpx.post(
        f"{GATEWAY_URL}/api/v1/acceptance/{ho_so_id}/milestones",
        headers=_h("mc.thu"),
        json={"loai_moc": "mong", "ket_qua": "khong_dat", "ghi_chu": "Cao độ móng sai"},
        timeout=20.0,
    )
    assert fail.status_code == 200, fail.text
    moc_id = fail.json()["id"]

    record = httpx.post(
        f"{GATEWAY_URL}/api/v1/acceptance/milestones/{moc_id}/records",
        headers=_h("mc.thu"),
        json={"so_bien_ban": f"BB-{moc_id[:6]}", "ket_luan": "Yêu cầu khắc phục", "ket_qua": "khong_dat"},
        timeout=20.0,
    )
    assert record.status_code == 200, record.text

    passed = httpx.post(
        f"{GATEWAY_URL}/api/v1/acceptance/{ho_so_id}/milestones",
        headers=_h("mc.thu"),
        json={"loai_moc": "mong", "ket_qua": "dat", "ghi_chu": "Đã khắc phục"},
        timeout=20.0,
    )
    assert passed.status_code == 200, passed.text
    assert passed.json()["version"] >= 2

    summary = httpx.get(f"{GATEWAY_URL}/api/v1/acceptance/{ho_so_id}", headers=_h("mc.thu"), timeout=20.0)
    assert summary.status_code == 200
    mong = [m for m in summary.json()["milestones"] if m["loai_moc"] == "mong"]
    assert any(m["ket_qua"] == "dat" for m in mong)
    assert any(m["bien_ban"] for m in mong)


def test_A02_ban_ve_hoan_cong_va_lich_su():
    ho_so_id = _tao_ho_so()
    # Tải tệp bằng tài khoản chủ đầu tư, sau đó cán bộ đính kèm vào bản vẽ hoàn công.
    token = get_token("cdt.minh")
    with httpx.Client(timeout=30.0) as client:
        upload = client.post(
            f"{GATEWAY_URL}/api/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("hoan-cong.pdf", make_pdf(f"asbuilt-{ho_so_id[:8]}"), "application/pdf")},
            data={"object_type": "draft.ho_so", "object_id": ho_so_id},
        )
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["file_id"]

    resp = httpx.post(
        f"{GATEWAY_URL}/api/v1/acceptance/{ho_so_id}/as-built",
        headers=_h("mc.thu"),
        json={"file_id": file_id, "ghi_chu": "Bản vẽ hoàn công đợt 1"},
        timeout=20.0,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["version"] >= 1

    hist = httpx.get(f"{GATEWAY_URL}/api/v1/acceptance/{ho_so_id}/history", headers=_h("mc.thu"), timeout=20.0)
    assert hist.status_code == 200, hist.text
    assert any(x["loai"] == "ban_ve" for x in hist.json())


def test_A02_cong_dan_khong_duoc_tao_moc():
    ho_so_id = _tao_ho_so()
    resp = httpx.post(
        f"{GATEWAY_URL}/api/v1/acceptance/{ho_so_id}/milestones",
        headers=_h("cdt.minh"),
        json={"loai_moc": "mong"},
        timeout=20.0,
    )
    assert resp.status_code == 403, resp.text

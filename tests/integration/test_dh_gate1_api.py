# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""D Gate 1: API Track D chạy qua APISIX tới DB (không còn 404), đúng vai, đúng phường, không lộ CCCD."""

import re
import uuid

import httpx

from tests.integration._auth import GATEWAY_URL, get_token


def _h(user: str, **them) -> dict:
    return {"Authorization": f"Bearer {get_token(user)}"} | them


def _get(path: str, user: str) -> httpx.Response:
    return httpx.get(f"{GATEWAY_URL}{path}", headers=_h(user), timeout=30.0)


def test_dh_cac_route_khong_con_404():
    for path, user in [
        ("/api/v1/search?q=CP", "mc.thu"),
        ("/api/v1/data-quality/summary", "ld.hoa"),
        ("/api/v1/data-quality/rules", "ld.hoa"),
        ("/api/v1/data-quality/runs", "ld.hoa"),
        ("/api/v1/data-quality/issues", "ld.hoa"),
        ("/api/v1/catalog/assets", "kt.an"),
        ("/api/v1/catalog/contracts", "kt.an"),
        ("/api/v1/lineage/jobs/dq.worker", "ld.hoa"),
        ("/api/v1/automation/metrics", "ld.hoa"),
    ]:
        r = _get(path, user)
        assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:200]}"


def test_dh_khong_token_bi_chan():
    r = httpx.get(f"{GATEWAY_URL}/api/v1/data-quality/summary", timeout=10.0)
    assert r.status_code == 401


def test_dh_360_ho_so_che_cccd_va_cach_ly_phuong(ho_so_moi):
    hs_id = ho_so_moi.get("id") or ho_so_moi.get("ho_so_id")
    r = _get(f"/api/v1/mdm/dossiers/{hs_id}/360", "mc.thu")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ho_so"]["id"] == hs_id
    assert "001099007777" not in r.text
    if body["chu_dau_tu"]:
        assert re.fullmatch(r"\d{4}\*{6}\d{2}", body["chu_dau_tu"]["cccd_mask"])
    lk = _get(f"/api/v1/mdm/dossiers/{hs_id}/links", "mc.thu")
    assert lk.status_code == 200 and lk.json()["dossier_id"] == hs_id
    khac = _get(f"/api/v1/mdm/dossiers/{hs_id}/360", "mc.phuongb")
    assert khac.status_code == 404 and khac.json()["code"] == "MDM_NOT_FOUND"


def test_dh_sai_vai_tra_loi_dung_hop_dong():
    r = _get("/api/v1/catalog/assets", "tt.khanh")
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
    r = _get("/api/v1/automation/metrics", "td.binh")
    assert r.status_code == 403
    r = httpx.post(f"{GATEWAY_URL}/api/v1/mdm/merge", headers=_h("tt.khanh", **{"Idempotency-Key": uuid.uuid4().hex}),
                   json={"entity_type": "parcel", "giu_id": str(uuid.uuid4()), "gop_ids": [str(uuid.uuid4())], "ly_do": "thử quyền"},
                   timeout=20.0)
    assert r.status_code == 403


def test_dh_tim_kiem_ma_ho_so(ho_so_moi):
    ma = ho_so_moi.get("ma_ho_so")
    r = _get(f"/api/v1/search?q={ma}&types=ho_so", "mc.thu")
    assert r.status_code == 200, r.text
    nhom = {g["type"]: g for g in r.json()["groups"]}
    assert nhom["ho_so"]["items"][0]["khop"] == "exact"


def test_dh_lineage_ho_so_va_cach_ly_phuong(ho_so_moi):
    hs_id = ho_so_moi.get("id") or ho_so_moi.get("ho_so_id")

    # 1. Kiểm tra quy hoạch
    r_plan = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/check",
        headers=_h("ld.hoa"),
        json={"ho_so_id": hs_id, "thua_dat_id": "TD-A-01", "proposal": {"so_tang": 2, "loai_dat": "dat_o"}},
        timeout=30.0,
    )
    assert r_plan.status_code == 200, r_plan.text

    # 2. Nghiệm thu mốc móng
    r_acc = httpx.post(
        f"{GATEWAY_URL}/api/v1/acceptance/{hs_id}/milestones",
        headers=_h("ld.hoa"),
        json={"loai_moc": "mong", "ket_qua": "dat"},
        timeout=30.0,
    )
    assert r_acc.status_code == 200, r_acc.text

    # 3. Tra cứu phả hệ hồ sơ bằng lãnh đạo phường A
    r_lin = _get(f"/api/v1/lineage/ho_so/{hs_id}", "ld.hoa")
    assert r_lin.status_code == 200, r_lin.text
    data = r_lin.json()
    assert data["entity_type"] == "ho_so"
    assert data["id"] == hs_id

    # Đồ thị có ít nhất 3 sự kiện (nộp hồ sơ, kiểm tra quy hoạch, nghiệm thu)
    jobs_in_edges = {e["job"] for e in data["edges"]}
    assert "ho_so.nop" in jobs_in_edges
    assert "quy_hoach.kiem_tra" in jobs_in_edges
    assert "nghiem_thu.moc" in jobs_in_edges

    # Đảm bảo không ghi lộ CCCD hoặc dữ liệu định danh trong response
    assert "001099007777" not in r_lin.text

    # 4. Cách ly địa bàn: Phường B không thấy hồ sơ của Phường A
    r_phuongb = _get(f"/api/v1/lineage/ho_so/{hs_id}", "ld.phuongb")
    assert r_phuongb.status_code == 404
    assert r_phuongb.json()["code"] == "LINEAGE_NOT_FOUND"

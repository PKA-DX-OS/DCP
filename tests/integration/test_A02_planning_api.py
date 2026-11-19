# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-PLAN-03: API quy hoạch, rule engine qua HTTP, cách ly địa bàn và audit."""

import httpx

from tests.integration._auth import GATEWAY_URL, get_token
from tests.integration._ho_so import run_sql


def _headers(username: str) -> dict:
    return {"Authorization": f"Bearer {get_token(username)}"}


def _check(username: str, body: dict) -> httpx.Response:
    return httpx.post(f"{GATEWAY_URL}/api/v1/planning/check", headers=_headers(username), json=body, timeout=30.0)


def test_A02_thua_dat_va_vung_cua_dia_ban():
    resp = httpx.get(f"{GATEWAY_URL}/api/v1/planning/parcels", headers=_headers("td.binh"), timeout=20.0)
    assert resp.status_code == 200, resp.text
    ma = {p["ma_thua_dat"] for p in resp.json()}
    assert {"TD-A-01", "TD-A-02", "TD-A-03"}.issubset(ma)
    assert "TD-B-01" not in ma

    resp = httpx.get(f"{GATEWAY_URL}/api/v1/planning/zones", headers=_headers("td.binh"), timeout=20.0)
    assert resp.status_code == 200, resp.text
    assert {z["ma_zone"] for z in resp.json()} == {"QH-A1", "QH-A2"}


def test_A02_kiem_tra_that_bai_5_tang_va_pass_3_tang():
    bad = _check("td.binh", {
        "thua_dat_id": "TD-A-01",
        "proposal": {
            "so_tang": 5, "chieu_cao_m": 16, "mat_do_xay_dung_pct": 80, "far": 2.4,
            "khoang_lui_truoc_m": 2, "khoang_lui_hong_m": 0.5, "khoang_lui_sau_m": 1.5, "loai_dat": "dat_o",
        },
    })
    assert bad.status_code == 200, bad.text
    data = bad.json()
    assert data["pass"] is False
    assert data["so_loi"] >= 5
    rules = {r["rule_id"]: r for r in data["results"]}
    for rule_id in ("R03", "R04", "R05", "R06", "R07", "R08"):
        assert rules[rule_id]["passed"] is False, rules[rule_id]
    assert rules["R04"]["citation"]["document_code"] == "47/2024/QH15"

    good = _check("td.binh", {
        "thua_dat_id": "TD-A-01",
        "proposal": {
            "so_tang": 3, "chieu_cao_m": 11, "mat_do_xay_dung_pct": 65, "far": 1.8,
            "khoang_lui_truoc_m": 3.5, "khoang_lui_hong_m": 1.2, "khoang_lui_sau_m": 1.2, "loai_dat": "dat_o",
        },
    })
    assert good.status_code == 200, good.text
    assert good.json()["pass"] is True
    assert good.json()["so_loi"] == 0


def test_A02_hanh_lang_giao_thong_bi_chan():
    resp = _check("td.binh", {
        "thua_dat_id": "TD-A-03",
        "proposal": {"so_tang": 2, "loai_dat": "dat_o"},
    })
    assert resp.status_code == 200, resp.text
    rules = {r["rule_id"]: r for r in resp.json()["results"]}
    assert rules["R01"]["passed"] is True
    assert rules["R09"]["passed"] is False


def test_A02_kiem_tra_luu_ket_qua_va_audit():
    resp = _check("td.binh", {
        "thua_dat_id": "TD-A-02",
        "proposal": {"so_tang": 2, "chieu_cao_m": 8, "loai_dat": "dat_o"},
    })
    assert resp.status_code == 200, resp.text
    ket_qua_id = resp.json()["id"]
    count = run_sql(
        "SELECT count(*) FROM app_construction.ket_qua_kiem_tra_quy_hoach "
        f"WHERE id = '{ket_qua_id}' AND tenant = 'phuong-a';"
    )
    assert int(count) == 1
    audit = run_sql(
        "SELECT count(*) FROM core.audit_log "
        "WHERE tenant = 'phuong-a' AND action = 'planning.checked' "
        f"AND detail->>'ket_qua_id' = '{ket_qua_id}';"
    )
    assert int(audit) >= 1


def test_A02_cong_dan_khong_duoc_kiem_tra_quy_hoach():
    resp = _check("cdt.minh", {"thua_dat_id": "TD-A-01", "proposal": {"so_tang": 2}})
    assert resp.status_code == 403, resp.text


def test_A02_cach_ly_dia_ban_phuong_b():
    resp = _check("td.binh", {"thua_dat_id": "TD-B-01", "proposal": {"so_tang": 2}})
    assert resp.status_code == 404, resp.text


def test_A02_tro_ly_tra_loi_co_trich_dan_phap_ly():
    token = get_token("td.binh")
    resp = httpx.post(
        f"{GATEWAY_URL}/api/v1/assistant/ask",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Vì sao hồ sơ không đạt kiểm tra quy hoạch do chiều cao?", "app": "cap-phep"},
        timeout=30.0,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("citations"), body
    assert any(c["nguon"].startswith("legal/") for c in body["citations"])

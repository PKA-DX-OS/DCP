# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-LEGAL-02..05: manifest Điều 60, severity, thẩm quyền, định danh địa điểm."""

import json
import uuid

import httpx

from tests.integration._auth import GATEWAY_URL, get_token
from tests.integration._ho_so import REQUIRED_DOC_LOAI, build_tep, run_sql


PAYLOAD = {
    "ho_ten": "Nguyễn Văn Kiểm Thử",
    "cccd": "001099009999",
    "dien_thoai": "0909999999",
    "dia_chi_cong_trinh": "Số 99 Đường Kiểm Thử, phường A",
    "thua_dat": "TD-A-01",
    "so_tang": 6,
    "dien_tich_san_m2": 600.0,
    "khu_quan_ly_kien_truc": False,
}


def _post(token: str, payload: dict, ho_so_id: str, tep: list) -> httpx.Response:
    body = dict(payload)
    body["p_ho_so_id"] = ho_so_id
    body["p_tep"] = tep
    return httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/nop_ho_so",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=60.0,
    )


def _build_docs(token: str, ho_so_id: str, loai_list: list[str]) -> list:
    with httpx.Client(timeout=60.0) as client:
        tep = build_tep(token, ho_so_id, PAYLOAD, f"A04-{ho_so_id[:8]}", client=client)
    return [t for t in tep if t["loai"] in loai_list]


def test_A04_manifest_theo_dieu_60_khong_doi_du_an_tong_mat_bang():
    rows = run_sql(
        "SELECT loai || '|' || bat_buoc || '|' || COALESCE(legal_citation_key,'') "
        "FROM app_cap_phep.document_requirements ORDER BY thu_tu;"
    )
    text = rows.lower()
    assert "quyết định phê duyệt dự án" not in text
    assert "tổng mặt bằng" not in text
    lines = {line.split("|")[0]: line for line in rows.splitlines() if line}
    assert lines["cam_ket_an_toan"].split("|")[1] == "true"
    assert lines["cam_ket_an_toan"].split("|")[2] == "ND217-D60-K3"
    assert lines["don"].split("|")[2] == "ND217-D60-K3"
    assert lines["giay_to_dat"].split("|")[2] == "ND217-D55"


def test_A04_ho_so_6_tang_600m2_khong_bi_chan():
    token = get_token("cdt.minh")
    ho_so_id = str(uuid.uuid4())
    tep = _build_docs(token, ho_so_id, REQUIRED_DOC_LOAI)
    resp = _post(token, PAYLOAD, ho_so_id, tep)
    assert resp.status_code == 200, f"Hồ sơ hợp pháp >5 tầng/>500m² không được chặn: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["status"] == "success"


def test_A04_thieu_cam_ket_an_toan_bi_chan():
    token = get_token("cdt.minh")
    ho_so_id = str(uuid.uuid4())
    loai = [x for x in REQUIRED_DOC_LOAI if x != "cam_ket_an_toan"]
    tep = _build_docs(token, ho_so_id, loai)
    resp = _post(token, PAYLOAD, ho_so_id, tep)
    assert resp.status_code == 422, resp.text
    details = json.loads(resp.json()["details"])
    assert any(x.get("loai_giay") == "cam_ket_an_toan" and x.get("severity") == "error" for x in details)


def test_A04_thieu_giay_to_dat_bi_chan():
    token = get_token("cdt.minh")
    ho_so_id = str(uuid.uuid4())
    loai = [x for x in REQUIRED_DOC_LOAI if x != "giay_to_dat"]
    tep = _build_docs(token, ho_so_id, loai)
    resp = _post(token, PAYLOAD, ho_so_id, tep)
    assert resp.status_code == 422, resp.text


def test_A04_tham_quyen_hai_cap():
    token = get_token("td.binh")
    headers = {"Authorization": f"Bearer {token}"}
    ca_nhan = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/authority/check",
        headers=headers,
        json={"loai_cong_trinh": "nha_o_rieng_le", "doi_tuong": "ho_gia_dinh_ca_nhan"},
        timeout=20.0,
    )
    assert ca_nhan.status_code == 200, ca_nhan.text
    assert ca_nhan.json()["co_quan_cap"] == "UBND cấp xã"

    to_chuc = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/authority/check",
        headers=headers,
        json={"loai_cong_trinh": "nha_o_rieng_le", "doi_tuong": "to_chuc"},
        timeout=20.0,
    )
    assert to_chuc.status_code == 200, to_chuc.text
    assert to_chuc.json()["co_quan_cap"] == "Sở Xây dựng"

    kcn = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/authority/check",
        headers=headers,
        json={"loai_cong_trinh": "cong_trinh", "doi_tuong": "to_chuc", "trong_kcn": True},
        timeout=20.0,
    )
    assert kcn.status_code == 200, kcn.text
    assert "Ban quản lý" in kcn.json()["co_quan_cap"]


def test_A04_dinh_danh_dia_diem_12_so():
    token = get_token("td.binh")
    headers = {"Authorization": f"Bearer {token}"}
    ok = httpx.get(f"{GATEWAY_URL}/api/v1/planning/location/790101000001", headers=headers, timeout=20.0)
    assert ok.status_code == 200, ok.text
    assert ok.json()["found"] is True
    assert ok.json()["can_reuse"] is True

    bad = httpx.get(f"{GATEWAY_URL}/api/v1/planning/location/123", headers=headers, timeout=20.0)
    assert bad.status_code == 422

    missing = httpx.get(f"{GATEWAY_URL}/api/v1/planning/location/799999999999", headers=headers, timeout=20.0)
    assert missing.status_code == 200
    assert missing.json()["found"] is False


def test_A04_canh_bao_va_xac_nhan_canh_bao():
    token = get_token("mc.thu")
    headers = {"Authorization": f"Bearer {token}"}
    ho_so_id = run_sql("SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so = 'CP-HERO-2026-001';")
    assert ho_so_id
    warn = httpx.get(f"{GATEWAY_URL}/api/v1/planning/validation/{ho_so_id}", headers=headers, timeout=20.0)
    assert warn.status_code == 200, warn.text
    body = warn.json()
    assert body["items"]
    assert any(x["ma"] == "dien_tich_nguong" for x in body["items"])

    confirm = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/validation/{ho_so_id}/confirm",
        headers=headers,
        json={"ghi_chu": "Cán bộ đã kiểm tra cảnh báo"},
        timeout=20.0,
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["xac_nhan_at"]


def test_A04_cap_nhat_doi_tuong_va_tham_quyen():
    token = get_token("mc.thu")
    headers = {"Authorization": f"Bearer {token}"}
    ho_so_id = run_sql("SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so = 'CP-HERO-2026-001';")
    assert ho_so_id

    try:
        upd = httpx.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/cap_nhat_thong_tin_tham_quyen",
            headers=headers,
            json={"p_ho_so_id": ho_so_id, "p_doi_tuong": "to_chuc", "p_trong_kcn": False, "p_cap_hanh_chinh": "tinh"},
            timeout=20.0,
        )
        assert upd.status_code == 200, upd.text
        assert upd.json()["co_quan_cap"] == "Sở Xây dựng"
    finally:
        httpx.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/cap_nhat_thong_tin_tham_quyen",
            headers=headers,
            json={"p_ho_so_id": ho_so_id, "p_doi_tuong": "ho_gia_dinh_ca_nhan", "p_trong_kcn": False, "p_cap_hanh_chinh": "xa"},
            timeout=20.0,
        )


def test_A04_phi_bien_lai_va_luu_tru_lifecycle():
    token = get_token("mc.thu")
    headers = {"Authorization": f"Bearer {token}"}
    ho_so_id = run_sql("SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so = 'CP-HERO-2026-001';")
    assert ho_so_id

    fee = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/fees",
        headers=headers,
        json={"ten_thu_tuc": "Kiểm thử phí A04", "muc_phi": 1000, "can_cu": "Kiểm thử"},
        timeout=20.0,
    )
    assert fee.status_code == 200, fee.text

    receipt = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/bien-lai",
        headers=headers,
        json={"ho_so_id": ho_so_id, "so_bien_lai": f"BL-A04-{uuid.uuid4().hex[:8]}", "so_tien": 50000},
        timeout=20.0,
    )
    assert receipt.status_code == 200, receipt.text
    rid = receipt.json()["id"]
    reconciled = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/bien-lai/{rid}/status",
        headers=headers,
        json={"trang_thai": "da_doi_soat"},
        timeout=20.0,
    )
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["trang_thai"] == "da_doi_soat"

    archive = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/archive/{ho_so_id}",
        headers=headers,
        json={"nhom_ho_so": "cap_phep_xay_dung"},
        timeout=20.0,
    )
    assert archive.status_code == 200, archive.text
    aid = archive.json()["id"]
    moved = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/archive/{aid}/status",
        headers=headers,
        json={"trang_thai": "chuyen_giao"},
        timeout=20.0,
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["trang_thai"] == "chuyen_giao"


def test_A04_chia_se_payload_toi_thieu():
    token = get_token("mc.thu")
    headers = {"Authorization": f"Bearer {token}"}
    ho_so_id = run_sql("SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so = 'CP-HERO-2026-001';")
    resp = httpx.get(f"{GATEWAY_URL}/api/v1/planning/share/payload/{ho_so_id}", headers=headers, timeout=20.0)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["can_cu_phap_ly"] == "ND-278/2025/ND-CP"
    assert body["cccd_masked"].startswith("*")
    assert len(body["cccd_masked"]) == 12


def test_A04_chia_se_du_lieu_theo_nd_278_va_luu_tru():
    token = get_token("mc.thu")
    headers = {"Authorization": f"Bearer {token}"}
    ho_so_id = run_sql("SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so = 'CP-HERO-2026-001';")
    assert ho_so_id

    share = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/share/export",
        headers=headers,
        json={"loai_du_lieu": "ho_so", "ho_so_id": ho_so_id, "ben_nhan": "CSDL quốc gia về HĐXD (demo)"},
        timeout=20.0,
    )
    assert share.status_code == 200, share.text
    assert share.json()["can_cu_phap_ly"] == "ND-278/2025/ND-CP"
    assert share.json()["trang_thai"] == "cho_ket_noi"

    logs = httpx.get(f"{GATEWAY_URL}/api/v1/planning/share/logs", headers=headers, timeout=20.0)
    assert logs.status_code == 200, logs.text
    assert any(x["ben_nhan"].startswith("CSDL quốc gia") for x in logs.json())

    fees = httpx.get(f"{GATEWAY_URL}/api/v1/planning/fees", headers=headers, timeout=20.0)
    assert fees.status_code == 200, fees.text
    assert any(x["status"] == "cho_van_ban_dia_phuong" for x in fees.json())

    archive = httpx.post(
        f"{GATEWAY_URL}/api/v1/planning/archive/{ho_so_id}",
        headers=headers,
        json={"nhom_ho_so": "cap_phep_xay_dung", "ghi_chu": "Lưu trữ hồ sơ hero"},
        timeout=20.0,
    )
    assert archive.status_code == 200, archive.text
    assert archive.json()["trang_thai"] in ("dang_luu_tru", "chuyen_giao", "tieu_huy", "het_han")
    listing = httpx.get(f"{GATEWAY_URL}/api/v1/planning/archive", headers=headers, timeout=20.0)
    assert listing.status_code == 200, listing.text
    assert any(x["ho_so_id"] == ho_so_id for x in listing.json())

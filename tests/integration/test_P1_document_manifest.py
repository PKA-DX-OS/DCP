# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""P1: Manifest giấy tờ + 7 lớp kiểm tra trước khi nộp hồ sơ."""

import json
import uuid

import httpx

from tests.integration._ho_so import (
    GATEWAY_URL,
    REQUIRED_DOC_LOAI,
    build_tep,
    get_token,
    normalize_payload,
    run_sql,
    submit_dossier,
    upload_document,
)


BASE_PAYLOAD = {
    "ho_ten": "Trần Văn P1",
    "cccd": "001099001234",
    "dien_thoai": "0901234567",
    "dia_chi_cong_trinh": "Số 1 Đường P1, Phường A",
    "thua_dat": "Thửa 12, Tờ 34",
    "so_tang": 3,
    "dien_tich_san_m2": 120.0,
    "khu_quan_ly_kien_truc": True,
}


def _post_nop_ho_so(token: str, payload: dict, ho_so_id: str, tep: list) -> httpx.Response:
    body = dict(payload)
    body["p_ho_so_id"] = ho_so_id
    body["p_tep"] = tep
    with httpx.Client(timeout=60.0) as client:
        return client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/nop_ho_so",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )


def _error_list(resp: httpx.Response) -> list:
    body = resp.json()
    details = body.get("details")
    assert isinstance(details, str), f"Thiếu details JSON: {body}"
    errors = json.loads(details)
    assert isinstance(errors, list) and errors, "Danh sách lỗi rỗng"
    return errors


def test_P1_missing_documents_returns_422_with_structured_errors():
    token = get_token("cdt.minh")
    payload = normalize_payload(BASE_PAYLOAD)
    resp = _post_nop_ho_so(token, payload, str(uuid.uuid4()), [])

    assert resp.status_code == 422, f"Thiếu giấy phải trả 422, nhận {resp.status_code}: {resp.text}"
    errors = _error_list(resp)
    missing = {e.get("loai_giay") for e in errors}
    assert set(REQUIRED_DOC_LOAI).issubset(missing), f"Thiếu loại giấy trong lỗi: {missing}"
    for err in errors:
        assert {"field", "reason", "action"}.issubset(err.keys()), f"Lỗi thiếu cấu trúc: {err}"


def test_P1_expired_document_returns_422():
    token = get_token("cdt.minh")
    payload = normalize_payload(BASE_PAYLOAD)
    ho_so_id = str(uuid.uuid4())
    with httpx.Client(timeout=60.0) as client:
        tep = build_tep(token, ho_so_id, payload, f"P1-exp-{ho_so_id[:8]}", client=client)
    for entry in tep:
        if entry["loai"] == "giay_to_dat":
            entry["ngay_het_han"] = "2020-01-01"

    resp = _post_nop_ho_so(token, payload, ho_so_id, tep)
    assert resp.status_code == 422, f"Giấy hết hạn phải trả 422: {resp.text}"
    errors = _error_list(resp)
    assert any("hết hạn" in e["reason"].lower() for e in errors), f"Không thấy lỗi hết hạn: {errors}"


def test_P1_duplicate_sha256_returns_422():
    token = get_token("cdt.minh")
    payload = normalize_payload(BASE_PAYLOAD)
    ho_so_id = str(uuid.uuid4())

    # Cùng nội dung tệp cho 2 loại giấy -> trùng SHA-256
    same_bytes_tag = f"P1-dup-{ho_so_id[:8]}"
    file_a = upload_document(token, ho_so_id, "don", same_bytes_tag)
    file_b = upload_document(token, ho_so_id, "giay_to_dat", same_bytes_tag)

    tep = [
        {"file_id": file_a, "loai": "don", "thong_tin": {"ho_ten": payload["ho_ten"], "cccd": payload["cccd"]}},
        {"file_id": file_b, "loai": "giay_to_dat", "thong_tin": {}, "ngay_het_han": "2035-01-01"},
    ]
    resp = _post_nop_ho_so(token, payload, ho_so_id, tep)
    assert resp.status_code == 422, f"Trùng SHA-256 phải trả 422: {resp.text}"
    errors = _error_list(resp)
    assert any("trùng SHA-256" in e["reason"] for e in errors), f"Không thấy lỗi trùng: {errors}"


def test_P1_cross_field_mismatch_returns_422():
    token = get_token("cdt.minh")
    payload = normalize_payload(BASE_PAYLOAD)
    ho_so_id = str(uuid.uuid4())
    with httpx.Client(timeout=60.0) as client:
        tep = build_tep(token, ho_so_id, payload, f"P1-l5-{ho_so_id[:8]}", client=client)
    for entry in tep:
        if entry["loai"] == "don":
            entry["thong_tin"]["ho_ten"] = "Nguyễn Văn Khác"

    resp = _post_nop_ho_so(token, payload, ho_so_id, tep)
    assert resp.status_code == 422, f"Lệch họ tên phải trả 422: {resp.text}"
    errors = _error_list(resp)
    assert any("Họ tên trên đơn khác hồ sơ" in e["reason"] for e in errors), f"Không thấy lỗi L5: {errors}"


def test_P1_valid_submission_then_review_file():
    token = get_token("cdt.minh")
    token_mc = get_token("mc.thu")
    payload = normalize_payload(BASE_PAYLOAD)

    resp = submit_dossier(token, payload, tag_prefix="P1-ok")
    assert resp.status_code == 200, f"Nộp đủ giấy phải 200: {resp.status_code} {resp.text}"
    data = resp.json()
    ho_so_id = data["id"]
    assert data.get("so_tep") == len(REQUIRED_DOC_LOAI)

    count = run_sql(f"SELECT count(*) FROM app_cap_phep.ho_so_tep WHERE ho_so_id = '{ho_so_id}';")
    assert int(count) == len(REQUIRED_DOC_LOAI), f"Số tệp trong DB phải là {len(REQUIRED_DOC_LOAI)}, nhận {count}"
    version = run_sql(f"SELECT min(version) FROM app_cap_phep.ho_so_tep WHERE ho_so_id = '{ho_so_id}';")
    assert int(version) == 1, f"Version khởi tạo phải là 1, nhận {version}"

    tep_id = run_sql(
        f"SELECT id FROM app_cap_phep.ho_so_tep WHERE ho_so_id = '{ho_so_id}' ORDER BY created_at LIMIT 1;"
    )
    assert tep_id, "Không tìm thấy tệp để đánh giá"

    with httpx.Client(timeout=30.0) as client:
        review = client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/danh_gia_tep",
            headers={"Authorization": f"Bearer {token_mc}"},
            json={"p_tep_id": tep_id, "p_trang_thai": "dat", "p_ly_do": None},
        )
    assert review.status_code == 200, f"Đánh giá tệp phải 200: {review.status_code} {review.text}"

    status = run_sql(f"SELECT trang_thai_kiem_tra FROM app_cap_phep.ho_so_tep WHERE id = '{tep_id}';")
    assert status == "dat", f"Trạng thái tệp phải là dat, nhận {status}"

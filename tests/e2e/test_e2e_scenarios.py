# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Kịch bản đầu-cuối trên stack thật (C15).

Mọi yêu cầu đi qua gateway APISIX, token lấy thật từ Keycloak (client `dx-test`, mật khẩu
trong secrets/demo-accounts.txt do seed sinh). Dữ liệu ghi thật vào PostgreSQL, SeaweedFS,
Flowable; ClamAV quét thật; doc-sign ký thật (SoftHSM hoặc OpenBao theo SIGNING_MODE).
Mỗi kịch bản tự tạo dữ liệu của mình và dọn lại khi kết thúc (audit log là WORM nên giữ nguyên).

Chạy: `pytest tests/e2e -q` (cần `dx up` với DEMO_MODE=true).
"""

import base64
import uuid

import httpx
import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, get_token
from tests.integration._ho_so import (
    cap_phep_den_buoc_duyet,
    complete_task,
    flowable,
    run_psql,
    run_sql,
    start_cap_phep,
    sub_of,
    submit_dossier,
    wait_task,
)

# Chuỗi kiểm thử chuẩn EICAR (không phải mã độc), mã hóa để không bị chính trình quét trên máy chặn tệp test
EICAR = base64.b64decode(
    b"WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo="
)
GIA_MAO = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciJ9.invalid"


@pytest.fixture(scope="module", autouse=True)
def _can_tai_khoan_demo():
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.fail("Thiếu secrets/demo-accounts.txt: chạy `dx up` với DEMO_MODE=true để seed sinh tài khoản demo")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _payload(tag: str, **them) -> dict:
    data = {
        "ho_ten": f"Nguyen Van E2E {tag}",
        "cccd": "001099008888",
        "dien_thoai": "0908888888",
        "dia_chi_cong_trinh": f"So {tag} Duong E2E",
        "thua_dat": f"Thua {tag}",
        "so_tang": 2,
        "dien_tich_san_m2": 150.0,
        "khu_quan_ly_kien_truc": True,
    }
    data.update(them)
    return data


def _don_ho_so(ho_so_id: str | None, proc_id: str | None) -> None:
    if proc_id:
        with flowable() as fl:
            fl.delete(f"/service/runtime/process-instances/{proc_id}")
    if ho_so_id:
        run_psql(
            f"DELETE FROM app_cap_phep.ho_so_lich_su WHERE ho_so_id = '{ho_so_id}';"
            f"DELETE FROM app_cap_phep.ho_so WHERE id = '{ho_so_id}';"
        )


def test_kb1_token_khong_hop_le_bi_tu_choi_401():
    """Không token, token giả HS256, token RS256 bị sửa chữ ký: gateway trả 401 trước khi tới dịch vụ."""
    duong_dan = [f"/api/v1/files/{uuid.uuid4()}", "/api/v1/flow/tasks", "/api/v1/rest/v_ho_so"]
    that = get_token("cdt.minh")
    sua_chu_ky = that[:-4] + ("AAAA" if not that.endswith("AAAA") else "BBBB")
    with httpx.Client(base_url=GATEWAY_URL, timeout=10.0) as c:
        for p in duong_dan:
            assert c.get(p).status_code == 401, f"{p} không token phải 401"
            assert c.get(p, headers=_auth(GIA_MAO)).status_code == 401, f"{p} token giả phải 401"
            assert c.get(p, headers=_auth(sua_chu_ky)).status_code == 401, f"{p} token sửa chữ ký phải 401"
        # Token thật vẫn qua được (đối chứng)
        assert c.get("/api/v1/flow/tasks", headers=_auth(that)).status_code == 200


def test_kb2_eicar_bi_chan_tep_sach_duoc_nhan():
    """ClamAV chặn EICAR (422, ghi audit file.infected); tệp PDF sạch được lưu (201, status clean)."""
    tok = get_token("cdt.minh")
    object_id = str(uuid.uuid4())
    data = {"object_type": "draft.ho_so", "object_id": object_id}
    with httpx.Client(base_url=GATEWAY_URL, timeout=60.0) as c:
        r = c.post("/api/v1/files", headers=_auth(tok), data=data,
                   files={"file": ("eicar.txt", EICAR, "text/plain")})
        assert r.status_code == 422, f"EICAR phải bị chặn 422, nhận {r.status_code}: {r.text}"
        assert r.json().get("loi") == "Tệp chứa mã độc"
        so_audit = run_sql(
            "SELECT count(*) FROM core.audit_log WHERE action = 'file.infected' "
            f"AND object_id = '{object_id}';"
        )
        assert int(so_audit) == 1, "Phải ghi đúng một audit file.infected"

        sach = f"%PDF-1.4\n% e2e {object_id}\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n".encode()
        r = c.post("/api/v1/files", headers=_auth(tok), data=data,
                   files={"file": ("ban_ve.pdf", sach, "application/pdf")})
        assert r.status_code == 201, f"Tệp sạch phải được nhận, nhận {r.status_code}: {r.text}"
        body = r.json()
        assert body["status"] == "clean" and body["file_id"] and len(body["sha256"]) == 64

    so_tep = run_sql(
        "SELECT count(*) FROM core.files WHERE object_type = 'draft.ho_so' "
        f"AND object_id = '{object_id}' AND status = 'clean';"
    )
    assert int(so_tep) == 1, "Chỉ tệp sạch được ghi vào core.files"


def test_kb3_thao_tac_task_quy_trinh():
    """Hồ sơ mới khởi động cap-phep; một cửa thấy và hoàn thành việc, việc tiếp theo chuyển sang lãnh đạo."""
    tok = {u: get_token(u) for u in ("cdt.minh", "mc.thu", "ld.hoa")}
    ho_so_id = proc_id = None
    try:
        r = submit_dossier(tok["cdt.minh"], _payload(uuid.uuid4().hex[:6]), tag_prefix="e2e-kb3")
        assert r.status_code == 200, f"Nộp hồ sơ thất bại: {r.status_code} {r.text}"
        ho_so = r.json()
        ho_so_id = ho_so["id"]
        proc_id = start_cap_phep(tok["cdt.minh"], ho_so, {"dien_tich_san_m2": 150.0, "khu_quan_ly_kien_truc": True})

        viec = wait_task(tok["mc.thu"], proc_id, "taskKiemTraHopLe")
        ds = httpx.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers=_auth(tok["mc.thu"]), timeout=10.0).json()
        assert ds["tenant"] == "phuong-a"

        chi_tiet = httpx.get(f"{GATEWAY_URL}/api/v1/flow/tasks/{viec['id']}", headers=_auth(tok["mc.thu"]), timeout=10.0)
        assert chi_tiet.status_code == 200, chi_tiet.text

        r = complete_task(tok["mc.thu"], viec["id"], {"hoSoHopLe": True})
        assert r.status_code == 200, f"Một cửa hoàn thành việc thất bại: {r.status_code} {r.text}"
        wait_task(tok["ld.hoa"], proc_id, "taskPhanCong")

        # Việc đã xong không còn hoàn thành lại được
        r = complete_task(tok["mc.thu"], viec["id"], {"hoSoHopLe": True})
        assert r.status_code in (403, 404, 409), f"Hoàn thành lại việc đã xong phải bị từ chối, nhận {r.status_code}"
    finally:
        _don_ho_so(ho_so_id, proc_id)


def test_kb4_rls_postgrest_cach_ly_chu_the_va_tenant():
    """Hồ sơ của cdt.minh: chủ hồ sơ và một cửa cùng phường thấy; cdt.lan và cán bộ phường B không thấy, không sửa được."""
    tok = {u: get_token(u) for u in ("cdt.minh", "cdt.lan", "mc.thu", "mc.phuongb")}
    ho_so_id = None
    try:
        r = submit_dossier(tok["cdt.minh"], _payload(uuid.uuid4().hex[:6]), tag_prefix="e2e-kb4")
        assert r.status_code == 200, f"Nộp hồ sơ thất bại: {r.status_code} {r.text}"
        ho_so_id = r.json()["id"]
        url = f"{GATEWAY_URL}/api/v1/rest/v_ho_so?id=eq.{ho_so_id}&select=id,tenant"

        def thay(user: str) -> list:
            res = httpx.get(url, headers=_auth(tok[user]), timeout=10.0)
            assert res.status_code == 200, f"{user}: {res.status_code} {res.text}"
            return res.json()

        assert [x["id"] for x in thay("cdt.minh")] == [ho_so_id]
        assert [x["tenant"] for x in thay("mc.thu")] == ["phuong-a"]
        assert thay("cdt.lan") == [], "Chủ đầu tư khác không được thấy hồ sơ"
        assert thay("mc.phuongb") == [], "Cán bộ phường B không được thấy hồ sơ phường A"

        for user in ("cdt.lan", "mc.phuongb"):
            res = httpx.patch(
                f"{GATEWAY_URL}/api/v1/rest/ho_so?id=eq.{ho_so_id}",
                headers={**_auth(tok[user]), "Prefer": "return=representation"},
                json={"dia_chi_cong_trinh": "Dia chi bi sua"}, timeout=10.0,
            )
            assert res.status_code in (200, 204, 403), f"{user} PATCH: {res.status_code} {res.text}"
            if res.status_code == 200:
                assert res.json() == [], f"RLS phải chặn {user} sửa hồ sơ"
        dia_chi = run_sql(f"SELECT dia_chi_cong_trinh FROM app_cap_phep.ho_so WHERE id = '{ho_so_id}';")
        assert dia_chi != "Dia chi bi sua"
    finally:
        _don_ho_so(ho_so_id, None)


def test_kb5_sod_loai_tru_nguoi_tham_dinh_tu_duyet():
    """Đi đủ quy trình tới bước duyệt; nếu người thẩm định trùng người duyệt thì flow chặn 403 và ghi audit."""
    ket_qua = cap_phep_den_buoc_duyet("cdt.minh", _payload(uuid.uuid4().hex[:6]), tag_prefix="e2e-kb5")
    proc_id, duyet, tok = ket_qua["proc_id"], ket_qua["task"], ket_qua["tokens"]
    try:
        with flowable() as fl:
            res = fl.put(f"/service/runtime/process-instances/{proc_id}/variables",
                         json=[{"name": "nguoiThamDinh", "type": "string", "value": sub_of(tok["ld.hoa"])}])
            assert res.status_code in (200, 201), f"Không đặt được nguoiThamDinh: {res.status_code} {res.text}"

        r = complete_task(tok["ld.hoa"], duyet["id"], {"dongYCapPhep": False, "yKienPheDuyet": "Thử tự duyệt"})
        assert r.status_code == 403, f"SoD phải chặn tự duyệt, nhận {r.status_code}: {r.text}"
        assert "phân tách nhiệm vụ" in r.text
        so_audit = run_sql(
            "SELECT count(*) FROM core.audit_log WHERE action = 'sod.violation_prevented' "
            f"AND object_id = '{duyet['id']}';"
        )
        assert int(so_audit) >= 1, "Phải ghi audit sod.violation_prevented"
        wait_task(tok["ld.hoa"], proc_id, "taskDuyetCapPhep", tries=2)
    finally:
        _don_ho_so(ket_qua["ho_so"]["id"], proc_id)


def test_kb6_ky_van_ban_va_xac_minh_cong_khai():
    """Lãnh đạo ký; tra cứu công khai Hop_le, không tải bản gốc công khai; đối soát tệp đúng/sửa 1 byte; thu hồi."""
    tok = get_token("ld.hoa")
    with httpx.Client(base_url=GATEWAY_URL, timeout=30.0) as c:
        r = c.post("/api/v1/docs/sign", headers=_auth(tok), json={
            "doc_type": "giay-phep-xay-dung",
            "data": {"ho_ten": "Trần Văn Minh (mẫu)", "dia_chi": "Số 123 Đường Hoa Phượng (mẫu)"},
        })
        assert r.status_code == 201, f"Ký thất bại: {r.status_code} {r.text}"
        doc = r.json()
        code = doc["public_code"]
        try:
            assert doc["status"] == "valid" and doc["signature"]

            pub = c.get(f"/kiem-tra/{code}", headers={"Accept": "application/json"})
            assert pub.status_code == 200 and pub.json()["trang_thai"] == "Hop_le", pub.text
            assert pub.json()["sha256"] == doc["sha256"]
            assert "data" not in pub.json() and "ho_ten" not in pub.text, "Trang công khai không lộ dữ liệu cá nhân"

            assert c.get(f"/kiem-tra/{code}/download").status_code in (404, 405), "Không tải bản gốc công khai (U-01)"
            assert c.get(f"/api/v1/docs/{doc['doc_id']}/download").status_code == 401
            pdf = c.get(f"/api/v1/docs/{doc['doc_id']}/download", headers=_auth(tok))
            assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

            ok = c.post(f"/kiem-tra/{code}/verify-file", files={"file": ("gp.pdf", pdf.content, "application/pdf")})
            assert ok.status_code == 200 and ok.json()["valid"] is True, ok.text
            assert ok.json()["signature_type"] == pub.json()["signature_type"]

            sua = bytearray(pdf.content)
            sua[200] ^= 0x01
            bad = c.post(f"/kiem-tra/{code}/verify-file", files={"file": ("gp-sua.pdf", bytes(sua), "application/pdf")})
            assert bad.status_code == 200 and bad.json()["valid"] is False and bad.json()["hash_match"] is False

            assert c.get("/kiem-tra/DOC-khongtontai0000000000", headers={"Accept": "application/json"}).status_code == 404
        finally:
            rv = c.post(f"/api/v1/docs/{doc['doc_id']}/revoke", headers=_auth(tok), json={"ly_do": "Văn bản kiểm thử e2e"})
            assert rv.status_code == 200, rv.text
        sau = c.get(f"/kiem-tra/{code}", headers={"Accept": "application/json"})
        assert sau.json()["trang_thai"] == "Da_thu_hoi"

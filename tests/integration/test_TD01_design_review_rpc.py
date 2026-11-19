# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-REVIEW-01/02: schema, RLS và RPC 5.2 qua PostgREST."""

import time
import uuid

import httpx

from tests.integration._auth import GATEWAY_URL
from tests.integration._ho_so import make_pdf, start_process


def _rpc(token: str, ten: str, body: dict) -> httpx.Response:
    return httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/{ten}",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=30.0,
    )


def _upload(token: str, ho_so_id: str, tag: str, object_type: str = "ho_so") -> str:
    resp = httpx.post(
        f"{GATEWAY_URL}/api/v1/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (f"{tag}.pdf", make_pdf(tag), "application/pdf")},
        data={"object_type": object_type, "object_id": ho_so_id},
        timeout=60.0,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["file_id"]


def test_TD01_phien_ban_ban_ve_nhan_xet_va_trang_thai(ho_so_moi, token):
    cdt = token("cdt.minh")
    td = token("td.binh")
    ho_so_id = ho_so_moi["id"]

    key = f"pb-{uuid.uuid4().hex}"
    pb = _rpc(cdt, "tao_phien_ban", {"p_ho_so_id": ho_so_id, "p_mo_ta": "Hồ sơ thiết kế ban đầu", "p_idempotency_key": key})
    assert pb.status_code == 200, pb.text
    pb1 = pb.json()
    assert pb1["so_phien_ban"] == 1
    again = _rpc(cdt, "tao_phien_ban", {"p_ho_so_id": ho_so_id, "p_mo_ta": "Khác", "p_idempotency_key": key})
    assert again.status_code == 200 and again.json()["id"] == pb1["id"]

    # v1: kiến trúc đạt, MEP không đạt, thiếu kết cấu.
    for bo_mon, tag in (("kien_truc", "kt"), ("mep", "me")):
        file_id = _upload(cdt, ho_so_id, f"TD01-{tag}-{ho_so_id[:8]}")
        r = _rpc(cdt, "them_ban_ve", {
            "p_phien_ban_id": pb1["id"],
            "p_bo_mon": bo_mon,
            "p_ten": f"Bản vẽ {tag}",
            "p_file_id": file_id,
            "p_idempotency_key": f"bv-{uuid.uuid4().hex}",
        })
        assert r.status_code == 200, r.text
        assert len(r.json()["sha256"]) == 64

    ds = _rpc(cdt, "ds_ban_ve", {"p_ho_so_id": ho_so_id})
    assert ds.status_code == 200, ds.text
    nhom = {x["bo_mon"]: x for x in ds.json()["nhom"]}
    assert len(nhom["kien_truc"]["ban_ve"]) == 1
    assert nhom["ket_cau"]["ban_ve"] == []

    bv = {x["bo_mon"]: x for x in ds.json()["nhom"] if x["ban_ve"]}
    kt_id = bv["kien_truc"]["ban_ve"][0]["id"]
    me_id = bv["mep"]["ban_ve"][0]["id"]
    assert _rpc(td, "danh_gia_ban_ve", {"p_ban_ve_id": kt_id, "p_ket_qua": "dat"}).status_code == 200
    assert _rpc(td, "danh_gia_ban_ve", {"p_ban_ve_id": me_id, "p_ket_qua": "khong_dat"}).status_code == 200
    cmt = _rpc(td, "them_nhan_xet", {
        "p_ban_ve_id": me_id,
        "p_noi_dung": "Bổ sung sơ đồ cấp điện",
        "p_muc_do": "loi",
    })
    assert cmt.status_code == 200, cmt.text

    cmt2 = _rpc(td, "them_nhan_xet", {
        "p_ban_ve_id": me_id,
        "p_noi_dung": "Ghi chú thêm cho MEP",
        "p_muc_do": "gop_y",
    })
    assert cmt2.status_code == 200, cmt2.text

    ds_nx = _rpc(td, "ds_nhan_xet", {"p_phien_ban_id": pb1["id"], "p_muc_do": "loi"})
    assert ds_nx.status_code == 200, ds_nx.text
    assert [x["id"] for x in ds_nx.json()] == [cmt.json()["id"]]

    tat_ca = _rpc(cdt, "ds_nhan_xet", {"p_phien_ban_id": pb1["id"]})
    assert tat_ca.status_code == 200, tat_ca.text
    assert tat_ca.json()[0]["id"] == cmt2.json()["id"]

    da_xu_ly = _rpc(cdt, "xu_ly_nhan_xet", {"p_nhan_xet_id": cmt.json()["id"], "p_ghi_chu": "Đã bổ sung"})
    assert da_xu_ly.status_code == 200, da_xu_ly.text
    assert da_xu_ly.json()["trang_thai"] == "da_xu_ly"
    lai = _rpc(cdt, "xu_ly_nhan_xet", {"p_nhan_xet_id": cmt.json()["id"]})
    assert lai.status_code == 409, lai.text
    assert lai.json()["code"] == "PT409"

    status = _rpc(td, "trang_thai_tham_dinh", {"p_ho_so_id": ho_so_id})
    assert status.status_code == 200, status.text
    st = status.json()
    assert "ket_cau" in st["thieu_bo_mon"]
    assert st["ket_luan"] == "khong_dat"
    assert st["nhan_xet_mo"] == 1

    # v2: đủ 3 bộ môn bắt buộc, tất cả đạt.
    pb2 = _rpc(cdt, "tao_phien_ban", {"p_ho_so_id": ho_so_id, "p_mo_ta": "Bổ sung kết cấu và sửa MEP"})
    assert pb2.status_code == 200, pb2.text
    pb2_id = pb2.json()["id"]
    assert pb2.json()["so_phien_ban"] == 2
    for bo_mon, tag in (("kien_truc", "kt2"), ("ket_cau", "kc2"), ("mep", "me2")):
        file_id = _upload(cdt, ho_so_id, f"TD01-v2-{tag}-{ho_so_id[:8]}")
        r = _rpc(cdt, "them_ban_ve", {
            "p_phien_ban_id": pb2_id,
            "p_bo_mon": bo_mon,
            "p_ten": f"Bản vẽ v2 {tag}",
            "p_file_id": file_id,
        })
        assert r.status_code == 200, r.text
    ds2 = _rpc(td, "ds_ban_ve", {"p_ho_so_id": ho_so_id})
    v2_ids = [x["id"] for g in ds2.json()["nhom"] for x in g["ban_ve"] if x["phien_ban_id"] == pb2_id]
    assert len(v2_ids) == 3
    for bv_id in v2_ids:
        assert _rpc(td, "danh_gia_ban_ve", {"p_ban_ve_id": bv_id, "p_ket_qua": "dat"}).status_code == 200

    status2 = _rpc(td, "trang_thai_tham_dinh", {"p_ho_so_id": ho_so_id})
    assert status2.status_code == 200, status2.text
    assert status2.json()["ket_luan"] == "dat"
    assert status2.json()["thieu_bo_mon"] == []
    assert status2.json()["so_phien_ban"] == 2

    # Chủ đầu tư không được đánh giá bản vẽ.
    denied = _rpc(cdt, "danh_gia_ban_ve", {"p_ban_ve_id": v2_ids[0], "p_ket_qua": "dat"})
    assert denied.status_code == 403, denied.text


def test_TD01_danh_muc_bo_mon_va_rls_doc(ho_so_moi, token):
    cdt = token("cdt.minh")
    td = token("td.binh")
    khac = token("cdt.lan")

    r = httpx.get(
        f"{GATEWAY_URL}/api/v1/rest/bo_mon_thiet_ke?select=ma,ten,bat_buoc,thu_tu&order=thu_tu",
        headers={"Authorization": f"Bearer {cdt}"},
        timeout=30.0,
    )
    assert r.status_code == 200, r.text
    assert [x["ma"] for x in r.json()] == ["kien_truc", "ket_cau", "mep", "pccc"]

    pb = _rpc(cdt, "tao_phien_ban", {"p_ho_so_id": ho_so_moi["id"], "p_mo_ta": "RLS"})
    assert pb.status_code == 200, pb.text
    url = f"{GATEWAY_URL}/api/v1/rest/phien_ban_thiet_ke?ho_so_id=eq.{ho_so_moi['id']}&select=id,so_phien_ban"

    cua_chu = httpx.get(url, headers={"Authorization": f"Bearer {cdt}"}, timeout=30.0)
    assert cua_chu.status_code == 200, cua_chu.text
    assert len(cua_chu.json()) == 1

    cua_tham_dinh = httpx.get(url, headers={"Authorization": f"Bearer {td}"}, timeout=30.0)
    assert cua_tham_dinh.status_code == 200, cua_tham_dinh.text
    assert len(cua_tham_dinh.json()) == 1

    nguoi_khac = httpx.get(url, headers={"Authorization": f"Bearer {khac}"}, timeout=30.0)
    assert nguoi_khac.status_code == 200, nguoi_khac.text
    assert nguoi_khac.json() == []

    anon = httpx.get(url, timeout=30.0)
    assert anon.status_code in (401, 403), anon.text


def test_TD01_rpc_khong_nhan_tenant_va_kiem_quyen(ho_so_moi, token):
    cdt = token("cdt.minh")
    body = {"p_ho_so_id": ho_so_moi["id"], "p_mo_ta": "Kiểm tra tenant", "tenant": "phuong-b"}
    r = _rpc(cdt, "tao_phien_ban", body)
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "PGRST202"

    ok = _rpc(cdt, "tao_phien_ban", {"p_ho_so_id": ho_so_moi["id"], "p_mo_ta": "Kiểm tra tenant"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["ho_so_id"] == ho_so_moi["id"]


def _viec_cua(token: str, proc_id: str, task_def: str | None = None) -> list[dict]:
    body = httpx.get(
        f"{GATEWAY_URL}/api/v1/flow/tasks",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    ).json()
    ds = [t for t in body.get("tasks", []) if t.get("processInstanceId") == proc_id]
    return [t for t in ds if task_def is None or t.get("taskDefinitionKey") == task_def]


def _cho_viec(token: str, proc_id: str, task_def: str, so_luong: int = 1, tries: int = 20) -> list[dict]:
    for _ in range(tries):
        ds = _viec_cua(token, proc_id, task_def)
        if len(ds) >= so_luong:
            return ds
        time.sleep(1)
    raise AssertionError(f"Không đủ {so_luong} việc {task_def} của {proc_id}")


def _hoan_thanh(token: str, task_id: str, variables: dict) -> None:
    r = httpx.post(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{task_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"variables": variables},
        timeout=20.0,
    )
    assert r.status_code == 200, r.text


def test_TD01_kiem_tra_tham_so_va_tep(ho_so_moi, token):
    cdt = token("cdt.minh")
    td = token("td.binh")
    ho_so_id = ho_so_moi["id"]

    trong = _rpc(cdt, "tao_phien_ban", {"p_ho_so_id": ho_so_id, "p_mo_ta": "   "})
    assert trong.status_code == 400, trong.text
    assert trong.json()["code"] == "22023"

    khong_co = _rpc(cdt, "tao_phien_ban", {"p_ho_so_id": str(uuid.uuid4()), "p_mo_ta": "Không tồn tại"})
    assert khong_co.status_code == 404, khong_co.text

    status = _rpc(td, "trang_thai_tham_dinh", {"p_ho_so_id": str(uuid.uuid4())})
    assert status.status_code == 404, status.text

    pb = _rpc(cdt, "tao_phien_ban", {"p_ho_so_id": ho_so_id, "p_mo_ta": "Kiểm tra tệp"}).json()

    sai_ho_so = _upload(cdt, str(uuid.uuid4()), f"TD01-sai-{uuid.uuid4().hex[:8]}", object_type="draft.ho_so")
    r = _rpc(cdt, "them_ban_ve", {
        "p_phien_ban_id": pb["id"],
        "p_bo_mon": "kien_truc",
        "p_ten": "Tệp sai hồ sơ",
        "p_file_id": sai_ho_so,
    })
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "22023"

    dung_ho_so = _upload(cdt, ho_so_id, f"TD01-dung-{ho_so_id[:8]}")
    r = _rpc(cdt, "them_ban_ve", {
        "p_phien_ban_id": pb["id"],
        "p_bo_mon": "dien",
        "p_ten": "Bộ môn sai",
        "p_file_id": dung_ho_so,
    })
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "22023"

    r = _rpc(cdt, "them_ban_ve", {
        "p_phien_ban_id": pb["id"],
        "p_bo_mon": "kien_truc",
        "p_ten": "Bản vẽ hợp lệ",
        "p_file_id": dung_ho_so,
    })
    assert r.status_code == 200, r.text
    bv_id = r.json()["id"]
    r = _rpc(td, "danh_gia_ban_ve", {"p_ban_ve_id": bv_id, "p_ket_qua": "chua_dat"})
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "22023"
    r = _rpc(td, "them_nhan_xet", {"p_ban_ve_id": bv_id, "p_noi_dung": "x", "p_muc_do": "nang"})
    assert r.status_code == 400, r.text


def test_TD01_bpmn_tham_dinh_da_bo_mon(ho_so_moi, token):
    cdt = token("cdt.minh")
    td = token("td.binh")
    ld = token("ld.hoa")
    proc = start_process(cdt, "tham-dinh-thiet-ke", {
        "ho_so_id": ho_so_moi["id"],
        "ma_ho_so": ho_so_moi["ma_ho_so"],
        "chu_dau_tu_sub": "cdt.minh",
    }, business_key=f"{ho_so_moi['ma_ho_so']}-TD-{uuid.uuid4().hex[:6]}")

    bo_mon = _cho_viec(td, proc, "taskThamDinhBoMon", so_luong=4)
    ten = sorted(t.get("name") or "" for t in bo_mon)
    assert any("kien_truc" in x for x in ten)
    assert any("ket_cau" in x for x in ten)
    assert any("mep" in x for x in ten)
    assert any("pccc" in x for x in ten)
    for t in bo_mon:
        _hoan_thanh(td, t["id"], {"ket_qua_bo_mon": "dat"})

    hop = _cho_viec(ld, proc, "taskTongHopThietKe")[0]
    _hoan_thanh(ld, hop["id"], {"ket_luan_thiet_ke": "dat"})

    for _ in range(15):
        if not _viec_cua(td, proc) and not _viec_cua(ld, proc):
            return
        time.sleep(1)
    raise AssertionError(f"Quy trình {proc} chưa kết thúc")

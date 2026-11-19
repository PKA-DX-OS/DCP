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

    ds_pb = _rpc(td, "ds_phien_ban", {"p_ho_so_id": ho_so_id})
    assert ds_pb.status_code == 200, ds_pb.text
    phien_ban = ds_pb.json()
    assert [x["so_phien_ban"] for x in phien_ban] == [2, 1]
    assert len(phien_ban[0]["ban_ve"]) == 3
    assert len(phien_ban[1]["ban_ve"]) == 2
    assert phien_ban[1]["trang_thai"] == "khong_dat"
    assert phien_ban[0]["trang_thai"] == "dat"

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

    phuong_b = token("td.phuongb")
    khac_tenant = httpx.get(url, headers={"Authorization": f"Bearer {phuong_b}"}, timeout=30.0)
    assert khac_tenant.status_code == 200, khac_tenant.text
    assert khac_tenant.json() == []
    rpc_khac_tenant = _rpc(phuong_b, "ds_ban_ve", {"p_ho_so_id": ho_so_moi["id"]})
    assert rpc_khac_tenant.status_code == 404, rpc_khac_tenant.text
    assert rpc_khac_tenant.json()["code"] == "PT404"

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

    bv_key = f"bv-{uuid.uuid4().hex}"
    r = _rpc(cdt, "them_ban_ve", {
        "p_phien_ban_id": pb["id"],
        "p_bo_mon": "kien_truc",
        "p_ten": "Bản vẽ hợp lệ",
        "p_file_id": dung_ho_so,
        "p_idempotency_key": bv_key,
    })
    assert r.status_code == 200, r.text
    bv_id = r.json()["id"]
    lai_bv = _rpc(cdt, "them_ban_ve", {
        "p_phien_ban_id": pb["id"],
        "p_bo_mon": "kien_truc",
        "p_ten": "Bản vẽ hợp lệ",
        "p_file_id": dung_ho_so,
        "p_idempotency_key": bv_key,
    })
    assert lai_bv.status_code == 200 and lai_bv.json()["id"] == bv_id

    nx_key = f"nx-{uuid.uuid4().hex}"
    nx1 = _rpc(td, "them_nhan_xet", {
        "p_ban_ve_id": bv_id,
        "p_noi_dung": "Kiểm tra lại kết cấu",
        "p_muc_do": "canh_bao",
        "p_idempotency_key": nx_key,
    })
    assert nx1.status_code == 200, nx1.text
    nx2 = _rpc(td, "them_nhan_xet", {
        "p_ban_ve_id": bv_id,
        "p_noi_dung": "Kiểm tra lại kết cấu",
        "p_muc_do": "canh_bao",
        "p_idempotency_key": nx_key,
    })
    assert nx2.status_code == 200 and nx2.json()["id"] == nx1.json()["id"]

    r = _rpc(td, "danh_gia_ban_ve", {"p_ban_ve_id": bv_id, "p_ket_qua": "chua_dat"})
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "22023"
    r = _rpc(td, "them_nhan_xet", {"p_ban_ve_id": bv_id, "p_noi_dung": "x", "p_muc_do": "nang"})
    assert r.status_code == 400, r.text

    # Vai sai: thẩm định viên không tạo phiên bản; chủ hồ sơ không nhận xét.
    r = _rpc(td, "tao_phien_ban", {"p_ho_so_id": ho_so_id, "p_mo_ta": "Sai vai"})
    assert r.status_code == 403, r.text
    r = _rpc(cdt, "them_nhan_xet", {"p_ban_ve_id": bv_id, "p_noi_dung": "Sai vai", "p_muc_do": "gop_y"})
    assert r.status_code == 403, r.text


def test_TD01_bpmn_tham_dinh_da_bo_mon(ho_so_moi, token):
    cdt = token("cdt.minh")
    td = token("td.binh")
    ld = token("ld.hoa")
    mc = token("mc.thu")
    # Một cửa khởi động để chủ đầu tư không bị quy tắc phân tách nhiệm vụ chặn ở task bổ sung.
    proc = start_process(mc, "tham-dinh-thiet-ke", {
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
    _hoan_thanh(ld, hop["id"], {"ket_luan_thiet_ke": "khong_dat"})

    bo_sung = _cho_viec(cdt, proc, "taskBoSungThietKe")[0]
    _hoan_thanh(cdt, bo_sung["id"], {"mo_ta_bo_sung": "Bổ sung kết cấu và MEP"})

    bo_mon_lan_2 = _cho_viec(td, proc, "taskThamDinhBoMon", so_luong=4)
    assert len(bo_mon_lan_2) == 4
    for t in bo_mon_lan_2:
        _hoan_thanh(td, t["id"], {"ket_qua_bo_mon": "dat"})
    hop2 = _cho_viec(ld, proc, "taskTongHopThietKe")[0]
    _hoan_thanh(ld, hop2["id"], {"ket_luan_thiet_ke": "dat"})

    for _ in range(15):
        if not _viec_cua(td, proc) and not _viec_cua(ld, proc) and not _viec_cua(cdt, proc):
            return
        time.sleep(1)
    raise AssertionError(f"Quy trình {proc} chưa kết thúc")

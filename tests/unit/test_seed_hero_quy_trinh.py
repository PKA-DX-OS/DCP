# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-08: seed_hero đưa CP-HERO-2026-001 tới bước thẩm định giao td.binh (Flowable giả lập)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("seed_hero", ROOT / "scripts/seed_hero.py")
sh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sh)

HS, CDT, TD = "11111111-1111-1111-1111-111111111111", "cdt-sub", "td-binh-sub"


class FlowableGia:
    """Mô phỏng cap-phep: KiemTraHopLe -> PhanCong -> ThamDinh."""

    def __init__(self, proc_cu_buoc=None):
        self.buoc = {"P-CU": proc_cu_buoc} if proc_cu_buoc else {}
        self.da_xoa, self.bien_hoan_thanh, self.bien_mo = [], [], None

    def goi(self, method, path, body=None):
        if method == "DELETE":
            self.da_xoa.append(path.split("/")[-1].split("?")[0])
            return 204, None
        if method == "POST" and path.endswith("/process-instances"):
            self.bien_mo = {v["name"]: v["value"] for v in body["variables"]}
            self.buoc["P-MOI"] = "taskKiemTraHopLe"
            return 201, {"id": "P-MOI"}
        raise AssertionError(path)

    def viec_dang_mo(self, proc_id):
        b = self.buoc.get(proc_id)
        return [{"id": f"{proc_id}-{b}", "taskDefinitionKey": b}] if b else []

    def hoan_thanh(self, task_id, bien):
        proc_id, buoc = task_id.rsplit("-", 1)
        self.bien_hoan_thanh.append((buoc, bien))
        self.buoc[proc_id] = {"taskKiemTraHopLe": "taskPhanCong", "taskPhanCong": "taskThamDinh"}[buoc]


def _chay(monkeypatch, fl, proc_cu="", da_phan_cong=True):
    sql_da_chay = []

    def psql(_cmd, sql):
        sql_da_chay.append(sql)
        if sql.startswith("SELECT h.id"):
            return f"{HS}|{proc_cu}|{CDT}|{TD}"
        if "core.assignments" in sql:
            return "1" if da_phan_cong else "0"
        return ""

    monkeypatch.setenv("FLOWABLE_PASSWORD", "x")
    monkeypatch.setattr(sh, "Flowable", lambda *a: fl)
    monkeypatch.setattr(sh, "psql_gia_tri", psql)
    return sh.gan_quy_trinh_hero([]), sql_da_chay


def test_mo_quy_trinh_moi_toi_tham_dinh_giao_td_binh(monkeypatch):
    fl = FlowableGia()
    kq, sql = _chay(monkeypatch, fl)
    assert kq.startswith("[PASS]")
    assert fl.bien_mo["ho_so_id"] == HS and fl.bien_mo["dien_tich_san_m2"] == 600.0
    assert fl.bien_hoan_thanh == [("taskKiemTraHopLe", {"hoSoHopLe": True}), ("taskPhanCong", {"nguoiThamDinh": TD})]
    assert any("process_instance_id = 'P-MOI'" in s for s in sql)
    dong_bo = [s for s in sql if "sync_flow_state" in s]
    assert len(dong_bo) == 2 and "'taskKiemTraHopLe'" in dong_bo[0] and "'taskPhanCong'" in dong_bo[1]
    assert TD in dong_bo[1], "Bước phân công phải ghi thẩm định viên để có core.assignments"


def test_da_o_tham_dinh_thi_giu_nguyen(monkeypatch):
    fl = FlowableGia(proc_cu_buoc="taskThamDinh")
    kq, sql = _chay(monkeypatch, fl, proc_cu="P-CU")
    assert kq.startswith("[PASS]") and not fl.da_xoa and fl.bien_mo is None
    assert not any(s.startswith("UPDATE") or "sync_flow_state" in s for s in sql)


def test_da_o_tham_dinh_thieu_phan_cong_thi_bo_sung(monkeypatch):
    fl = FlowableGia(proc_cu_buoc="taskThamDinh")
    kq, sql = _chay(monkeypatch, fl, proc_cu="P-CU", da_phan_cong=False)
    assert "bổ sung phân công" in kq and fl.bien_mo is None
    dong_bo = [s for s in sql if "sync_flow_state" in s]
    assert len(dong_bo) == 1 and "'P-CU', 'taskPhanCong'" in dong_bo[0]


def test_quy_trinh_cu_da_di_tiep_thi_lam_lai(monkeypatch):
    fl = FlowableGia(proc_cu_buoc="taskDuyetCapPhep")
    kq, _ = _chay(monkeypatch, fl, proc_cu="P-CU")
    assert kq.startswith("[PASS]") and fl.da_xoa == ["P-CU"]


def test_thieu_mat_khau_chi_canh_bao(monkeypatch, tmp_path):
    monkeypatch.delenv("FLOWABLE_PASSWORD", raising=False)
    monkeypatch.setattr(sh, "ROOT", tmp_path)
    assert sh.gan_quy_trinh_hero([]).startswith("[CẢNH BÁO]")

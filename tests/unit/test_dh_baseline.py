# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""D-P0-02: tính mốc đo D & H từ số đếm thô (không cần stack)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("dh_baseline", ROOT / "scripts/dh_baseline.py")
dh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dh)

RAW = {
    "tong_ho_so": 4,
    "thao_tac_moi_ho_so": [1, 1, 2, 8],
    "chuyen_tay_moi_ho_so": [0, 0, 1, 3],
    "thao_tac_chu_dau_tu": 3,
    "thao_tac_nguoi_dung": 12,
    "task_hoan_thanh": 5,
    "ho_so_phai_bo_sung": 2,
    "vong_bo_sung": 3,
    "ocr_trich_xuat": 0,
    "cccd_sai_dang": 1,
    "dien_thoai_sai_dang": 0,
    "thieu_ma_dia_diem": 2,
    "thieu_thua_dat": 0,
    "cccd_nhieu_ten": 1,
    "ho_so_trung_cccd_thua": 1,
    "job_lineage": 1,
    "mdm_subject": 0,
}


def test_chi_so_h():
    tac_dong = {"do_duoc": {"thoi_gian_xu_ly_tb_ngay_lam_viec": 4.5, "ty_le_ky_dung_han_pct": 75.0}}
    h = dh.tinh(RAW, tac_dong)["h"]
    assert h["thao_tac_thu_cong_tb"] == 3.0
    assert h["thao_tac_thu_cong_trung_vi"] == 1.5
    assert h["chuyen_tay_tb"] == 1.0
    assert h["ty_le_ho_so_phai_bo_sung_pct"] == 50.0
    assert h["vong_bo_sung_tb_tren_ho_so_bo_sung"] == 1.5
    assert h["ty_le_tu_phuc_vu_pct"] == 25.0
    assert h["task_hoan_thanh_chua_gan_ho_so"] == 5
    assert h["trich_xuat_tu_dong"] == 0
    assert h["thoi_gian_xu_ly_tb_ngay_lam_viec"] == 4.5


def test_chi_so_d():
    d = dh.tinh(RAW)["d"]
    assert d["cccd_sai_dang_pct"] == 25.0
    assert d["thieu_ma_dinh_danh_dia_diem_pct"] == 50.0
    assert d["ty_le_trung_pct"] == 25.0
    assert d["cccd_gan_nhieu_ho_ten"] == 1


def test_khong_co_ho_so_thi_khong_bia_so():
    kq = dh.tinh({})
    assert kq["h"]["thao_tac_thu_cong_tb"] is None
    assert kq["h"]["ty_le_tu_phuc_vu_pct"] is None
    assert kq["d"]["cccd_sai_dang_pct"] is None


def test_sql_chi_doc_va_khong_tra_du_lieu_dinh_danh():
    sql = dh.sql_baseline({}).lower()
    for tu in ("insert ", "update ", "delete ", "truncate ", "alter ", "drop "):
        assert tu not in sql
    # chỉ trả số đếm: không có cột định danh trong json_build_object đầu ra
    dau_ra = sql[sql.index("select json_build_object"):]
    for cot in ("'cccd'", "'ho_ten'", "'dien_thoai'", "'ma_ho_so'"):
        assert cot not in dau_ra


def test_bang_tuy_chon_chua_co_thi_dem_0():
    sql = dh.sql_baseline({"app_cap_phep.ocr_extractions": False})
    assert "'ocr_trich_xuat', 0" in sql
    sql = dh.sql_baseline({"app_cap_phep.ocr_extractions": True})
    assert "app_cap_phep.ocr_extractions" in sql

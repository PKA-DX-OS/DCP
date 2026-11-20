# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-DEMO-04: tính chỉ số tác động từ số liệu thô (không cần stack)."""

import importlib.util
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("impact_metrics", ROOT / "scripts/impact_metrics.py")
im = importlib.util.module_from_spec(spec)
spec.loader.exec_module(im)


def test_ngay_lam_viec_bo_cuoi_tuan_theo_gio_viet_nam():
    # Thứ Sáu 06/11/2026 -> thứ Hai 09/11/2026: 1 ngày làm việc
    assert im.ngay_lam_viec(datetime.fromisoformat("2026-11-06T09:00+07:00"), datetime.fromisoformat("2026-11-09T09:00+07:00")) == 1
    # 23:30 UTC thứ Năm 05/11 là sáng thứ Sáu 06/11 giờ Việt Nam
    assert im.ngay_lam_viec(datetime.fromisoformat("2026-11-05T23:30+00:00"), datetime.fromisoformat("2026-11-09T02:00+00:00")) == 1
    assert im.ngay_lam_viec(datetime.fromisoformat("2026-11-02T09:00+07:00"), datetime.fromisoformat("2026-11-02T17:00+07:00")) == 0


def test_tinh_chi_so_do_duoc():
    raw = {
        "tong_ho_so": 3, "da_dong": 2, "dong_dung_han": 1,
        "cap_phep": [
            {"nop": "2026-11-02T02:00:00+00:00", "han": "2026-11-11T10:00:00+00:00", "cap": "2026-11-06T03:00:00+00:00"},
            {"nop": "2026-11-02T02:00:00+00:00", "han": "2026-11-05T10:00:00+00:00", "cap": "2026-11-13T03:00:00+00:00"},
        ],
        "kiem_tra_quy_hoach": 4, "quy_hoach_khong_dat": 2, "ho_so_quy_hoach_khong_dat": 1,
        "tep_quet_virus": 10, "tep_nhiem_virus": 1, "ban_ve_da_danh_gia": 5, "van_ban_ky_so": 2,
        "moc_nghiem_thu": 3, "nghiem_thu_khong_dat": 1, "ho_so_tung_bo_sung": 1,
        "ho_so_co_thiet_ke": 1, "so_phien_ban_tb": "2.00",
    }
    d = im.tinh(raw)["do_duoc"]
    assert d["giay_phep_da_ky"] == 2
    assert d["thoi_gian_xu_ly_tb_ngay_lam_viec"] == 6.5  # 4 và 9 ngày làm việc
    assert d["thoi_gian_xu_ly_max_ngay_lam_viec"] == 9
    assert d["ty_le_ky_dung_han_pct"] == 50.0
    assert d["ty_le_dong_dung_han_pct"] == 50.0
    assert d["so_kiem_tra_tu_dong"] == 4 + 10 + 5 + 2 + 3
    assert d["so_vong_thiet_ke_tb"] == 2.0
    assert d["thoi_han_luat_ngay_lam_viec"] == 7


def test_khong_co_du_lieu_thi_khong_bia_so():
    kq = im.tinh({})
    d = kq["do_duoc"]
    assert d["thoi_gian_xu_ly_tb_ngay_lam_viec"] is None
    assert d["ty_le_ky_dung_han_pct"] is None
    assert d["ty_le_dong_dung_han_pct"] is None
    assert d["so_vong_thiet_ke_tb"] is None
    assert im._fmt(None) == "chưa có dữ liệu"


def test_gia_dinh_duoc_ghi_ro():
    gd = im.tinh({})["gia_dinh"]
    assert [g["chi_so"] for g in gd] == ["Giấy tờ giảm", "Mức độ hài lòng"]
    assert gd[1]["gia_tri"] == "chưa đo"
    for g in gd:
        assert "Giả định" in g["cach_gia_dinh"] or "Không có số liệu" in g["cach_gia_dinh"]


def test_thieu_bang_thi_null_va_ghi_ten_bang():
    kq = im.tinh({"tong_ho_so": 2, "tep_quet_virus": 3, "van_ban_ky_so": 1, "_thieu_bang": ["app_construction.moc_nghiem_thu"]})
    d = kq["do_duoc"]
    assert d["chi_tiet_kiem_tra"]["moc_nghiem_thu"] is None
    assert d["so_kiem_tra_tu_dong"] == 4
    assert d["ho_so_phat_hien_loi_quy_hoach_som"] is None
    assert kq["thieu_bang"] == ["app_construction.moc_nghiem_thu"]
    assert im.tinh({})["do_duoc"]["so_kiem_tra_tu_dong"] is None


def test_cau_sql_bo_chi_so_thieu_bang():
    co = {t: True for t in im.BANG_TUY_CHON}
    day_du = im.sql_chi_so(co)
    assert "app_construction.ket_qua_kiem_tra_quy_hoach" in day_du and "'_thieu_bang', '[]'::json" in day_du
    co["app_construction.ket_qua_kiem_tra_quy_hoach"] = False
    thieu = im.sql_chi_so(co)
    assert "FROM app_construction.ket_qua_kiem_tra_quy_hoach" not in thieu
    assert "'kiem_tra_quy_hoach', NULL" in thieu
    assert "json_build_array('app_construction.ket_qua_kiem_tra_quy_hoach')" in thieu

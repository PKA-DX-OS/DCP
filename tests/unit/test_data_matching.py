# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
D-MDM-02: Unit test thuật toán so khớp dữ liệu và sinh ứng viên trùng MDM.
"""

import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mdm_backfill", ROOT / "scripts/mdm_backfill.py")
mdm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mdm)


def test_chuan_hoa_chuoi():
    assert mdm.bo_dau_tieng_viet("Nguyễn Văn Tuấn") == "Nguyen Van Tuan"
    assert mdm.chuan_hoa_ten("  Lê   Thị Lan (mẫu) ") == "le thi lan (mau)"
    assert mdm.chuan_hoa_dien_thoai("+84 901 234 567") == "0901234567"
    assert mdm.chuan_hoa_dien_thoai("090.123.4567") == "0901234567"
    assert mdm.chuan_hoa_dia_chi("Số 12 đường Trần Phú, Phường A, Quận 1") == "12 tran phu a 1"


def test_so_khop_chu_the_trung_khop_cao():
    # Cùng số điện thoại, tên lệch dấu nhẹ (Nguyễn Văn Tuấn và Nguyen Van Tuan)
    ct1 = {
        "ho_ten": "Nguyễn Văn Tuấn",
        "dien_thoai": "0912345678",
        "dia_chi": "Số 1 đường Mẫu, phường A",
    }
    ct2 = {
        "ho_ten": "Nguyen Van Tuan",
        "dien_thoai": "0912345678",
        "dia_chi": "Số 1 đường Mẫu, phường A",
    }
    conf, ly_do = mdm.so_khop_chu_the(ct1, ct2)
    # Tên chuẩn hóa giống 100%, điện thoại giống 100%, địa chỉ giống 100% -> conf = 1.0 (exact)
    # Nếu tên có khác biệt nhẹ:
    ct3 = {
        "ho_ten": "Nguyễn Văn Tuấn Anh",
        "dien_thoai": "0912345678",
        "dia_chi": "Số 1 Mẫu, phường A",
    }
    conf3, ly_do3 = mdm.so_khop_chu_the(ct1, ct3)
    assert 0.70 <= conf3 < 1.0
    assert "ho_ten" in ly_do3
    assert "dien_thoai" in ly_do3


def test_so_khop_chu_the_khac_nhau():
    # Hai người hoàn toàn khác nhau
    ct1 = {
        "ho_ten": "Trần Văn Minh",
        "dien_thoai": "0901234567",
        "dia_chi": "Số 10 đường A",
    }
    ct2 = {
        "ho_ten": "Lê Thị Lan",
        "dien_thoai": "0988776655",
        "dia_chi": "Số 200 đường B",
    }
    conf, ly_do = mdm.so_khop_chu_the(ct1, ct2)
    assert conf < 0.70
    assert ly_do == []


def test_so_khop_thua_dat():
    # Cùng số thửa nhưng khác tờ bản đồ, cùng địa chỉ
    td1 = {"so_thua": "125", "to_ban_do": "18", "dia_chi": "Số 125 đường A"}
    td2 = {"so_thua": "125", "to_ban_do": "18a", "dia_chi": "Số 125 đường A"}
    conf, ly_do = mdm.so_khop_thua_dat(td1, td2)
    assert 0.75 <= conf < 1.0
    assert "thua_dat" in ly_do

    # Khác số thửa
    td3 = {"so_thua": "126", "to_ban_do": "18", "dia_chi": "Số 125 đường A"}
    conf3, ly_do3 = mdm.so_khop_thua_dat(td1, td3)
    assert conf3 == 0.0
    assert ly_do3 == []


def test_so_khop_cong_trinh():
    # Cùng thửa đất gắn liền nhưng mã công trình khác
    ct1 = {"parcel_id": "00000000-0000-4000-8000-000000000001", "ma_cong_trinh": "CT-01", "dia_chi": "Số 10 đường A"}
    ct2 = {"parcel_id": "00000000-0000-4000-8000-000000000001", "ma_cong_trinh": "CT-02", "dia_chi": "Số 10 đường A"}
    conf, ly_do = mdm.so_khop_cong_trinh(ct1, ct2)
    assert 0.75 <= conf < 1.0
    assert "dia_chi" in ly_do

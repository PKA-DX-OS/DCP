# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit test kiểm tra parser trích xuất 3 loại giấy tờ (D-OCR, Gate 3, FIX-V11-29)."""

from ocr.parser import parse_cccd, parse_don_de_nghi, parse_giay_chung_nhan, parse_document


def test_parse_cccd():
    raw_sample = """
    CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
    Độc lập - Tự do - Hạnh phúc
    CĂN CƯỚC CÔNG DÂN / IDENTITY CARD
    Số / No.: 001099001234
    Họ và tên / Full name: NGUYỄN VĂN AN
    Ngày sinh / Date of birth: 15/08/1985
    Giới tính / Sex: Nam
    Quê quán / Place of origin: Phường Kim Mã, Ba Đình, Hà Nội
    Nơi thường trú / Place of residence: Số 12 phố Liễu Giai, phường Liễu Giai, Ba Đình, Hà Nội
    """
    fields, conf = parse_cccd(raw_sample)
    d = {f["name"]: f["value"] for f in fields}

    assert d["so_cccd"] == "001099001234"
    assert "NGUYỄN VĂN AN" in d["ho_ten"]
    assert d["ngay_sinh"] == "15/08/1985"
    assert d["gioi_tinh"] == "Nam"
    assert "Liễu Giai" in d["dia_chi"]
    assert conf >= 0.8
    assert all("confidence" in f for f in fields)
    assert all("page" in f for f in fields)


def test_parse_giay_chung_nhan_qsdd():
    raw_sample = """
    CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
    GIẤY CHỨNG NHẬN QUYỀN SỬ DỤNG ĐẤT, QUYỀN SỞ HỮU NHÀ Ở
    Số phát hành: BD 123456
    I. Người sử dụng đất: TRẦN THỊ BÌNH
    II. Thửa đất:
    Thửa đất số: 105
    Tờ bản đồ số: 12
    Địa chỉ thửa đất: Tổ 4, phường Liễu Giai, quận Ba Đình, Hà Nội
    Diện tích: 120.5 m2
    Hà Nội, ngày 20 tháng 10 năm 2023
    """
    fields, conf = parse_giay_chung_nhan(raw_sample)
    d = {f["name"]: f["value"] for f in fields}

    assert "BD 123456" in d["so_giay_chung_nhan"]
    assert d["so_thua"] == "105"
    assert d["to_ban_do"] == "12"
    assert d["dien_tich_m2"] == "120.5"
    assert "Liễu Giai" in d["dia_chi"]
    assert d["ngay_cap"] == "20/10/2023"
    assert conf >= 0.8


def test_parse_don_de_nghi_cap_phep():
    raw_sample = """
    CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
    ĐƠN ĐỀ NGHỊ CẤP GIẤY PHÉP XÂY DỰNG
    1. Tên chủ đầu tư: LÊ VĂN CƯỜNG
    Số CCCD: 001285009876
    Địa chỉ liên hệ: Số 25 ngõ 10 đường Hoàng Hoa Thám, Ba Đình, Hà Nội
    2. Địa điểm xây dựng công trình: Thửa đất số 88, tờ bản đồ 05, phường Liễu Giai
    Diện tích xây dựng: 85.0 m2
    Số tầng: 4
    """
    fields, conf = parse_don_de_nghi(raw_sample)
    d = {f["name"]: f["value"] for f in fields}

    assert "LÊ VĂN CƯỜNG" in d["ho_ten"]
    assert d["so_cccd"] == "001285009876"
    assert "Hoàng Hoa Thám" in d["dia_chi"]
    assert "Thửa đất số 88" in d["dia_diem_xay_dung"]
    assert d["dien_tich_m2"] == "85.0"
    assert d["so_tang"] == "4"
    assert conf >= 0.8


def test_parse_document_dispatcher():
    f_cccd, _ = parse_document("CCCD: 001099001234\nHọ tên: NGUYEN VAN A", "cccd")
    assert any(f["name"] == "so_cccd" for f in f_cccd)

    f_invalid, conf_invalid = parse_document("khong co gi", "loai_khong_hop_le")
    assert f_invalid == []
    assert conf_invalid == 0.0


def test_parse_giay_chung_nhan_loi_dau_ocr():
    """FIX-V11-29: Kiểm tra trích xuất GCN QSDĐ khi OCR đọc sai dấu/ký tự."""
    raw_ocr_error = """Ngusi st dung dét: NGUYEN VAN MAU
Thtra dat s6: 12
To ban dé sé: 4
Dién tich: 85.5 m2
Dia chi thita dat: S6 1 Dudng Mau
ngay 15 thang 3 nam 2020"""

    fields, conf = parse_giay_chung_nhan(raw_ocr_error)
    d = {f["name"]: f["value"] for f in fields}
    confs = {f["name"]: f["confidence"] for f in fields}

    # Đạt khi đọc được ít nhất 5/7 trường
    tim_thay = [f["name"] for f in fields if f["value"] is not None]
    assert len(tim_thay) >= 5, f"Chỉ tìm thấy {len(tim_thay)}/7 trường: {tim_thay}"

    assert d["ho_ten"] == "NGUYEN VAN MAU"
    assert d["so_thua"] == "12"
    assert d["to_ban_do"] == "4"
    assert d["dien_tich_m2"] == "85.5"
    assert "Dudng Mau" in d["dia_chi"]
    assert d["ngay_cap"] == "15/03/2020"

    # Kiểm tra trường khớp mờ có độ tin cậy được nhân 0.8 (ví dụ so_thua: 0.92 * 0.8 = 0.736)
    assert confs["so_thua"] <= 0.8
    assert confs["so_thua"] == round(0.92 * 0.8, 3)


def test_parse_cccd_khong_nhan_tieng_anh_loi_dau():
    """FIX-V11-29: Kiểm tra trích xuất CCCD khi bỏ nhãn tiếng Anh và OCR lỗi dấu."""
    raw_cccd_viet = """CONG HOA XA HOI CHU NGHIA VIET NAM
Doc lap - Tu do - Hanh phuc
CAN CUOC CONG DAN
S6: 001099001234
H9 va ten: NGUYEN VAN AN
Ngay sinh: 15/08/1985
Gi6i tinh: Nam
Que quan: Kim Ma, Ba Dinh, Ha Noi
Ndi thudng tru: So 12 pho Lieu Giai, phuong Lieu Giai, Ba Dinh, Ha Noi"""

    fields, conf = parse_cccd(raw_cccd_viet)
    d = {f["name"]: f["value"] for f in fields}
    confs = {f["name"]: f["confidence"] for f in fields}

    # Đạt khi đọc được ít nhất 5/6 trường
    tim_thay = [f["name"] for f in fields if f["value"] is not None]
    assert len(tim_thay) >= 5, f"Chỉ tìm thấy {len(tim_thay)}/6 trường: {tim_thay}"

    assert d["so_cccd"] == "001099001234"
    assert d["ho_ten"] == "NGUYEN VAN AN"
    assert d["ngay_sinh"] == "15/08/1985"
    assert d["gioi_tinh"] == "Nam"
    assert "Kim Ma" in d["que_quan"]
    assert "Lieu Giai" in d["dia_chi"]

    # Độ tin cậy trường khớp mờ được nhân 0.8 (<= 0.8)
    assert confs["so_cccd"] <= 0.8
    assert confs["ho_ten"] <= 0.8

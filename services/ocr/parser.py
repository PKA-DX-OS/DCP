# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""D-OCR: Parser trích xuất các trường từ văn bản giấy tờ (CCCD, đất đai, đơn đề nghị)."""

import re
from typing import Any, Dict, List, Optional, Tuple


def _tim_regex(pattern: str, text: str, group: int = 1) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return m.group(group).strip() if m else None


def parse_cccd(text: str) -> Tuple[List[Dict[str, Any]], float]:
    """Trích xuất thông tin Căn cước công dân (12 số)."""
    fields: List[Dict[str, Any]] = []

    # 1. Số CCCD: 12 chữ số, bắt đầu bằng 0
    so_cccd = _tim_regex(r"(?:Số|No\.?|Identity card No\.?|CCCD)?:?\s*\b(0\d{11})\b", text)
    if not so_cccd:
        so_cccd = _tim_regex(r"\b(0\d{11})\b", text)
    fields.append({
        "name": "so_cccd",
        "value": so_cccd,
        "confidence": 0.95 if so_cccd else 0.0,
        "page": 1,
        "bbox": [0.35, 0.28, 0.40, 0.06] if so_cccd else None,
        "edited": False,
    })

    # 2. Họ và tên
    ho_ten = _tim_regex(r"(?:Họ và tên\s*/\s*Full name|Họ và tên|HỌ VÀ TÊN|Full name)[\s/:]+([^\n\r]+)", text)
    if not ho_ten:
        ho_ten = _tim_regex(r"Họ tên:?\s*([A-Za-zÀ-ỹ\s]{3,40})", text)
    fields.append({
        "name": "ho_ten",
        "value": ho_ten.strip() if ho_ten else None,
        "confidence": 0.90 if ho_ten else 0.0,
        "page": 1,
        "bbox": [0.35, 0.35, 0.50, 0.06] if ho_ten else None,
        "edited": False,
    })

    # 3. Ngày sinh
    ngay_sinh = _tim_regex(r"(?:Ngày sinh\s*/\s*Date of birth|Ngày sinh|Date of birth)[\s/:]+(\d{1,2}/\d{1,2}/\d{4})", text)
    fields.append({
        "name": "ngay_sinh",
        "value": ngay_sinh,
        "confidence": 0.90 if ngay_sinh else 0.0,
        "page": 1,
        "bbox": [0.35, 0.42, 0.30, 0.05] if ngay_sinh else None,
        "edited": False,
    })

    # 4. Giới tính
    gioi_tinh = _tim_regex(r"(?:Giới tính\s*/\s*Sex|Giới tính|Sex)[\s/:]+(Nam|Nữ|Male|Female)", text)
    fields.append({
        "name": "gioi_tinh",
        "value": gioi_tinh,
        "confidence": 0.85 if gioi_tinh else 0.0,
        "page": 1,
        "bbox": [0.35, 0.48, 0.15, 0.05] if gioi_tinh else None,
        "edited": False,
    })

    # 5. Quê quán
    que_quan = _tim_regex(r"(?:Quê quán\s*/\s*Place of origin|Quê quán|Place of origin)[\s/:]+([^\n\r]+)", text)
    fields.append({
        "name": "que_quan",
        "value": que_quan,
        "confidence": 0.85 if que_quan else 0.0,
        "page": 1,
        "bbox": [0.35, 0.55, 0.60, 0.08] if que_quan else None,
        "edited": False,
    })

    # 6. Địa chỉ thường trú
    dia_chi = _tim_regex(r"(?:Nơi thường trú\s*/\s*Place of residence|Nơi thường trú|Place of residence|Thường trú)[\s/:]+([^\n\r]+)", text)
    fields.append({
        "name": "dia_chi",
        "value": dia_chi,
        "confidence": 0.85 if dia_chi else 0.0,
        "page": 1,
        "bbox": [0.35, 0.64, 0.60, 0.10] if dia_chi else None,
        "edited": False,
    })

    # Tính độ tin cậy trung bình các trường
    valid = [f["confidence"] for f in fields if f["value"]]
    avg_conf = round(sum(valid) / len(fields), 3) if valid else 0.0
    return fields, avg_conf


def parse_giay_chung_nhan(text: str) -> Tuple[List[Dict[str, Any]], float]:
    """Trích xuất thông tin Giấy chứng nhận quyền sử dụng đất."""
    fields: List[Dict[str, Any]] = []

    # 1. Số giấy chứng nhận / Số phát hành
    so_gcn = _tim_regex(r"(?:Số phát hành|Số seri|Số vào sổ|Số GCN|Số)[\s/:]+([A-Z0-9\s/-]{4,20})", text)
    if not so_gcn:
        so_gcn = _tim_regex(r"\b([A-Z]{2}\s*\d{6})\b", text)
    fields.append({
        "name": "so_giay_chung_nhan",
        "value": so_gcn,
        "confidence": 0.90 if so_gcn else 0.0,
        "page": 1,
        "bbox": [0.70, 0.08, 0.25, 0.05] if so_gcn else None,
        "edited": False,
    })

    # 2. Số thửa
    so_thua = _tim_regex(r"(?:Thửa đất số|Số thửa|Thửa đất)[\s/:]+(\d+)", text)
    fields.append({
        "name": "so_thua",
        "value": so_thua,
        "confidence": 0.92 if so_thua else 0.0,
        "page": 2,
        "bbox": [0.20, 0.22, 0.15, 0.05] if so_thua else None,
        "edited": False,
    })

    # 3. Tờ bản đồ
    to_ban_do = _tim_regex(r"(?:Tờ bản đồ số|Tờ bản đồ)[\s/:]+(\d+)", text)
    fields.append({
        "name": "to_ban_do",
        "value": to_ban_do,
        "confidence": 0.92 if to_ban_do else 0.0,
        "page": 2,
        "bbox": [0.50, 0.22, 0.15, 0.05] if to_ban_do else None,
        "edited": False,
    })

    # 4. Diện tích
    dien_tich = _tim_regex(r"(?:Diện tích|Diện tích đất)[\s/:]+([\d\.,]+)\s*(?:m2|m²)?", text)
    fields.append({
        "name": "dien_tich_m2",
        "value": dien_tich,
        "confidence": 0.88 if dien_tich else 0.0,
        "page": 2,
        "bbox": [0.20, 0.28, 0.25, 0.05] if dien_tich else None,
        "edited": False,
    })

    # 5. Địa chỉ thửa đất
    dia_chi = _tim_regex(r"(?:Địa chỉ thửa đất|Địa chỉ)[\s/:]+([^\n\r]+)", text)
    fields.append({
        "name": "dia_chi",
        "value": dia_chi,
        "confidence": 0.85 if dia_chi else 0.0,
        "page": 2,
        "bbox": [0.20, 0.35, 0.70, 0.06] if dia_chi else None,
        "edited": False,
    })

    # 6. Người sử dụng đất / Chủ sở hữu
    ho_ten = _tim_regex(r"(?:Người sử dụng đất|Chủ sở hữu|Ông|Bà|Ông/Bà)[\s/:]+([A-ZÀ-Ỹ\s]{3,40})", text)
    fields.append({
        "name": "ho_ten",
        "value": ho_ten.strip() if ho_ten else None,
        "confidence": 0.85 if ho_ten else 0.0,
        "page": 1,
        "bbox": [0.20, 0.18, 0.60, 0.05] if ho_ten else None,
        "edited": False,
    })

    # 7. Ngày cấp
    ngay_cap = _tim_regex(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", text)
    ngay_cap_val = None
    if ngay_cap:
        m_ngay = re.search(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", text, re.I)
        if m_ngay:
            d, m, y = m_ngay.groups()
            ngay_cap_val = f"{int(d):02d}/{int(m):02d}/{y}"
    else:
        ngay_cap_val = _tim_regex(r"(?:Ngày cấp)[\s/:]+(\d{1,2}/\d{1,2}/\d{4})", text)

    fields.append({
        "name": "ngay_cap",
        "value": ngay_cap_val,
        "confidence": 0.85 if ngay_cap_val else 0.0,
        "page": 2,
        "bbox": [0.60, 0.85, 0.30, 0.05] if ngay_cap_val else None,
        "edited": False,
    })

    valid = [f["confidence"] for f in fields if f["value"]]
    avg_conf = round(sum(valid) / len(fields), 3) if valid else 0.0
    return fields, avg_conf


def parse_don_de_nghi(text: str) -> Tuple[List[Dict[str, Any]], float]:
    """Trích xuất thông tin Đơn đề nghị cấp giấy phép xây dựng."""
    fields: List[Dict[str, Any]] = []

    # 1. Tên chủ đầu tư / Người đề nghị
    ho_ten = _tim_regex(r"(?:Tên chủ đầu tư|Người đề nghị|Tôi là|Chủ đầu tư)[\s/:]+([A-ZÀ-Ỹa-zà-ỹ\s]{3,40})", text)
    fields.append({
        "name": "ho_ten",
        "value": ho_ten.strip() if ho_ten else None,
        "confidence": 0.90 if ho_ten else 0.0,
        "page": 1,
        "bbox": [0.25, 0.20, 0.60, 0.05] if ho_ten else None,
        "edited": False,
    })

    # 2. Số CCCD
    so_cccd = _tim_regex(r"(?:CCCD|Số CCCD|Số CMND|Số định danh)[\s/:]*\b(0\d{11})\b", text)
    if not so_cccd:
        so_cccd = _tim_regex(r"\b(0\d{11})\b", text)
    fields.append({
        "name": "so_cccd",
        "value": so_cccd,
        "confidence": 0.92 if so_cccd else 0.0,
        "page": 1,
        "bbox": [0.25, 0.26, 0.35, 0.05] if so_cccd else None,
        "edited": False,
    })

    # 3. Địa chỉ liên hệ
    dia_chi = _tim_regex(r"(?:Địa chỉ liên hệ|Nơi ở hiện nay|Địa chỉ)[\s/:]+([^\n\r]+)", text)
    fields.append({
        "name": "dia_chi",
        "value": dia_chi,
        "confidence": 0.85 if dia_chi else 0.0,
        "page": 1,
        "bbox": [0.25, 0.32, 0.65, 0.05] if dia_chi else None,
        "edited": False,
    })

    # 4. Địa điểm xây dựng công trình
    dia_diem = _tim_regex(r"(?:Địa điểm xây dựng|Địa điểm xây dựng công trình)[\s/:]+([^\n\r]+)", text)
    fields.append({
        "name": "dia_diem_xay_dung",
        "value": dia_diem,
        "confidence": 0.88 if dia_diem else 0.0,
        "page": 1,
        "bbox": [0.25, 0.40, 0.65, 0.06] if dia_diem else None,
        "edited": False,
    })

    # 5. Diện tích xây dựng / diện tích sàn
    dien_tich = _tim_regex(r"(?:Diện tích xây dựng|Diện tích sàn|Diện tích)[\s/:]+([\d\.,]+)\s*(?:m2|m²)?", text)
    fields.append({
        "name": "dien_tich_m2",
        "value": dien_tich,
        "confidence": 0.85 if dien_tich else 0.0,
        "page": 1,
        "bbox": [0.25, 0.48, 0.25, 0.05] if dien_tich else None,
        "edited": False,
    })

    # 6. Số tầng
    so_tang = _tim_regex(r"(?:Số tầng|Chiều cao tầng)[\s/:]+(\d+)", text)
    fields.append({
        "name": "so_tang",
        "value": so_tang,
        "confidence": 0.85 if so_tang else 0.0,
        "page": 1,
        "bbox": [0.25, 0.54, 0.15, 0.05] if so_tang else None,
        "edited": False,
    })

    valid = [f["confidence"] for f in fields if f["value"]]
    avg_conf = round(sum(valid) / len(fields), 3) if valid else 0.0
    return fields, avg_conf


def parse_document(text: str, doc_type: str) -> Tuple[List[Dict[str, Any]], float]:
    """Tách trường theo loại giấy tờ được chỉ định."""
    if doc_type == "cccd":
        return parse_cccd(text)
    elif doc_type == "giay_chung_nhan_qsdd":
        return parse_giay_chung_nhan(text)
    elif doc_type == "don_de_nghi_cap_phep":
        return parse_don_de_nghi(text)
    else:
        return [], 0.0

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""D-OCR: Parser trích xuất các trường từ văn bản giấy tờ (CCCD, đất đai, đơn đề nghị).

- Chuẩn hóa văn bản về NFC; so khớp nhãn không phân biệt dấu (NFD, đ->d) và không phân biệt hoa/thường.
- Giá trị trả về lấy theo vị trí trên văn bản gốc có dấu.
- Nới mẫu cho lỗi OCR thường gặp: 6/o, 0/o, 1/l, mất dấu hai chấm ':'.
- Khi phải khớp mờ, độ tin cậy được nhân 0.8 để hỗ trợ lọc hàng chờ duyệt <= 80%.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple


def bo_dau(text: str) -> str:
    """Bỏ dấu tiếng Việt, chuyển đ/Đ thành d/D, giữ nguyên độ dài chuỗi ký tự so với NFC."""
    nfc = unicodedata.normalize("NFC", text)
    no_diac = "".join(c for c in unicodedata.normalize("NFD", nfc) if unicodedata.category(c) != "Mn")
    return no_diac.replace("đ", "d").replace("Đ", "D")


def _lam_sach_so(val: str) -> str:
    """Chuyển các ký tự hay bị OCR đọc nhầm trong số: o/O -> 0, l/I -> 1."""
    return val.replace("o", "0").replace("O", "0").replace("l", "1").replace("I", "1")


def _tim_truong(
    text_nfc: str,
    text_nodiac: str,
    pattern_chuan: Optional[str],
    pattern_fuzzy: str,
    base_conf: float,
    group: int = 1,
    chuan_hoa_so: bool = False,
) -> Tuple[Optional[str], float]:
    """Tìm trường theo mẫu chuẩn trước; nếu không thấy thì dùng mẫu nới lỏng (khớp mờ)."""
    # 1. Thử khớp chuẩn trên văn bản gốc NFC
    if pattern_chuan:
        m_chuan = re.search(pattern_chuan, text_nfc, re.IGNORECASE | re.MULTILINE)
        if m_chuan:
            val = m_chuan.group(group).strip()
            if chuan_hoa_so:
                val = _lam_sach_so(val)
            return val, base_conf

    # 2. Thử khớp mờ trên text_nodiac, lấy vị trí để cắt từ text_nfc (giữ nguyên dấu)
    m_fuzzy = re.search(pattern_fuzzy, text_nodiac, re.IGNORECASE | re.MULTILINE)
    if m_fuzzy:
        start, end = m_fuzzy.span(group)
        val = text_nfc[start:end].strip()
        if chuan_hoa_so:
            val = _lam_sach_so(val)
        # Khớp mờ -> nhân độ tin cậy với 0.8
        fuzzy_conf = round(base_conf * 0.8, 3)
        return val, fuzzy_conf

    return None, 0.0


def parse_cccd(text: str) -> Tuple[List[Dict[str, Any]], float]:
    """Trích xuất thông tin Căn cước công dân (12 số)."""
    text_nfc = unicodedata.normalize("NFC", text)
    text_nodiac = bo_dau(text_nfc).lower()

    fields: List[Dict[str, Any]] = []

    # 1. Số CCCD: 12 chữ số
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Số|No\.?|Identity card No\.?|CCCD)[\s/:]+\b(0\d{11})\b",
        pattern_fuzzy=r"(?:s[a-z0-9]*|no\.?|cccd|so\s*cccd|identity|card|dinh\s*danh)[\s/:-]*\b([0o][0-9ol]{11})\b|\b([0o][0-9ol]{11})\b",
        base_conf=0.95,
        group=1,
        chuan_hoa_so=True,
    )
    if not val:
        m = re.search(r"\b([0o][0-9ol]{11})\b", text_nodiac)
        if m:
            val = _lam_sach_so(text_nfc[m.start(1):m.end(1)].strip())
            conf = round(0.95 * 0.8, 3)

    fields.append({
        "name": "so_cccd",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.35, 0.28, 0.40, 0.06] if val else None,
        "edited": False,
    })

    # 2. Họ và tên
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Họ và tên\s*/\s*Full name|Họ và tên|HỌ VÀ TÊN|Full name)[\s/:]+([^\n\r]+)",
        pattern_fuzzy=r"(?:h[a-z0-9]*\s*v[a-z0-9]*\s*t[eé][a-z0-9]*|h[a-z0-9]*\s*t[eé][a-z0-9]*|full\s*name)[:\s/]*([^\n\r]+)",
        base_conf=0.90,
    )
    fields.append({
        "name": "ho_ten",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.35, 0.35, 0.50, 0.06] if val else None,
        "edited": False,
    })

    # 3. Ngày sinh
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Ngày sinh\s*/\s*Date of birth|Ngày sinh|Date of birth)[\s/:]+(\d{1,2}/\d{1,2}/\d{4})",
        pattern_fuzzy=r"(?:ng[a-z0-9]*\s*s[a-z0-9]*|date\s*of\s*birth)[:\s/]*([0-9ol]{1,2}/[0-9ol]{1,2}/[0-9ol]{4})",
        base_conf=0.90,
        chuan_hoa_so=True,
    )
    fields.append({
        "name": "ngay_sinh",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.35, 0.42, 0.30, 0.05] if val else None,
        "edited": False,
    })

    # 4. Giới tính
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Giới tính\s*/\s*Sex|Giới tính|Sex)[\s/:]+(Nam|Nữ|Male|Female)",
        pattern_fuzzy=r"(?:gi[a-z0-9]*\s*t[a-z0-9]*|sex)[:\s/]*([^\n\r]+)",
        base_conf=0.85,
    )
    fields.append({
        "name": "gioi_tinh",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.35, 0.48, 0.15, 0.05] if val else None,
        "edited": False,
    })

    # 5. Quê quán
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Quê quán\s*/\s*Place of origin|Quê quán|Place of origin)[\s/:]+([^\n\r]+)",
        pattern_fuzzy=r"(?:qu[a-z0-9]*\s*qu[a-z0-9]*|place\s*of\s*origin)[:\s/]*([^\n\r]+)",
        base_conf=0.85,
    )
    fields.append({
        "name": "que_quan",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.35, 0.55, 0.60, 0.08] if val else None,
        "edited": False,
    })

    # 6. Địa chỉ thường trú
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Nơi thường trú\s*/\s*Place of residence|Nơi thường trú|Place of residence|Thường trú)[\s/:]+([^\n\r]+)",
        pattern_fuzzy=r"(?:n[a-z0-9]*\s*th[a-z0-9]*\s*tr[a-z0-9]*|th[a-z0-9]*\s*tr[a-z0-9]*|place\s*of\s*residence|dia\s*chi)[:\s/]*([^\n\r]+)",
        base_conf=0.85,
    )
    fields.append({
        "name": "dia_chi",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.35, 0.64, 0.60, 0.10] if val else None,
        "edited": False,
    })

    valid = [f["confidence"] for f in fields if f["value"]]
    avg_conf = round(sum(valid) / len(fields), 3) if valid else 0.0
    return fields, avg_conf


def parse_giay_chung_nhan(text: str) -> Tuple[List[Dict[str, Any]], float]:
    """Trích xuất thông tin Giấy chứng nhận quyền sử dụng đất."""
    text_nfc = unicodedata.normalize("NFC", text)
    text_nodiac = bo_dau(text_nfc).lower()

    fields: List[Dict[str, Any]] = []

    # 1. Số giấy chứng nhận / Số phát hành
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Số phát hành|Số seri|Số vào sổ|Số GCN)[\s/:]+([A-Z0-9\s/-]{4,20})|\b([A-Z]{2}\s*\d{6})\b",
        pattern_fuzzy=r"(?:s[o06]\s*ph[a-z0-9]*\s*h[a-z0-9]*|s[o06]\s*seri|s[o06]\s*vao\s*s[o06]|s[o06]\s*gcn|s[o06])[:\s-]*([A-Z0-9\s/-]{4,20})|\b([A-Z]{2}\s*[0-9ol]{6})\b",
        base_conf=0.90,
    )
    fields.append({
        "name": "so_giay_chung_nhan",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.70, 0.08, 0.25, 0.05] if val else None,
        "edited": False,
    })

    # 2. Số thửa
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Thửa đất số|Số thửa)[\s/:]+(\d+)",
        pattern_fuzzy=r"(?:th[a-z0-9]*\s*d[a-z0-9]*(?:\s*s[a-z0-9]*)?|s[a-z0-9]*\s*th[a-z0-9]*)[:\s-]*([0-9ol]+)",
        base_conf=0.92,
        chuan_hoa_so=True,
    )
    fields.append({
        "name": "so_thua",
        "value": val,
        "confidence": conf,
        "page": 2,
        "bbox": [0.20, 0.22, 0.15, 0.05] if val else None,
        "edited": False,
    })

    # 3. Tờ bản đồ
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Tờ bản đồ số|Tờ bản đồ)[\s/:]+(\d+)",
        pattern_fuzzy=r"(?:t[o0]\s*b[a-z0-9]*\s*d[a-z0-9]*(?:\s*s[a-z0-9]*)?)[:\s-]*([0-9ol]+)",
        base_conf=0.92,
        chuan_hoa_so=True,
    )
    fields.append({
        "name": "to_ban_do",
        "value": val,
        "confidence": conf,
        "page": 2,
        "bbox": [0.50, 0.22, 0.15, 0.05] if val else None,
        "edited": False,
    })

    # 4. Diện tích
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Diện tích|Diện tích đất)[\s/:]+([\d\.,]+)\s*(?:m2|m²)?",
        pattern_fuzzy=r"(?:di[a-z0-9]*\s*t[a-z0-9]*(?:\s*d[a-z0-9]*)?)[:\s-]*([0-9ol\.,]+)\s*(?:m[2²])?",
        base_conf=0.88,
        chuan_hoa_so=True,
    )
    fields.append({
        "name": "dien_tich_m2",
        "value": val,
        "confidence": conf,
        "page": 2,
        "bbox": [0.20, 0.28, 0.25, 0.05] if val else None,
        "edited": False,
    })

    # 5. Địa chỉ thửa đất
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Địa chỉ thửa đất|Địa chỉ)[\s/:]+([^\n\r]+)",
        pattern_fuzzy=r"(?:di[a-z0-9]*\s*ch[a-z0-9]*(?:\s*th[a-z0-9]*\s*d[a-z0-9]*)?)[:\s-]*([^\n\r]+)",
        base_conf=0.85,
    )
    fields.append({
        "name": "dia_chi",
        "value": val,
        "confidence": conf,
        "page": 2,
        "bbox": [0.20, 0.35, 0.70, 0.06] if val else None,
        "edited": False,
    })

    # 6. Người sử dụng đất / Chủ sở hữu
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Người sử dụng đất|Chủ sở hữu|Ông|Bà|Ông/Bà)[\s/:]+([A-ZÀ-Ỹ\s]{3,40})",
        pattern_fuzzy=r"(?:ngu[a-z0-9]*\s*s[a-z0-9]*\s*dung\s*d[a-z0-9]*|chu\s*s[a-z0-9]*\s*h[a-z0-9]*|ong\s*/\s*ba|ong|ba)[:\s-]*([^\n\r]+)",
        base_conf=0.85,
    )
    fields.append({
        "name": "ho_ten",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.20, 0.18, 0.60, 0.05] if val else None,
        "edited": False,
    })

    # 7. Ngày cấp
    m_ngay_chuan = re.search(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", text_nfc, re.I)
    if m_ngay_chuan:
        d, m, y = m_ngay_chuan.groups()
        val_ngay = f"{int(d):02d}/{int(m):02d}/{y}"
        conf_ngay = 0.85
    else:
        m_ngay_fuzzy = re.search(r"ng[a-z0-9]*\s+([0-9ol]+)\s+th[a-z0-9]*\s+([0-9ol]+)\s+n[a-z0-9]*\s+([0-9ol]{4})", text_nodiac, re.I)
        if m_ngay_fuzzy:
            d = _lam_sach_so(m_ngay_fuzzy.group(1))
            m = _lam_sach_so(m_ngay_fuzzy.group(2))
            y = _lam_sach_so(m_ngay_fuzzy.group(3))
            try:
                val_ngay = f"{int(d):02d}/{int(m):02d}/{int(y)}"
                conf_ngay = round(0.85 * 0.8, 3)
            except ValueError:
                val_ngay = None
                conf_ngay = 0.0
        else:
            val_ngay, conf_ngay = _tim_truong(
                text_nfc,
                text_nodiac,
                pattern_chuan=r"(?:Ngày cấp)[\s/:]+(\d{1,2}/\d{1,2}/\d{4})",
                pattern_fuzzy=r"(?:ng[a-z0-9]*\s*c[a-z0-9]*)[:\s-]*([0-9ol]{1,2}/[0-9ol]{1,2}/[0-9ol]{4})",
                base_conf=0.85,
                chuan_hoa_so=True,
            )

    fields.append({
        "name": "ngay_cap",
        "value": val_ngay,
        "confidence": conf_ngay,
        "page": 2,
        "bbox": [0.60, 0.85, 0.30, 0.05] if val_ngay else None,
        "edited": False,
    })

    valid = [f["confidence"] for f in fields if f["value"]]
    avg_conf = round(sum(valid) / len(fields), 3) if valid else 0.0
    return fields, avg_conf


def parse_don_de_nghi(text: str) -> Tuple[List[Dict[str, Any]], float]:
    """Trích xuất thông tin Đơn đề nghị cấp giấy phép xây dựng."""
    text_nfc = unicodedata.normalize("NFC", text)
    text_nodiac = bo_dau(text_nfc).lower()

    fields: List[Dict[str, Any]] = []

    # 1. Tên chủ đầu tư / Người đề nghị
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Tên chủ đầu tư|Người đề nghị|Tôi là|Chủ đầu tư)[\s/:]+([A-ZÀ-Ỹa-zà-ỹ\s]{3,40})",
        pattern_fuzzy=r"(?:t[a-z0-9]*\s*chu\s*d[a-z0-9]*\s*t[a-z0-9]*|ngu[a-z0-9]*\s*d[a-z0-9]*\s*ngh[a-z0-9]*|t[a-z0-9]*\s*l[a-z0-9]*|chu\s*d[a-z0-9]*\s*t[a-z0-9]*)[:\s-]*([^\n\r]+)",
        base_conf=0.90,
    )
    fields.append({
        "name": "ho_ten",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.25, 0.20, 0.60, 0.05] if val else None,
        "edited": False,
    })

    # 2. Số CCCD
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:CCCD|Số CCCD|Số CMND|Số định danh)[\s/:]+\b(0\d{11})\b",
        pattern_fuzzy=r"(?:cccd|s[a-z0-9]*\s*cccd|s[a-z0-9]*\s*cmnd|s[a-z0-9]*\s*d[a-z0-9]*)[:\s-]*\b([0o][0-9ol]{11})\b|\b([0o][0-9ol]{11})\b",
        base_conf=0.92,
        chuan_hoa_so=True,
    )
    fields.append({
        "name": "so_cccd",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.25, 0.26, 0.35, 0.05] if val else None,
        "edited": False,
    })

    # 3. Địa chỉ liên hệ
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Địa chỉ liên hệ|Nơi ở hiện nay|Địa chỉ)[\s/:]+([^\n\r]+)",
        pattern_fuzzy=r"(?:di[a-z0-9]*\s*ch[a-z0-9]*\s*li[a-z0-9]*\s*h[a-z0-9]*|n[a-z0-9]*\s*[o0]\s*hi[a-z0-9]*\s*nay|di[a-z0-9]*\s*ch[a-z0-9]*)[:\s-]*([^\n\r]+)",
        base_conf=0.85,
    )
    fields.append({
        "name": "dia_chi",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.25, 0.32, 0.65, 0.05] if val else None,
        "edited": False,
    })

    # 4. Địa điểm xây dựng công trình
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Địa điểm xây dựng|Địa điểm xây dựng công trình)[\s/:]+([^\n\r]+)",
        pattern_fuzzy=r"(?:di[a-z0-9]*\s*di[a-z0-9]*\s*x[a-z0-9]*\s*d[a-z0-9]*(?:\s*c[a-z0-9]*\s*tr[a-z0-9]*)?)[:\s-]*([^\n\r]+)",
        base_conf=0.88,
    )
    fields.append({
        "name": "dia_diem_xay_dung",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.25, 0.40, 0.65, 0.06] if val else None,
        "edited": False,
    })

    # 5. Diện tích xây dựng / diện tích sàn
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Diện tích xây dựng|Diện tích sàn|Diện tích)[\s/:]+([\d\.,]+)\s*(?:m2|m²)?",
        pattern_fuzzy=r"(?:di[a-z0-9]*\s*t[a-z0-9]*(?:\s*x[a-z0-9]*\s*d[a-z0-9]*|\s*s[a-z0-9]*)?)[:\s-]*([0-9ol\.,]+)\s*(?:m[2²])?",
        base_conf=0.85,
        chuan_hoa_so=True,
    )
    fields.append({
        "name": "dien_tich_m2",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.25, 0.48, 0.25, 0.05] if val else None,
        "edited": False,
    })

    # 6. Số tầng
    val, conf = _tim_truong(
        text_nfc,
        text_nodiac,
        pattern_chuan=r"(?:Số tầng|Chiều cao tầng)[\s/:]+(\d+)",
        pattern_fuzzy=r"(?:s[o06]\s*t[a-z0-9]*|chi[a-z0-9]*\s*c[a-z0-9]*\s*t[a-z0-9]*)[:\s-]*([0-9ol]+)",
        base_conf=0.85,
        chuan_hoa_so=True,
    )
    fields.append({
        "name": "so_tang",
        "value": val,
        "confidence": conf,
        "page": 1,
        "bbox": [0.25, 0.54, 0.15, 0.05] if val else None,
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

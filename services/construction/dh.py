# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tiện ích dùng chung cho API Track D (contracts/dh/*.yaml).

- Lỗi theo hợp đồng: thân phản hồi `{code, message, details}` (main.py đăng ký handler cho LoiDH).
- Vai theo bảng vai của từng hợp đồng; quản trị nền tảng luôn được.
- Che dữ liệu cá nhân: CCCD `0012******90`, điện thoại `090****567`.
- HMAC CCCD bằng khóa `secrets/mdm-hmac.key` (scripts/dh_khoa.py sinh); không có khóa thì không so CCCD.
- Idempotency-Key: gọi lại cùng khóa trả đúng kết quả cũ (bảng core.dh_idempotency).
"""

import hashlib
import hmac
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional, Tuple

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from dxos_core.jwt import UserClaims

logger = logging.getLogger("dxos.dh")

VAI_CAN_BO = (
    "app:cap-phep:mot-cua",
    "app:cap-phep:tham-dinh",
    "app:cap-phep:lanh-dao",
    "app:cap-phep:trat-tu-xd",
)
VAI_QUAN_TRI_DU_LIEU = ("dx:tenant-admin", "dx:data-steward")
VAI_DOC_DH = VAI_CAN_BO + ("dx:auditor",) + VAI_QUAN_TRI_DU_LIEU
VAI_LIEN_KET = ("app:cap-phep:mot-cua", "app:cap-phep:tham-dinh") + VAI_QUAN_TRI_DU_LIEU
VAI_GOP = VAI_QUAN_TRI_DU_LIEU
VAI_DANH_MUC = ("dx:auditor",) + VAI_QUAN_TRI_DU_LIEU
VAI_GIAO_DQ = ("app:cap-phep:lanh-dao",) + VAI_QUAN_TRI_DU_LIEU
VAI_CHI_SO_H = ("app:cap-phep:lanh-dao", "dx:tenant-admin", "dx:auditor")
VAI_CHU_DAU_TU = "app:cap-phep:chu-dau-tu"
QUAN_TRI_NEN_TANG = "dx:platform-admin"

KHOA_HMAC_MAC_DINH = Path(os.getenv("DH_MDM_HMAC_KEY_FILE", "/app/secrets/mdm-hmac.key"))


class LoiDH(HTTPException):
    """Lỗi API Track D; handler trả nguyên `{code, message, details}`.

    Kế thừa HTTPException để get_db_connection không đổi thành 503 khi lỗi ném trong khối kết nối."""

    def __init__(self, status_code: int, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "details": details or {}})
        self.code = code
        self.message = message
        self.details = details or {}

    def body(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


def co_vai(claims: UserClaims, vai: Iterable[str]) -> bool:
    return QUAN_TRI_NEN_TANG in claims.roles or any(r in set(vai) for r in claims.roles)


def can_vai(claims: UserClaims, vai: Iterable[str], thong_diep: str = "Bạn không có quyền thực hiện thao tác này") -> None:
    if not co_vai(claims, vai):
        raise LoiDH(403, "FORBIDDEN", thong_diep)


def la_chu_dau_tu(claims: UserClaims) -> bool:
    return VAI_CHU_DAU_TU in claims.roles and not co_vai(claims, VAI_DOC_DH)


def che_cccd(cccd: Optional[str]) -> Optional[str]:
    """CCCD 12 số → 4 số đầu, 6 dấu *, 2 số cuối. Sai dạng thì không trả gì."""
    so = re.sub(r"\D", "", cccd or "")
    if len(so) != 12:
        return None
    return f"{so[:4]}{'*' * 6}{so[-2:]}"


def che_dien_thoai(dt: Optional[str]) -> Optional[str]:
    so = re.sub(r"\D", "", dt or "")
    if so.startswith("84") and len(so) == 11:
        so = "0" + so[2:]
    if len(so) < 9:
        return None
    return f"{so[:3]}{'*' * (len(so) - 6)}{so[-3:]}"


def _doc_khoa(duong_dan: Path) -> Optional[bytes]:
    try:
        noi_dung = duong_dan.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return noi_dung.encode("utf-8") if len(noi_dung) >= 32 else None


def cccd_hmac(cccd: Optional[str], duong_dan_khoa: Optional[Path] = None) -> Optional[str]:
    """HMAC-SHA256 của CCCD 12 số; thiếu khóa hoặc CCCD sai dạng thì None (không so khớp CCCD)."""
    so = re.sub(r"\D", "", cccd or "")
    if len(so) != 12:
        return None
    khoa = _doc_khoa(duong_dan_khoa or KHOA_HMAC_MAC_DINH)
    if khoa is None:
        logger.warning("Thiếu khóa HMAC MDM, bỏ qua so khớp CCCD")
        return None
    return hmac.new(khoa, so.encode("ascii"), hashlib.sha256).hexdigest()


def trang(page: int, page_size: int) -> Tuple[int, int, int]:
    """Kiểm tham số phân trang theo hợp đồng; trả (page, page_size, offset)."""
    if page < 1 or not 1 <= page_size <= 100:
        raise LoiDH(400, "BAD_REQUEST", "page từ 1, page_size từ 1 đến 100")
    return page, page_size, (page - 1) * page_size


def kiem_khoa_idempotency(khoa: Optional[str]) -> str:
    if not khoa or not 8 <= len(khoa) <= 128:
        raise LoiDH(400, "IDEMPOTENCY_KEY_REQUIRED", "Thiếu hoặc sai header Idempotency-Key (8–128 ký tự)")
    return khoa


async def idempotent(
    conn,
    claims: UserClaims,
    pham_vi: str,
    khoa: str,
    lam: Callable[[], Awaitable[Tuple[int, Any]]],
) -> Tuple[int, Any]:
    """Gọi lại cùng khóa và phạm vi trả đúng kết quả cũ; lần đầu chạy `lam` rồi lưu kết quả."""
    cu = await conn.fetchrow(
        "SELECT status_code, response FROM core.dh_idempotency WHERE tenant = $1 AND scope = $2 AND key = $3",
        claims.tenant, pham_vi, khoa,
    )
    if cu:
        than = cu["response"]
        return cu["status_code"], json.loads(than) if isinstance(than, str) else than
    ma, ket_qua = await lam()
    ket_qua = jsonable_encoder(ket_qua)
    await conn.execute(
        """
        INSERT INTO core.dh_idempotency (tenant, scope, key, status_code, response, created_by)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6)
        ON CONFLICT (tenant, scope, key) DO NOTHING
        """,
        claims.tenant, pham_vi, khoa, ma, json.dumps(ket_qua, ensure_ascii=False), claims.sub,
    )
    return ma, ket_qua


def iso(v: Any) -> Optional[str]:
    return v.isoformat() if hasattr(v, "isoformat") else (None if v is None else str(v))

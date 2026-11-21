# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Ngữ cảnh CSDL cho số liệu tổng hợp của bảng điều hành.

- Quản trị nền tảng (tenant `global`) chọn phường cần xem bằng tham số `tenant`; vai khác chỉ xem
  phường của mình.
- Số đếm tổng hợp (không trả dòng dữ liệu cá nhân) chạy bằng vai dịch vụ của đúng phường, để kiểm
  toán viên và quản trị thấy số thật thay vì 0 do RLS của app chặn đọc từng dòng.
- Danh sách có dữ liệu cá nhân vẫn đọc theo quyền của người gọi; chỉ quản trị nền tảng xem phường
  khác mới dùng vai dịch vụ.
"""

import re
from typing import Optional

from fastapi import HTTPException, status

from dxos_core.jwt import UserClaims

# Vai cấp nền tảng xem số tổng hợp của phường; vai nghiệp vụ của app (lãnh đạo...) đọc theo RLS của app.
VAI_XEM_TONG_HOP = ("dx:auditor", "dx:tenant-admin", "dx:platform-admin")
_MA_DIA_BAN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def dia_ban_duoc_xem(claims: UserClaims, tenant: Optional[str]) -> str:
    """Phường sẽ xem: của người gọi, hoặc phường được chọn nếu là quản trị nền tảng."""
    if not tenant or tenant == claims.tenant:
        return claims.tenant
    if "dx:platform-admin" not in claims.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Chỉ quản trị nền tảng được xem số liệu của phường khác", "ma_loi": "FORBIDDEN"},
        )
    if not _MA_DIA_BAN.match(tenant):
        raise HTTPException(status_code=422, detail={"loi": "Mã địa bàn không hợp lệ"})
    return tenant


def _vai_dich_vu(claims: UserClaims, dia_ban: str) -> UserClaims:
    return UserClaims(
        sub=claims.sub,
        tenant=dia_ban,
        roles=["dx:service"],
        preferred_username=claims.preferred_username,
    )


def ngu_canh_tong_hop(claims: UserClaims, tenant: Optional[str] = None) -> UserClaims:
    """Ngữ cảnh cho truy vấn chỉ trả số đếm/tỷ lệ của một phường."""
    dia_ban = dia_ban_duoc_xem(claims, tenant)
    if any(r in VAI_XEM_TONG_HOP for r in claims.roles):
        return _vai_dich_vu(claims, dia_ban)
    return claims


def ngu_canh_danh_sach(claims: UserClaims, tenant: Optional[str] = None) -> UserClaims:
    """Ngữ cảnh cho truy vấn trả danh sách hồ sơ (có họ tên, địa chỉ)."""
    dia_ban = dia_ban_duoc_xem(claims, tenant)
    if dia_ban != claims.tenant:
        return _vai_dich_vu(claims, dia_ban)
    return claims

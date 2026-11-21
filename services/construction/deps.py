# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tiện ích phân quyền dùng chung cho các router Track A."""

from typing import Iterable

from fastapi import HTTPException, status

from dxos_core.jwt import UserClaims

STAFF_ROLES = (
    "app:cap-phep:mot-cua",
    "app:cap-phep:tham-dinh",
    "app:cap-phep:lanh-dao",
    "app:cap-phep:trat-tu-xd",
)
CHECK_ROLES = (
    "app:cap-phep:mot-cua",
    "app:cap-phep:tham-dinh",
    "app:cap-phep:lanh-dao",
)
# Nghiệm thu theo mốc do cán bộ kiểm tra hoặc trật tự xây dựng thực hiện
# (BPMN giao việc nghiệm thu cho nhóm tham-dinh và trat-tu-xd).
ACCEPTANCE_ROLES = CHECK_ROLES + ("app:cap-phep:trat-tu-xd",)
AUDIT_ROLES = ("dx:auditor",)
ADMIN_ROLES = ("dx:platform-admin", "dx:tenant-admin")


def co_vai(claims: UserClaims, roles: Iterable[str]) -> bool:
    wanted = set(roles)
    return any(r in wanted for r in claims.roles)


def la_can_bo(claims: UserClaims) -> bool:
    return co_vai(claims, STAFF_ROLES + AUDIT_ROLES + ADMIN_ROLES)


def la_nguoi_kiem_tra(claims: UserClaims) -> bool:
    return co_vai(claims, CHECK_ROLES + ADMIN_ROLES)


def la_nguoi_nghiem_thu(claims: UserClaims) -> bool:
    return co_vai(claims, ACCEPTANCE_ROLES + ADMIN_ROLES)


def la_auditor(claims: UserClaims) -> bool:
    return co_vai(claims, AUDIT_ROLES + ADMIN_ROLES)


def yeu_cau(claims: UserClaims, roles: Iterable[str], thong_diep: str = "Bạn không có quyền thực hiện thao tác này") -> None:
    if not co_vai(claims, roles + ADMIN_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"loi": thong_diep, "ma_loi": "FORBIDDEN"})


def yeu_cau_kiem_tra(claims: UserClaims) -> None:
    if not la_nguoi_kiem_tra(claims):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Chỉ cán bộ một cửa, thẩm định hoặc lãnh đạo được thực hiện kiểm tra", "ma_loi": "FORBIDDEN"},
        )


def yeu_cau_can_bo(claims: UserClaims) -> None:
    if not la_can_bo(claims):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Chỉ cán bộ nghiệp vụ hoặc kiểm toán viên được xem dữ liệu này", "ma_loi": "FORBIDDEN"},
        )


def yeu_cau_nghiem_thu(claims: UserClaims) -> None:
    if not la_nguoi_nghiem_thu(claims):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Chỉ cán bộ một cửa, thẩm định, trật tự xây dựng hoặc lãnh đạo được nghiệm thu", "ma_loi": "FORBIDDEN"},
        )

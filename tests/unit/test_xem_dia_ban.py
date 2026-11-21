# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Ngữ cảnh số liệu tổng hợp: chọn phường chỉ cho quản trị nền tảng; vai nền tảng đọc số tổng hợp
bằng vai dịch vụ của đúng phường; vai khác giữ nguyên quyền của mình."""

import pytest
from fastapi import HTTPException

from dxos_core.jwt import UserClaims
from dxos_core.xem_dia_ban import dia_ban_duoc_xem, ngu_canh_danh_sach, ngu_canh_tong_hop


def _c(roles, tenant="phuong-a"):
    return UserClaims(sub="u1", tenant=tenant, roles=roles, preferred_username="u1")


def test_vai_thuong_khong_doi_phuong():
    c = _c(["app:x:can-bo"])
    assert dia_ban_duoc_xem(c, None) == "phuong-a"
    assert dia_ban_duoc_xem(c, "phuong-a") == "phuong-a"
    with pytest.raises(HTTPException) as e:
        dia_ban_duoc_xem(c, "phuong-b")
    assert e.value.status_code == 403
    assert ngu_canh_tong_hop(c, None) is c
    assert ngu_canh_danh_sach(c, None) is c


def test_kiem_toan_doc_tong_hop_bang_vai_dich_vu_cung_phuong():
    c = _c(["dx:auditor"])
    ctx = ngu_canh_tong_hop(c, None)
    assert ctx.tenant == "phuong-a" and ctx.roles == ["dx:service"]
    assert ngu_canh_danh_sach(c, None) is c
    with pytest.raises(HTTPException):
        ngu_canh_tong_hop(c, "phuong-b")


def test_quan_tri_nen_tang_chon_phuong():
    c = _c(["dx:platform-admin"], tenant="global")
    assert ngu_canh_tong_hop(c, "phuong-b").tenant == "phuong-b"
    ds = ngu_canh_danh_sach(c, "phuong-b")
    assert ds.tenant == "phuong-b" and ds.roles == ["dx:service"]
    with pytest.raises(HTTPException) as e:
        dia_ban_duoc_xem(c, "Phuong B; drop")
    assert e.value.status_code == 422

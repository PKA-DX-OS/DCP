# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-17: trật tự xây dựng được ghi mốc nghiệm thu (API và RLS), quyền kiểm tra khác giữ nguyên."""

from pathlib import Path

import pytest
from construction import deps
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]


class _Claims:
    def __init__(self, *roles):
        self.roles = list(roles)


@pytest.mark.parametrize("vai", [
    "app:cap-phep:trat-tu-xd", "app:cap-phep:tham-dinh", "app:cap-phep:mot-cua",
    "app:cap-phep:lanh-dao", "dx:platform-admin",
])
def test_vai_duoc_nghiem_thu(vai):
    deps.yeu_cau_nghiem_thu(_Claims(vai))


@pytest.mark.parametrize("vai", ["app:cap-phep:chu-dau-tu", "dx:auditor"])
def test_vai_khong_duoc_nghiem_thu(vai):
    with pytest.raises(HTTPException) as loi:
        deps.yeu_cau_nghiem_thu(_Claims(vai))
    assert loi.value.status_code == 403


def test_quyen_kiem_tra_khong_mo_rong_cho_trat_tu():
    with pytest.raises(HTTPException):
        deps.yeu_cau_kiem_tra(_Claims("app:cap-phep:trat-tu-xd"))


def test_api_nghiem_thu_dung_kiem_tra_quyen_nghiem_thu():
    src = (ROOT / "services/construction/routers/acceptance.py").read_text(encoding="utf-8")
    assert src.count("yeu_cau_nghiem_thu(claims)") == 3
    assert "yeu_cau_kiem_tra" not in src


def test_rls_ghi_nghiem_thu_cho_trat_tu():
    sql = (ROOT / "core/postgres/17-nghiem-thu-trat-tu.sql").read_text(encoding="utf-8")
    assert "core.has_role('app:cap-phep:trat-tu-xd')" in sql
    for bang, chinh_sach in (("moc_nghiem_thu", "rls_moc_write"), ("bien_ban_nghiem_thu", "rls_bien_ban_write"),
                             ("ban_ve_hoan_cong", "rls_ban_ve_write")):
        assert f"CREATE POLICY {chinh_sach} ON app_construction.{bang}" in sql
    assert "la_nguoi_kiem_tra()" not in sql.split("$$;", 1)[1]

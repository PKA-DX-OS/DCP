# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-15: chính sách SELECT ho_so cho trật tự xây dựng khớp mo_ho_so (chỉ hồ sơ đã cấp phép)."""

from pathlib import Path

MIG = Path(__file__).resolve().parents[2] / "apps/cap-phep/db/migrations"


def test_rls_ho_so_cho_trat_tu_chi_ho_so_da_cap():
    sql = (MIG / "19-trat-tu-rls-ho-so-da-cap.sql").read_text(encoding="utf-8")
    assert "CREATE POLICY rls_ho_so_select ON app_cap_phep.ho_so" in sql
    assert "tenant = core.jwt_tenant() AND (" in sql
    assert "core.has_role('app:cap-phep:trat-tu-xd') AND trang_thai = 'DA_CAP'" in sql
    for dieu_kien in ("chu_dau_tu_sub = core.jwt_sub()", "core.can_access('ho_so', id)",
                      "core.has_role('app:cap-phep:lanh-dao')", "core.has_role('app:cap-phep:mot-cua')"):
        assert dieu_kien in sql


def test_chay_sau_migration_tao_lai_chinh_sach():
    ten = sorted(p.name for p in MIG.glob("*.sql"))
    assert ten.index("19-trat-tu-rls-ho-so-da-cap.sql") > ten.index("01-app-cap-phep.sql")
    assert ten[-1] == "19-trat-tu-rls-ho-so-da-cap.sql" or all(
        "rls_ho_so_select" not in (MIG / t).read_text(encoding="utf-8") for t in ten[ten.index("19-trat-tu-rls-ho-so-da-cap.sql") + 1:]
    )

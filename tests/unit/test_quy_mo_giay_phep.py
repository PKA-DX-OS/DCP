# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-23: giấy phép và văn bản ký dùng quy mô của lần kiểm tra quy hoạch đạt gần nhất."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG = ROOT / "apps/cap-phep/db/migrations"
SQL = (MIG / "23-quy-mo-giay-phep.sql").read_text(encoding="utf-8")


def test_quy_mo_lay_tu_lan_kiem_tra_dat_gan_nhat():
    assert "CREATE OR REPLACE FUNCTION app_cap_phep_private.quy_mo_duyet(p_ho_so_id uuid, p_tenant text)" in SQL
    assert "WHERE ho_so_id = $1 AND tenant = $2 AND pass" in SQL
    assert "ORDER BY created_at DESC" in SQL
    assert "to_regclass('app_construction.ket_qua_kiem_tra_quy_hoach')" in SQL
    assert "COALESCE(v_so_tang, v_hs.so_tang)" in SQL and "COALESCE(v_dien_tich, v_hs.dien_tich_san_m2)" in SQL


def test_du_lieu_ky_va_giay_phep_dung_quy_mo_duyet():
    assert "CREATE OR REPLACE FUNCTION app_cap_phep_private.du_lieu_giay_phep(" in SQL
    assert "'so_tang', (v_qm->>'so_tang')::int" in SQL
    assert "'so_tang', v_hs.so_tang" not in SQL
    assert "'nguon_quy_mo', v_qm->>'nguon'" in SQL
    for cot in ("so_tang integer", "dien_tich_san_m2 double precision", "nguon_quy_mo text"):
        assert f"ALTER TABLE app_cap_phep.giay_phep ADD COLUMN IF NOT EXISTS {cot}" in SQL
    assert "BEFORE INSERT ON app_cap_phep.giay_phep" in SQL


def test_khong_migration_sau_ghi_de_du_lieu_giay_phep():
    ten = sorted(p.name for p in MIG.glob("*.sql"))
    sau = ten[ten.index("23-quy-mo-giay-phep.sql") + 1:]
    assert all("du_lieu_giay_phep" not in (MIG / t).read_text(encoding="utf-8") for t in sau)

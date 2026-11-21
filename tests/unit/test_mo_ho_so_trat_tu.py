# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-12: trật tự xây dựng chỉ được mở thêm hồ sơ đã cấp phép; các điều kiện cũ giữ nguyên."""

from pathlib import Path

MIG = Path(__file__).resolve().parents[2] / "apps/cap-phep/db/migrations/18-trat-tu-xem-ho-so-da-cap.sql"


def test_trat_tu_chi_xem_ho_so_da_cap():
    sql = MIG.read_text(encoding="utf-8")
    assert "core.has_role('app:cap-phep:trat-tu-xd') AND v_rec.trang_thai = 'DA_CAP'" in sql
    # Kiểm tra phường vẫn đứng trước kiểm tra quyền
    assert sql.index("FORBIDDEN_TENANT") < sql.index("app:cap-phep:trat-tu-xd")
    for dieu_kien in ("v_rec.chu_dau_tu_sub = v_sub", "core.can_access('ho_so', p_id)", "access.denied"):
        assert dieu_kien in sql

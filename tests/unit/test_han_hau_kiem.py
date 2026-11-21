# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-22: phiếu hậu kiểm có hạn xử lý, việc hậu kiểm có SLA trong hàng đợi."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _sla():
    data = yaml.safe_load((ROOT / "apps/cap-phep/app.yaml").read_text(encoding="utf-8"))
    return data["flow_policies"]["sla"]


def test_viec_hau_kiem_co_sla():
    bpmn = (ROOT / "apps/cap-phep/bpmn/hau-kiem.bpmn20.xml").read_text(encoding="utf-8")
    sla = _sla()
    for buoc in ("taskKiemTraHienTruong", "taskXuLyViPham"):
        assert f'id="{buoc}"' in bpmn
        assert sla.get(buoc), buoc
    assert sla["taskKiemTraHienTruong"] == "P2D"


def test_phieu_co_han_khop_sla():
    sql = (ROOT / "apps/cap-phep/db/migrations/22-han-hau-kiem.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS han_xu_ly_at timestamptz" in sql
    assert "interval '2 days'" in sql  # khớp P2D của taskKiemTraHienTruong
    assert "BEFORE INSERT ON app_cap_phep.phieu_kiem_tra" in sql
    assert "WHERE han_xu_ly_at IS NULL" in sql
    assert "SECURITY DEFINER" in sql

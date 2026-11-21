# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FIX-V11-07: thời hạn giải quyết 7 ngày làm việc (Điều 54 NĐ 217/2026) thống nhất ở SQL, SLA, giao diện."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "cap-phep"
SO_NGAY = 7


def _migration() -> str:
    return (APP / "db" / "migrations" / "15-thoi-han-7-ngay.sql").read_text(encoding="utf-8")


def test_sql_mot_hang_so_7_ngay():
    sql = _migration()
    assert re.search(r"so_ngay_giai_quyet\(\)\s+RETURNS integer.*?SELECT 7", sql, re.S)
    assert "add_business_days(now(), app_cap_phep.so_ngay_giai_quyet())" in sql
    assert "add_business_days(now(), 15)" not in sql


def test_sla_luong_cap_phep_cong_lai_7_ngay():
    sla = yaml.safe_load((APP / "app.yaml").read_text(encoding="utf-8"))["flow_policies"]["sla"]
    ngay = lambda k: int(re.fullmatch(r"P(\d+)D", sla[k]).group(1))  # noqa: E731
    assert ngay("taskKiemTraHopLe") + ngay("taskPhanCong") + ngay("taskThamDinh") + ngay("taskDuyetCapPhep") == SO_NGAY
    assert ngay("taskThamDinh") == 3


def test_giao_dien_dung_7_ngay():
    ws = (APP / "web" / "src" / "views" / "WorkspaceView.vue").read_text(encoding="utf-8")
    khoi = re.search(r"const STEPS = \[(.*?)\];", ws, re.S).group(1)
    assert sum(int(d) for d in re.findall(r"days: (\d+)", khoi)) == SO_NGAY
    form = (APP / "web" / "src" / "components" / "CreateDossierModal.vue").read_text(encoding="utf-8")
    assert "7 ngày làm việc" in form and "15 ngày" not in form

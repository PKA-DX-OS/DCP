# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-UX-08: seed 12 tháng, idempotent và mỗi vai có việc."""

import subprocess
import sys

from tests.integration._auth import ROOT
from tests.integration._ho_so import run_sql


def test_UX08_seed_demo_history_idempotent_va_du_12_thang():
    for _ in range(2):
        subprocess.run([sys.executable, "scripts/seed_demo_history.py"], cwd=ROOT, check=True)

    so_thang = int(
        run_sql(
            "SELECT count(DISTINCT date_trunc('month', created_at)) "
            "FROM app_cap_phep.ho_so WHERE ma_ho_so LIKE 'CP-DEMO-HIST-%';"
        )
    )
    so_ho_so = int(run_sql("SELECT count(*) FROM app_cap_phep.ho_so WHERE ma_ho_so LIKE 'CP-DEMO-HIST-%';"))
    assert so_thang == 12, so_thang
    assert so_ho_so == 72, so_ho_so

    for username in ("td.binh", "td.cuong", "mc.thu"):
        so_viec = int(
            run_sql(
                "SELECT count(*) FROM core.assignments a "
                "JOIN core.users_directory u ON u.id::text = a.user_sub "
                f"WHERE u.username = '{username}' AND a.active = true "
                "AND a.object_id IN (SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so LIKE 'CP-DEMO-HIST-%');"
            )
        )
        assert so_viec > 0, f"{username} chưa có việc"

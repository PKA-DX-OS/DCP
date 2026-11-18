# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""export-warm chạy được như dịch vụ nền trong compose (--lap-giay) và vẫn giữ chế độ chạy một lô."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("export_warm_worker", ROOT / "services" / "export-warm" / "worker.py")
worker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(worker)


def test_thang_can_xuat_gom_thang_truoc_va_thang_nay():
    assert worker.thang_can_xuat(datetime(2026, 11, 18, tzinfo=timezone.utc)) == ["2026-10", "2026-11"]
    assert worker.thang_can_xuat(datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)) == ["2025-12", "2026-01"]


@pytest.mark.parametrize("argv", [[], ["--lap-giay", "30"], ["--lap-giay", "3600", "--month", "2026-11"]])
def test_tham_so_sai_bi_tu_choi(argv):
    with pytest.raises(SystemExit) as e:
        worker.main(argv)
    assert e.value.code == 2


def test_compose_chay_export_warm_o_che_do_lap():
    import yaml

    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    cmd = compose["services"]["export-warm"]["command"]
    assert "--lap-giay" in cmd and int(cmd[cmd.index("--lap-giay") + 1]) >= 60

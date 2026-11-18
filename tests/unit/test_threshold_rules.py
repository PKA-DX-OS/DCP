# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import datetime, timezone
from ingest.main import check_threshold_breach


def test_noise_daytime_threshold():
    # 10h00 sáng (ban ngày)
    day_ts = datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc)

    # Dưới ngưỡng 70 dBA -> Không vi phạm
    assert check_threshold_breach("laeq_dba", 68.5, day_ts) is None

    # Trên ngưỡng 70 dBA -> Có vi phạm
    breach = check_threshold_breach("laeq_dba", 72.0, day_ts)
    assert breach is not None
    assert breach["threshold"] == 70.0
    assert breach["time_window"] == "day"


def test_noise_nighttime_threshold():
    # 22h00 đêm (ban đêm)
    night_ts = datetime(2026, 11, 4, 22, 0, tzinfo=timezone.utc)

    # 54 dBA -> Dưới ngưỡng 55 dBA ban đêm -> Không vi phạm
    assert check_threshold_breach("laeq_dba", 54.0, night_ts) is None

    # 58 dBA -> Vượt ngưỡng 55 dBA ban đêm -> Có vi phạm
    breach = check_threshold_breach("laeq_dba", 58.0, night_ts)
    assert breach is not None
    assert breach["threshold"] == 55.0
    assert breach["time_window"] == "night"


def test_dust_thresholds():
    ts = datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc)
    assert check_threshold_breach("pm10", 95.0, ts) is None

    b_pm10 = check_threshold_breach("pm10", 105.0, ts)
    assert b_pm10 is not None
    assert b_pm10["threshold"] == 100.0

    assert check_threshold_breach("pm25", 45.0, ts) is None
    b_pm25 = check_threshold_breach("pm25", 55.0, ts)
    assert b_pm25 is not None
    assert b_pm25["threshold"] == 50.0

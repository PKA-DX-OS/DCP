# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import datetime, timezone, timedelta


def add_business_days(start_ts: datetime, n: int) -> datetime:
    """Hàm Python tương đương chính xác với hàm SQL `core.add_business_days`."""
    cur = start_ts
    added = 0
    if n <= 0:
        return start_ts
    while added < n:
        cur += timedelta(days=1)
        # weekday(): Monday is 0, Sunday is 6. Saturday is 5.
        if cur.weekday() not in (5, 6):
            added += 1
    return cur


def test_add_business_days_within_week():
    # Thứ Hai ngày 02/11/2026 cộng 3 ngày làm việc -> Thứ Năm ngày 05/11/2026
    start = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
    res = add_business_days(start, 3)
    assert res == datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)


def test_add_business_days_spanning_weekend():
    # Thứ Năm ngày 05/11/2026 cộng 3 ngày làm việc -> Thứ Ba ngày 10/11/2026 (bỏ qua T7 và CN)
    start = datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)
    res = add_business_days(start, 3)
    assert res.weekday() == 1  # Tuesday
    assert res == datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)


def test_add_business_days_seven_days():
    # 7 ngày làm việc từ Thứ Hai ngày 02/11/2026 -> Thứ Tư tuần sau ngày 11/11/2026
    start = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
    res = add_business_days(start, 7)
    assert res == datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)

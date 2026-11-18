# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import datetime, timezone, timedelta


def test_business_days_calculation_logic():
    """Kiểm tra logic tính ngày làm việc (bỏ qua Thứ Bảy và Chủ Nhật) tương ứng SQL core.add_business_days."""
    def add_business_days(start_date: datetime, n: int) -> datetime:
        cur = start_date
        added = 0
        while added < n:
            cur += timedelta(days=1)
            # Monday is 0, Sunday is 6
            if cur.weekday() < 5:
                added += 1
        return cur

    # Bắt đầu từ Thứ Sáu (2026-11-06)
    friday = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)
    # +1 ngày làm việc -> Thứ Hai (2026-11-09)
    monday = add_business_days(friday, 1)
    assert monday.weekday() == 0
    assert monday.day == 9

    # +3 ngày làm việc -> Thứ Tư (2026-11-11)
    wednesday = add_business_days(friday, 3)
    assert wednesday.weekday() == 2
    assert wednesday.day == 11

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import datetime, timezone
from tests.unit.test_business_days import add_business_days

DSAR_LIMITS_BUSINESS_DAYS = {
    "access": 10,
    "rectify": 10,
    "withdraw": 15,
    "restrict": 15,
    "erase": 20,
}


def calculate_dsar_deadlines(req_type: str, received_at: datetime):
    days = DSAR_LIMITS_BUSINESS_DAYS.get(req_type, 10)
    ack_due = add_business_days(received_at, 2)
    process_due = add_business_days(received_at, days)
    return ack_due, process_due


def test_dsar_access_deadlines():
    start = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)  # Monday
    ack_due, process_due = calculate_dsar_deadlines("access", start)
    # 2 ngày làm việc -> Thứ Tư
    assert ack_due == datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)
    # 10 ngày làm việc (2 tuần) -> Thứ Hai tuần sau nữa
    assert process_due == datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc)


def test_dsar_erase_deadline():
    start = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)  # Monday
    _, process_due = calculate_dsar_deadlines("erase", start)
    # 20 ngày làm việc (4 tuần) -> Thứ Hai 4 tuần sau
    assert process_due == datetime(2026, 11, 30, 8, 0, tzinfo=timezone.utc)

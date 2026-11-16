# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
import subprocess
from tests.integration.conftest import GATEWAY_URL, get_token


def test_V3_06_dsar_due_dates_calculation():
    token_minh = get_token("cdt.minh")
    url = f"{GATEWAY_URL}/api/v1/rest/rpc/gui_yeu_cau_dsar"

    # Kiểm tra cho cả 3 nhóm thời hạn: access (10), withdraw (15), erase (20)
    cases = [
        ("access", 2, 10),
        ("withdraw", 2, 15),
        ("erase", 2, 20),
    ]

    for req_type, exp_ack_days, exp_due_days in cases:
        req = urllib.request.Request(
            url,
            data=json.dumps({"p_type": req_type}).encode(),
            headers={"Authorization": f"Bearer {token_minh}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        req_id = data["id"]
        ack_due_str = data["ack_due_at"]
        due_str = data["due_at"]

        # Truy vấn trực tiếp PostgreSQL để tính ngày làm việc chuẩn từ received_at
        query = f"""
        SELECT received_at,
               core.add_business_days(received_at, {exp_ack_days}) AS exp_ack,
               core.add_business_days(received_at, {exp_due_days}) AS exp_due
        FROM core.dsar_requests
        WHERE id = '{req_id}';
        """
        cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", query]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        rec_at, exp_ack, exp_due = proc.stdout.strip().split("|")

        # So khớp ngày (YYYY-MM-DD)
        assert ack_due_str[:10] == exp_ack[:10], (
            f"Loại {req_type}: ack_due_at không khớp (+{exp_ack_days} ngày làm việc). "
            f"Nhận được: {ack_due_str}, Kỳ vọng: {exp_ack}"
        )
        assert due_str[:10] == exp_due[:10], (
            f"Loại {req_type}: due_at không khớp (+{exp_due_days} ngày làm việc). "
            f"Nhận được: {due_str}, Kỳ vọng: {exp_due}"
        )

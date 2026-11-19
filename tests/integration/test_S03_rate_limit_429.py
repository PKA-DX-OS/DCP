# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import urllib.request
import urllib.error
from tests.integration.conftest import GATEWAY_URL


def test_S03_rate_limit_429():
    url = f"{GATEWAY_URL}/api/v1/health"
    received_429 = False

    for _ in range(130):
        try:
            with urllib.request.urlopen(url, timeout=2):
                pass
        except urllib.error.HTTPError as e:
            if e.code == 429:
                received_429 = True
                break

    assert received_429 is True, "Mong đợi nhận được mã 429 khi gửi vượt ngưỡng 120 req/phút"

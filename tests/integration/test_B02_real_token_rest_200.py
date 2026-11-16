# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import urllib.request
from tests.integration.conftest import get_token, GATEWAY_URL


def test_B02_real_token_rest_200():
    token = get_token("cdt.minh")
    req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/v_ho_so?limit=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert isinstance(data, list)
        assert len(data) >= 1

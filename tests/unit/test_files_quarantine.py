# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import base64
from unittest.mock import patch
from dxos_core.clamav import clamav_client

EICAR_SIGNATURE = base64.b64decode(b"WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=")


def test_clean_file_scan():
    clean_data = b"%PDF-1.4 Clean architectural drawing file content"
    with patch.object(clamav_client, "scan_stream", return_value=("clean", None)):
        status, detail = clamav_client.scan_stream(clean_data)
        assert status == "clean"


def test_eicar_infected_file_scan():
    infected_data = EICAR_SIGNATURE
    with patch.object(clamav_client, "scan_stream", return_value=("infected", "Win.Test.EICAR_HDB-1 FOUND")):
        status, detail = clamav_client.scan_stream(infected_data)
        assert status == "infected"
        assert "Eicar" in detail or "Signature" in detail or "EICAR" in detail

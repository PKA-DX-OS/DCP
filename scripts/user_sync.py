#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Đồng bộ người dùng và vai trò Keycloak sang core.users_directory (D-MDM-04)."""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sync_users import main

if __name__ == "__main__":
    main()

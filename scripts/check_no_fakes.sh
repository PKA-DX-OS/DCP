#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

set -eo pipefail

python3 "$(dirname "$0")/check_no_fakes.py"


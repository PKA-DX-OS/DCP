#!/bin/sh
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Điểm vào image dxos/tools:
#   tools scripts/doctor.py ...        -> python3 scripts/doctor.py ... (cách dx gọi)
#   tools python scripts/x.py ...      -> chạy đúng lệnh đã cho (python, python3, sh, restic...)
# Tham số đầu có dấu "/" hoặc bắt đầu bằng "-" luôn được coi là tham số của python3.
set -e
if [ "$#" -gt 0 ]; then
  case "$1" in
    -*|*/*) ;;
    *)
      if command -v "$1" >/dev/null 2>&1; then
        exec "$@"
      fi
      ;;
  esac
fi
exec python3 "$@"

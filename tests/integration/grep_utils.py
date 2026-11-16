# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tiện ích grep hoạt động cả khi package không có .git."""

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def grep_repo(pattern: str, paths: tuple[str, ...] = ("core", "services")) -> str:
    """Trả về các dòng khớp; dùng git grep nếu có repo, nếu không quét filesystem."""
    if (ROOT / ".git").exists():
        res = subprocess.run(
            ["git", "grep", "-niE", pattern, "--", *paths],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if res.returncode in (0, 1):
            return res.stdout

    regex = re.compile(pattern, re.IGNORECASE)
    matches = []
    for base in paths:
        base_path = ROOT / base
        if not base_path.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(base_path):
            dirnames[:] = [d for d in dirnames if d not in {"__pycache__", ".git"}]
            for filename in filenames:
                if filename.endswith(".pyc"):
                    continue
                path = Path(dirpath) / filename
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for lineno, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        rel = path.relative_to(ROOT).as_posix()
                        matches.append(f"{rel}:{lineno}:{line.strip()}")
    return "\n".join(matches)

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""U-04: lõi (core/, services/) không chứa từ vựng nghiệp vụ của app cấp phép, kể cả tiếng Việt có dấu.

core/keycloak và core/nats là dữ liệu triển khai mẫu (tài khoản, thiết bị theo phường) nên được loại trừ.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERN = re.compile(
    r"cap[-_.]phep|giay[-_.]phep|cong[-_.]trinh|hau[-_.]kiem|qcvn|ho_so|taskDuyet|chu[-_.]dau[-_.]tu"
    r"|trat[-_.]tu|phuong-[ab]\b|giấy phép|xây dựng|hậu kiểm",
    re.IGNORECASE,
)
EXCLUDED = {"core/keycloak", "core/nats"}
SUFFIXES = {".py", ".sql", ".yaml", ".yml", ".conf", ".sh", ".json", ".toml", ".ts", ".js"}


def _files():
    for top in ("core", "services"):
        for p in (ROOT / top).rglob("*"):
            rel = p.relative_to(ROOT).as_posix()
            if not p.is_file() or p.suffix not in SUFFIXES:
                continue
            if any(rel.startswith(e + "/") for e in EXCLUDED) or "__pycache__" in rel:
                continue
            yield rel, p


def test_core_khong_chua_tu_vung_nghiep_vu():
    hits = []
    for rel, p in _files():
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if PATTERN.search(line):
                hits.append(f"{rel}:{i}: {line.strip()[:120]}")
    assert not hits, "Lõi còn từ vựng nghiệp vụ:\n" + "\n".join(hits)

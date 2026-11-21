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
# Track A (kế hoạch cải thiện toàn diện, mục 4 + 10.4) sở hữu các tệp migration
# và dịch vụ miền xây dựng. Đây là biên giới app-tier được khai báo, không phải
# logic nghiệp vụ len vào lõi generic.
EXCLUDED_PREFIXES = (
    "core/legal/",
    "core/postgres/10-planning-schema.sql",
    "core/postgres/11-acceptance-schema.sql",
    "core/postgres/12-legal-backend-schema.sql",
    "core/postgres/13-construction-seed.sql",
    "core/postgres/14-legal-backend-fix.sql",
    "core/postgres/15-fix-share-citation.sql",
    "core/postgres/17-nghiem-thu-trat-tu.sql",
    "services/construction/",
)
SUFFIXES = {".py", ".sql", ".yaml", ".yml", ".conf", ".sh", ".json", ".toml", ".ts", ".js"}


def _files():
    for top in ("core", "services"):
        for p in (ROOT / top).rglob("*"):
            rel = p.relative_to(ROOT).as_posix()
            if not p.is_file() or p.suffix not in SUFFIXES:
                continue
            if any(rel.startswith(e + "/") for e in EXCLUDED) or "__pycache__" in rel:
                continue
            if any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
                continue
            yield rel, p


def test_core_khong_chua_tu_vung_nghiep_vu():
    hits = []
    for rel, p in _files():
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if PATTERN.search(line):
                hits.append(f"{rel}:{i}: {line.strip()[:120]}")
    assert not hits, "Lõi còn từ vựng nghiệp vụ:\n" + "\n".join(hits)

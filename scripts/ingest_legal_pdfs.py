#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

r"""
Ingest toàn văn PDF pháp luật + tài liệu phân tích vào RAG (A-LEGAL-01 / P0-11).

- Nguồn ngoài repo: mặc định D:\PMNM\TaiLieuHanhChinh_C3
  (01_VanBanPhapLuat/*.pdf, 03_PHAN_TICH/*.md, metadata.json).
- Chunk ~1800 ký tự, lưu core.knowledge_chunks với source `legal-pdf/<file>#pN`
  và `legal-analysis/<file>#cN`.
- Idempotent: xóa chunk cũ của hai nhóm nguồn này trước khi nạp.
- Không commit nội dung PDF vào repo; chỉ nạp DB demo.

Chạy:
    py -3 scripts/ingest_legal_pdfs.py
    py -3 scripts/ingest_legal_pdfs.py --source "D:\\PMNM\\TaiLieuHanhChinh_C3" --tenant phuong-a
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception):
        pass

DEFAULT_SOURCE = Path(r"D:\PMNM\TaiLieuHanhChinh_C3")
CHUNK_CHARS = 1800


def q(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def chunk_text(text: str, size: int = CHUNK_CHARS) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = text.rfind(". ", start, end)
            if cut > start + size // 2:
                end = cut + 1
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if len(c) >= 80]


def extract_pdf(path: Path) -> Iterable[tuple[int, str]]:
    try:
        import pymupdf  # type: ignore
    except ImportError:  # pragma: no cover
        raise SystemExit("Thiếu pymupdf. Cài: py -3 -m pip install pymupdf")
    with pymupdf.open(path) as doc:
        for idx, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            for chunk in chunk_text(text):
                yield idx, chunk


def build_sql(source: Path, tenants: list[str], docs: dict[str, dict]) -> tuple[str, int]:
    lines = ["BEGIN;"]
    for tenant in tenants:
        lines.append(
            "DELETE FROM core.knowledge_chunks WHERE tenant = "
            f"{q(tenant)} AND app = 'cap-phep' AND (source LIKE 'legal-pdf/%' OR source LIKE 'legal-analysis/%');"
        )

    count = 0
    pdf_dir = source / "01_VanBanPhapLuat"
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        meta = docs.get(pdf.name, {})
        code = meta.get("code") or pdf.stem
        title = meta.get("title") or pdf.stem
        for page, chunk in extract_pdf(pdf):
            body = f"Văn bản {code} — {title}, trang {page}: {chunk}"
            for tenant in tenants:
                lines.append(
                    "INSERT INTO core.knowledge_chunks (tenant, app, source, chunk) VALUES ("
                    f"{q(tenant)}, 'cap-phep', {q(f'legal-pdf/{pdf.name}#p{page}')}, {q(body)});"
                )
            count += 1

    analysis_dir = source / "03_PHAN_TICH"
    if analysis_dir.exists():
        for md in sorted(analysis_dir.glob("*.md")):
            text = md.read_text(encoding="utf-8", errors="replace")
            for idx, chunk in enumerate(chunk_text(text), start=1):
                body = f"Tài liệu phân tích {md.name}, đoạn {idx}: {chunk}"
                for tenant in tenants:
                    lines.append(
                        "INSERT INTO core.knowledge_chunks (tenant, app, source, chunk) VALUES ("
                        f"{q(tenant)}, 'cap-phep', {q(f'legal-analysis/{md.name}#c{idx}')}, {q(body)});"
                    )
                count += 1

    lines.append("NOTIFY pgrst, 'reload schema';")
    lines.append("COMMIT;")
    return "\n".join(lines), count


def run_sql(sql: str, args: argparse.Namespace) -> subprocess.CompletedProcess:
    if args.no_docker:
        psql = args.psql or shutil.which("psql")
        if not psql:
            raise SystemExit("Không tìm thấy psql.")
        cmd = [psql, "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1", "-f", "-"]
    else:
        cmd = [
            "docker", "exec", "-i", args.container,
            "psql", "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1", "-f", "-",
        ]
    return subprocess.run(cmd, input=sql, capture_output=True, text=True, encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Nạp toàn văn PDF pháp luật vào RAG")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--tenant", action="append", dest="tenants")
    parser.add_argument("--no-docker", action="store_true")
    parser.add_argument("--psql")
    parser.add_argument("--container", default="dxos-postgres")
    parser.add_argument("--user", default="dxos_owner")
    parser.add_argument("--database", default="dxos")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    source = Path(args.source)
    if not (source / "01_VanBanPhapLuat").exists():
        raise SystemExit(f"Không thấy thư mục 01_VanBanPhapLuat trong {source}")
    metadata = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
    docs = {d["file"]: d for d in metadata.get("documents", [])}
    tenants = args.tenants or ["phuong-a", "phuong-b"]

    sql, count = build_sql(source, tenants, docs)
    print(f"[INFO] {len(docs)} văn bản metadata, {count} chunk cho {', '.join(tenants)}")
    if args.dry_run:
        print(f"[DRY-RUN] SQL {len(sql)} ký tự")
        return 0
    res = run_sql(sql, args)
    if res.returncode != 0:
        print(res.stderr or res.stdout, file=sys.stderr)
        return 1
    print(f"[PASS] Đã nạp {count} chunk toàn văn PDF + phân tích vào RAG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

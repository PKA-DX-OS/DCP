#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Nạp kho văn bản pháp luật và trích dẫn vào Track A (A-LEGAL-01).

- Dữ liệu nguồn: core/legal/danh_muc_van_ban.json (50 văn bản, sinh từ metadata.json)
  và core/legal/citations.json (trích dẫn điều/khoản có kiểm chứng).
- Ghi vào app_construction.legal_refs, app_construction.legal_citations.
- Nạp thêm các đoạn tri thức pháp lý vào core.knowledge_chunks để trợ lý RAG trả citation.
- Idempotent: chạy lại không tạo bản ghi trùng.

Chạy:
    py -3 scripts/seed_legal.py --tenant phuong-a --tenant phuong-b
    py -3 scripts/seed_legal.py --no-docker --psql "C:\\...\\psql.exe"
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception):
        pass

ROOT = Path(__file__).resolve().parent.parent
LEGAL_DIR = ROOT / "core" / "legal"
DOCS_FILE = LEGAL_DIR / "danh_muc_van_ban.json"
CITATIONS_FILE = LEGAL_DIR / "citations.json"

STATUS_MAP = {
    "Còn hiệu lực": "con_hieu_luc",
    "Hết hiệu lực": "het_hieu_luc",
    "Còn hiệu lực một phần": "mot_phan",
    "Chưa có hiệu lực": "chua_hieu_luc",
}


def q(value: Any) -> str:
    """Literal SQL an toàn cho chuỗi/None."""
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Thiếu tệp dữ liệu: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Tệp phải là mảng JSON: {path}")
    return data


def build_sql(docs: list[dict[str, Any]], citations: list[dict[str, Any]], tenants: list[str]) -> str:
    lines: list[str] = ["BEGIN;"]
    for doc in docs:
        status = STATUS_MAP.get(doc.get("status") or "", "can_doi_chieu")
        lines.append(
            "INSERT INTO app_construction.legal_refs "
            "(document_id, code, title, doc_type, issuer, issued_date, effective_date, status, "
            "status_detail, group_name, source_url, sha256, file_name, notes, tags) VALUES ("
            f"{q(doc['document_id'])}, {q(doc['code'])}, {q(doc['title'])}, {q(doc.get('doc_type'))}, "
            f"{q(doc.get('issuer'))}, {q(doc.get('issued_date'))}, {q(doc.get('effective_date'))}, "
            f"{q(status)}, {q(doc.get('status_detail'))}, {q(doc.get('group_name'))}, "
            f"{q(doc.get('source_url'))}, {q(doc.get('sha256'))}, {q(doc.get('file_name'))}, "
            f"{q(doc.get('notes'))}, {q(json.dumps(doc.get('tags') or [], ensure_ascii=False))}::jsonb) "
            "ON CONFLICT (document_id) DO UPDATE SET "
            "code = EXCLUDED.code, title = EXCLUDED.title, doc_type = EXCLUDED.doc_type, "
            "issuer = EXCLUDED.issuer, issued_date = EXCLUDED.issued_date, "
            "effective_date = EXCLUDED.effective_date, status = EXCLUDED.status, "
            "status_detail = EXCLUDED.status_detail, group_name = EXCLUDED.group_name, "
            "source_url = EXCLUDED.source_url, sha256 = EXCLUDED.sha256, "
            "file_name = EXCLUDED.file_name, notes = EXCLUDED.notes, tags = EXCLUDED.tags, "
            "updated_at = now();"
        )

    lines.append(
        "UPDATE app_construction.quy_hoach_van_ban SET legal_document_id = 'VB-13', updated_at = now() "
        "WHERE legal_document_id IS NULL AND ma_van_ban LIKE 'QH-%';"
    )

    docs_by_id = {d["document_id"]: d for d in docs}
    for cit in citations:
        doc = docs_by_id.get(cit["document_id"])
        if doc is None:
            raise SystemExit(f"Trích dẫn {cit['citation_key']} tham chiếu văn bản không tồn tại: {cit['document_id']}")
        status = STATUS_MAP.get(doc.get("status") or "", "can_doi_chieu")
        lines.append(
            "INSERT INTO app_construction.legal_citations "
            "(citation_key, document_id, article, clause, point, topic, summary, effective_date, "
            "status, source_url, sha256, can_doi_chieu) VALUES ("
            f"{q(cit['citation_key'])}, {q(cit['document_id'])}, {q(cit['article'])}, "
            f"{q(cit.get('clause'))}, {q(cit.get('point'))}, {q(cit['topic'])}, {q(cit['summary'])}, "
            f"{q(doc.get('effective_date'))}, {q(status)}, {q(doc.get('source_url'))}, "
            f"{q(doc.get('sha256'))}, {str(bool(cit.get('can_doi_chieu'))).lower()}) "
            "ON CONFLICT (citation_key) DO UPDATE SET "
            "document_id = EXCLUDED.document_id, article = EXCLUDED.article, clause = EXCLUDED.clause, "
            "point = EXCLUDED.point, topic = EXCLUDED.topic, summary = EXCLUDED.summary, "
            "effective_date = EXCLUDED.effective_date, status = EXCLUDED.status, "
            "source_url = EXCLUDED.source_url, sha256 = EXCLUDED.sha256, "
            "can_doi_chieu = EXCLUDED.can_doi_chieu, updated_at = now();"
        )

    for tenant in tenants:
        lines.append(
            "DELETE FROM core.knowledge_chunks "
            f"WHERE tenant = {q(tenant)} AND app = 'cap-phep' AND source LIKE 'legal/%';"
        )
    for cit in citations:
        doc = docs_by_id[cit["document_id"]]
        pos = " ".join(x for x in [cit.get("clause"), cit.get("point")] if x)
        chunk = (
            f"Văn bản {doc['code']} ({doc['title']}) — {cit['article']}"
            f"{', ' + pos if pos else ''}: {cit['summary']} "
            f"Trạng thái hiệu lực: {doc.get('status') or 'cần đối chiếu'}; "
            f"ngày hiệu lực: {doc.get('effective_date') or 'chưa xác định'}."
        )
        for tenant in tenants:
            lines.append(
                "INSERT INTO core.knowledge_chunks (tenant, app, source, chunk) VALUES ("
                f"{q(tenant)}, 'cap-phep', {q('legal/' + cit['citation_key'])}, {q(chunk)});"
            )
    lines.append("NOTIFY pgrst, 'reload schema';")
    lines.append("COMMIT;")
    return "\n".join(lines)


def run_sql(sql: str, args: argparse.Namespace) -> subprocess.CompletedProcess:
    if args.no_docker:
        psql = args.psql or shutil.which("psql")
        if not psql:
            raise SystemExit("Không tìm thấy psql. Truyền --psql hoặc bỏ --no-docker.")
        cmd = [psql, "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1", "-f", "-"]
    else:
        cmd = [
            "docker", "exec", "-i", args.container,
            "psql", "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1", "-f", "-",
        ]
    return subprocess.run(cmd, input=sql, capture_output=True, text=True, encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Nạp kho pháp luật Track A")
    parser.add_argument("--tenant", action="append", dest="tenants", help="Tenant cần nạp tri thức")
    parser.add_argument("--no-docker", action="store_true", help="Dùng psql trên máy thay vì docker exec")
    parser.add_argument("--psql", help="Đường dẫn psql khi dùng --no-docker")
    parser.add_argument("--container", default="dxos-postgres")
    parser.add_argument("--user", default="dxos_owner")
    parser.add_argument("--database", default="dxos")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in số câu lệnh, không chạy")
    args = parser.parse_args(argv)

    tenants = args.tenants or ["phuong-a", "phuong-b"]
    docs = load_json(DOCS_FILE)
    citations = load_json(CITATIONS_FILE)
    sql = build_sql(docs, citations, tenants)

    if args.dry_run:
        print(f"[DRY-RUN] {len(docs)} văn bản, {len(citations)} trích dẫn, tenant: {', '.join(tenants)}")
        return 0

    res = run_sql(sql, args)
    if res.returncode != 0:
        print(res.stderr or res.stdout, file=sys.stderr)
        return 1
    print(f"[PASS] Đã nạp {len(docs)} văn bản, {len(citations)} trích dẫn cho: {', '.join(tenants)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

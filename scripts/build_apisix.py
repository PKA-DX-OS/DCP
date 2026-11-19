#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Ghép APISIX route fragments thành core/apisix/apisix.yaml (P0-05).

- core/apisix/apisix.template.yaml vẫn là nguồn route nền.
- Mỗi file trong core/apisix/routes/*.yaml bổ sung danh sách `routes`.
- Trùng id: fragment thắng (cho phép thay route cũ mà không sửa file lớn).
- Giữ thay thế CSP động như scripts/init.py.

Dùng:
    py -3 scripts/build_apisix.py --check
    py -3 scripts/build_apisix.py --csp "http://localhost:8080 http://localhost:8081"
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "core" / "apisix" / "apisix.template.yaml"
FRAGMENTS = ROOT / "core" / "apisix" / "routes"
OUTPUT = ROOT / "core" / "apisix" / "apisix.yaml"


def load_fragments(fragments_dir: Path) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    if not fragments_dir.exists():
        return routes
    for path in sorted(fragments_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        chunk = data.get("routes") or []
        if not isinstance(chunk, list):
            raise SystemExit(f"{path}: khóa 'routes' phải là danh sách")
        for route in chunk:
            if not isinstance(route, dict) or not route.get("id"):
                raise SystemExit(f"{path}: mỗi route phải có 'id'")
            routes.append(route)
    return routes


def merge_routes(template: dict[str, Any], fragments: list[dict[str, Any]]) -> dict[str, Any]:
    merged = template.get("routes") or []
    by_id = {r.get("id"): idx for idx, r in enumerate(merged) if r.get("id")}
    for route in fragments:
        idx = by_id.get(route["id"])
        if idx is None:
            merged.append(route)
            by_id[route["id"]] = len(merged) - 1
        else:
            merged[idx] = route
    template["routes"] = merged
    return template


def build(csp: Optional[str] = None) -> dict[str, Any]:
    text = TEMPLATE.read_text(encoding="utf-8")
    if csp:
        text = re.sub(r"connect-src 'self' [^;\"]*", f"connect-src 'self' {csp}", text)
    template = yaml.safe_load(text) or {}
    if not isinstance(template, dict):
        raise SystemExit("apisix.template.yaml không phải mapping YAML")
    return merge_routes(template, load_fragments(FRAGMENTS))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ghép APISIX route fragments")
    parser.add_argument("--csp", help="Danh sách origin cho connect-src")
    parser.add_argument("--check", action="store_true", help="Chỉ kiểm tra parse, không ghi tệp")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args(argv)

    data = build(args.csp)
    if args.check:
        ids = [r.get("id") for r in data.get("routes", [])]
        if len(ids) != len(set(ids)):
            raise SystemExit("Trùng id route sau khi ghép")
        print(f"[PASS] {len(ids)} route, YAML hợp lệ.")
        return 0

    out = Path(args.output)
    out.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False) + "\n#END\n",
        encoding="utf-8",
    )
    print(f"[PASS] Đã ghi {out} ({len(data.get('routes', []))} route).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

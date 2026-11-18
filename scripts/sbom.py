#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Sinh SBOM CycloneDX 1.5 từ requirements, Dockerfile và image tags trong compose.yaml.
Đây là inventory thành phần, không thay thế quét lỗ hổng (Trivy/Grype).
"""

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(f"[sbom] Không thể chuyển UTF-8: {exc}", file=sys.stderr)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "sbom"
VERSION = "1.1.0"


def parse_requirements(path: Path):
    components = []
    if not path.exists():
        return components
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==([^\s;]+)", line)
        if not match:
            continue
        name, version = match.group(1), match.group(2)
        components.append({
            "type": "library",
            "name": name,
            "version": version,
            "purl": f"pkg:pypi/{name.lower()}@{version}",
            "properties": [{"name": "dxos:source", "value": str(path.relative_to(ROOT))}],
        })
    return components


def parse_images(path: Path):
    components = []
    if not path.exists():
        return components
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s+image:\s+([^\s#]+)", raw)
        if not match:
            continue
        image = match.group(1)
        if image.startswith("dxos/"):
            continue
        if ":" in image:
            name, tag = image.rsplit(":", 1)
        else:
            name, tag = image, "latest"
        components.append({
            "type": "container",
            "name": name,
            "version": tag,
            "purl": f"pkg:docker/{name}@{tag}",
            "properties": [{"name": "dxos:source", "value": "compose.yaml"}],
        })
    return components


def parse_apt(path: Path):
    components = []
    if not path.exists():
        return components
    text = path.read_text(encoding="utf-8")
    match = re.search(r"apt-get install[^\\\n]*(?:\\\n[^\n]*)*", text)
    if not match:
        return components
    block = match.group(0)
    packages = re.findall(r"\b([a-z0-9][a-z0-9+.-]+)\b", block)
    ignored = {"apt-get", "install", "update", "rm", "rf", "var", "lib", "apt", "lists", "y", "no-install-recommends", "&&"}
    for name in sorted(set(packages) - ignored):
        components.append({
            "type": "library",
            "name": name,
            "version": "debian",
            "purl": f"pkg:deb/debian/{name}",
            "properties": [{"name": "dxos:source", "value": str(path.relative_to(ROOT))}],
        })
    return components


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    components = []
    components += parse_requirements(ROOT / "services" / "requirements.txt")
    components += parse_requirements(ROOT / "requirements-dev.txt")
    components += parse_images(ROOT / "compose.yaml")
    components += parse_apt(ROOT / "services" / "Dockerfile")

    seen = set()
    unique = []
    for comp in components:
        key = comp["purl"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(comp)

    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [{"vendor": "DX-OS", "name": "scripts/sbom.py", "version": VERSION}],
            "component": {
                "type": "application",
                "name": "dxos-open-core",
                "version": VERSION,
                "licenses": [{"license": {"id": "AGPL-3.0-or-later"}}],
            },
        },
        "components": unique,
    }
    out = OUT_DIR / f"dxos-{VERSION}.cdx.json"
    out.write_text(json.dumps(bom, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[sbom] Đã ghi {out} ({len(unique)} thành phần)")


if __name__ == "__main__":
    main()

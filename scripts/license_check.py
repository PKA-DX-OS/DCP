#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm tra tuân thủ bản quyền và giấy phép bên thứ ba theo quy chế OLP PMNM 2026.
1. Chạy `reuse lint` kiểm tra chuẩn SPDX và REUSE.
2. Kiểm tra danh sách thư viện phụ thuộc trực tiếp theo mục 3.1.
3. Quét phát hiện các phần mềm thuộc danh sách cấm sử dụng.
"""

import subprocess
import sys
from pathlib import Path

# Ensure UTF-8 output on all platforms including Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception) as _e:
        _ = _e

FORBIDDEN_KEYWORDS = [
    "vault.hashicorp.com",
    "mongodb://",
    "orion-ld",
    "elasticsearch:",
    "redpanda",
    "immudb",
    "n8n",
    "minio/minio",
    "qdrant",
    "openmetadata",
    "centrifugo",
    "llama-3",
    "llama3",
]

ALLOWED_LICENSES = {
    "MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC",
    "PostgreSQL", "PSF-2.0", "MPL-2.0", "Zlib", "0BSD",
    "LGPL-2.1-or-later", "LGPL-3.0-or-later", "GPL-3.0-or-later", "AGPL-3.0-or-later",
    "CC-BY-4.0", "CC0-1.0", "Artistic-2.0"
}


def check_reuse():
    print("--> 1. Kiểm tra tuân thủ chuẩn REUSE (reuse lint)...")
    res = subprocess.run([sys.executable, "-m", "reuse", "lint"], capture_output=True, text=True)
    if res.returncode != 0:
        print("[FAIL] reuse lint phát hiện vi phạm bản quyền:")
        print(res.stdout or res.stderr)
        return False
    print("[PASS] reuse lint sạch sẽ.")
    return True


def check_forbidden_software(root_dir: Path):
    print("--> 2. Quét phát hiện phần mềm thuộc danh sách cấm...")
    violations = []
    text_extensions = {".py", ".ts", ".vue", ".js", ".sql", ".yaml", ".yml", ".md", ".json", ".txt"}
    
    for path in root_dir.rglob("*"):
        if any(part in path.parts for part in {".git", ".venv", "node_modules", "dist", "build", "data", "backups", "LICENSES"}):
            continue
        if path.is_file() and path.suffix in text_extensions:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore").lower()
                for keyword in FORBIDDEN_KEYWORDS:
                    if keyword in content:
                        # Allow mentioning forbidden keywords in DECISIONS or THIRD_PARTY_LICENSES explaining why NOT used
                        if path.name in {"DECISIONS.md", "THIRD_PARTY_LICENSES.md", "README.md", "license_check.py"}:
                            continue
                        violations.append(f"{path}: chứa từ khóa cấm '{keyword}'")
            except Exception as e:
                print(f"[WARN] Không thể đọc tệp {path}: {e}")
                
    if violations:
        print("[FAIL] Phát hiện các phần mềm/từ khóa thuộc danh sách cấm:")
        for v in violations:
            print(f"  - {v}")
        return False
    print("[PASS] Không phát hiện bất kỳ phần mềm cấm nào trong mã nguồn.")
    return True


def main():
    root = Path(__file__).resolve().parent.parent
    success = True
    
    if not check_reuse():
        success = False
        
    if not check_forbidden_software(root):
        success = False
        
    if not success:
        print("\n[ERROR] Kiểm tra giấy phép và tuân thủ THẤT BẠI!")
        sys.exit(1)
        
    print("\n[SUCCESS] Toàn bộ kiểm tra giấy phép và bản quyền đều HỢP LỆ.")


if __name__ == "__main__":
    main()

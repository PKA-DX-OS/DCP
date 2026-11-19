#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import sys
import os
import re

p_mock = r'\b' + 'M' + 'ock[A-Za-z0-9_]*'
p_mem = '_' + 'memory_store'
p_signed = '_' + 'SIGNED_DOCS_STORE'
p_local = '_' + 'LOCAL_PRIVATE_KEY'
p_versig = 'verify_' + 'signature\\s*:\\s*False'
p_offline = 'Offline' + '-Verified'
p_test = 'startswith\\(b["\']' + 'TEST'
p_swallow = 'except\\s+Exception\\s*:\\s*' + 'pass\\b'
p_empty_sha = 'e3b0c44298fc' + '[0-9a-fA-F]*b855'
p_trend = '["\']trend["\']\\s*:\\s*["\']'
p_backup_key = 'dxos_secure_backup_key_2026'
p_default_passwords = r'(dxos_dev_postgres_password_2026|dxos_dev_openbao_root_token_2026|test_e2e_secret_key_2026)'
p_ui_rel_time = r'["\'][^"\']*\b(\d+\s*(phút|giờ|ngày)\s*trước)\b[^"\']*["\']'
p_ui_static_countdown = r'["\']\s*\d+d\s+\d+h\s+\d+m\s*["\']'
p_ui_hardcoded_uuid = r'(61e0ee9a-3581-40d6-84be-8d505b722aa3|636fe597-987d-4ba6-8f3b-c290a612dc53)'
p_ui_demo_user_option = r'\{\s*value\s*:\s*["\'](td\.(binh|cuong)|ld\.hoa|mc\.thu|cdt\.(minh|lan))["\']'
p_ui_demo_user_default = r'nguoiThamDinh\s*:\s*["\'](td\.(binh|cuong)|ld\.hoa|mc\.thu|cdt\.(minh|lan))["\']'
p_default_tenant = r'\bor\s+["\']phuong-[a-z]["\']'
p_sql_fake_person = r":=\s*'[A-ZĐÀ-Ỹ][^'\s]*\s[A-ZĐÀ-Ỹ][^'\s]*\s[A-ZĐÀ-Ỹ][^'\s]*'"
p_ui_demo_user_span = r'>\s*(td\.(binh|cuong)|ld\.hoa|mc\.thu|cdt\.(minh|lan))\s*<'

FORBIDDEN_PATTERNS = [
    (re.compile(p_mock), "Fake variable/class"),
    (re.compile(p_mem), "Memory fallback store"),
    (re.compile(p_signed), "Signed docs RAM store"),
    (re.compile(p_local), "Local private key"),
    (re.compile(p_versig), "Disabled signature verification"),
    (re.compile(p_offline), "Fake verified label"),
    (re.compile(p_test), "Test file prefix bypass"),
    (re.compile(p_swallow), "Bare exception pass"),
    (re.compile(p_empty_sha), "Empty string SHA-256 hash"),
    (re.compile(p_trend), "Hardcoded trend metric string"),
    (re.compile(p_backup_key), "Hardcoded insecure backup key"),
    (re.compile(p_default_passwords), "Hardcoded default secret in production code"),
    (re.compile(p_ui_rel_time), "Hardcoded UI relative time fake string"),
    (re.compile(p_ui_static_countdown), "Hardcoded UI static countdown string"),
    (re.compile(p_ui_hardcoded_uuid), "Hardcoded UI officer UUID"),
    (re.compile(p_ui_demo_user_option), "Hardcoded demo user option array in UI"),
    (re.compile(p_ui_demo_user_default), "Hardcoded demo user default value in UI"),
    (re.compile(p_ui_demo_user_span), "Hardcoded demo user span badge in UI"),
    (re.compile(p_default_tenant), "Hardcoded default tenant fallback (U-04)"),
    (re.compile(p_sql_fake_person), "Hardcoded person name fallback in SQL (U-05)"),
]

EXCLUDED_DIRS = {".git", "__pycache__", "tests", "dist", "node_modules", ".pytest_cache", ".venv", "vendor"}
TARGET_DIRS = ["services", "scripts", "ops", "tools", "apps", "deploy"]


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    violations = []

    for target in TARGET_DIRS:
        target_path = os.path.join(root, target)
        if not os.path.exists(target_path):
            continue
        for dirpath, dirnames, filenames in os.walk(target_path):
            dirnames[:] = [d for d in dirnames if d.lower() not in EXCLUDED_DIRS]
            for fname in filenames:
                if fname == "check_no_fakes.py":
                    continue
                if not (fname.endswith(".py") or fname.endswith(".sql") or fname.endswith(".env") or fname.endswith(".yaml") or fname.endswith(".yml") or fname.endswith(".vue") or fname.endswith(".ts") or fname.endswith(".js")):
                    continue

                file_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(file_path, root)

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                except Exception:
                    continue

                in_except = False
                except_line = ""
                except_indent = 0

                for idx, line in enumerate(lines, 1):
                    # 1. Regex kiểm tra từng dòng
                    for pattern, desc in FORBIDDEN_PATTERNS:
                        if pattern.search(line):
                            violations.append((rel_path, idx, desc, line.strip()))

                    # 2. Bare exception pass
                    if idx < len(lines):
                        combined = line.strip() + " " + lines[idx].strip()
                        if re.search(r'except\s+Exception\s*:\s*pass\b', combined):
                            violations.append((rel_path, idx, "except Exception: pass bare swallow", combined))

                    # 3. Quét trạng thái khối except theo thụt đầu dòng (indentation)
                    stripped = line.strip()
                    if stripped.startswith("except ") or stripped.startswith("except:"):
                        in_except = True
                        except_line = stripped
                        except_indent = len(line) - len(line.lstrip())
                    elif in_except:
                        current_indent = len(line) - len(line.lstrip())
                        if stripped and current_indent <= except_indent and not stripped.startswith("#"):
                            in_except = False
                        else:
                            if "FileNotFoundError" in except_line and "return True" in stripped:
                                violations.append((rel_path, idx, "except FileNotFoundError returning True", stripped))
                            if "print(" in stripped and any(k in stripped for k in ["[PASS]", "thành công", "thanh cong"]):
                                violations.append((rel_path, idx, "Printing [PASS] or thanh cong inside except block", stripped))

    if violations:
        print(f"[FAIL] Phat hien {len(violations)} mau ma gia:")
        for rel_path, idx, desc, line_content in violations:
            print(f"  - {rel_path}:{idx}: [{desc}] -> {line_content}")
        sys.exit(1)
    else:
        print("[PASS] Khong con bat ky ma gia nao trong he thong!")
        sys.exit(0)


if __name__ == "__main__":
    main()

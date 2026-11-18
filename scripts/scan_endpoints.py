# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Rà soát toàn bộ endpoint trong services/*/main.py (Q-01 bước 5).
Kiểm tra cơ chế xác thực: JWT token, Internal Token, hoặc Public Endpoint có lý do chính đáng.
"""

import ast
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SERVICES_DIR = ROOT / "services"

PUBLIC_ALLOWLIST = {
    "/health": "Kiểm tra tình trạng sức khỏe của container/dịch vụ (Docker/K8s/APISIX healthcheck)",
    "/livez": "Liveness probe",
    "/readyz": "Readiness probe",
    "/metrics": "Thu thập chỉ số vận hành Prometheus (nội bộ hạ tầng quan sát)",
    "/api/v1/public/docs/verify/{public_code}": "Cổng tra cứu xác minh giấy phép và chữ ký số công khai cho người dân",
    "/kiem-tra/{public_code}": "Tra cứu thông tin xác thực chứng thư và chữ ký số công khai của giấy phép",
    "/kiem-tra/{public_code}/verify-file": "Tải tệp PDF lên để đối soát băm SHA256 và chữ ký số số hóa công khai",
}

INTERNAL_PREFIXES = ("/internal",)


def scan_service_endpoints():
    endpoints = []
    for p in sorted(SERVICES_DIR.glob("*/main.py")):
        service = p.parent.name
        content = p.read_text(encoding="utf-8")
        tree = ast.parse(content)
        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        method = dec.func.attr.upper()
                        if method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                            route_path = ""
                            if dec.args and isinstance(dec.args[0], ast.Constant):
                                route_path = str(dec.args[0].value)

                            # Kiểm tra cơ chế xác thực trong thân hàm hoặc decorator
                            func_source = "\n".join(lines[node.lineno - 1 : node.end_lineno])
                            has_jwt = "verify_jwt_token" in func_source or "claims" in [a.arg for a in node.args.args]
                            has_internal = "X-DXOS-Internal-Token" in func_source or any(route_path.startswith(pre) for pre in INTERNAL_PREFIXES)

                            auth_type = "JWT" if has_jwt else ("INTERNAL" if has_internal else "NONE")
                            reason = PUBLIC_ALLOWLIST.get(route_path, "")

                            endpoints.append({
                                "service": service,
                                "method": method,
                                "path": route_path,
                                "func": node.name,
                                "auth_type": auth_type,
                                "reason": reason,
                            })
    return endpoints


if __name__ == "__main__":
    eps = scan_service_endpoints()
    print("| Dịch vụ | Phương thức | Đường dẫn Endpoint | Hàm xử lý | Cơ chế xác thực | Lý do cho phép công khai |")
    print("|---|---|---|---|---|---|")
    for e in eps:
        reason = e["reason"] if e["auth_type"] == "NONE" else ("Xác thực qua JWT Keycloak" if e["auth_type"] == "JWT" else "Xác thực qua X-DXOS-Internal-Token")
        print(f"| `{e['service']}` | `{e['method']}` | `{e['path']}` | `{e['func']}` | `{e['auth_type']}` | {reason} |")

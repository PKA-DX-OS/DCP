# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy cho N-08 và N-09:
- N-08: Cấu hình LAN IP động không làm bẩn Git; apisix.yaml sinh từ template;
        redirectUris và webOrigins sinh từ PUBLIC_BASE_URL (hỗ trợ nhiều URL).
- N-09: Client công khai dxos-web bị tắt directAccessGrantsEnabled (không được đăng nhập mật khẩu trực tiếp);
        Chỉ dx-test được dùng password grant (và chỉ tạo khi DEMO_MODE=true).
"""

import json
import subprocess
import tempfile
from pathlib import Path

import httpx

from tests.integration.conftest import load_demo_accounts


def test_N08_apisix_template_and_dynamic_lan_config():
    root = Path(__file__).resolve().parent.parent.parent

    # 1. Kiểm tra apisix.template.yaml tồn tại
    tpl_path = root / "core" / "apisix" / "apisix.template.yaml"
    assert tpl_path.exists(), "Tệp core/apisix/apisix.template.yaml phải tồn tại"

    # 2. Kiểm tra apisix.yaml được ignore trong git
    if (root / ".git").exists():
        status_proc = subprocess.run(
            ["git", "check-ignore", "core/apisix/apisix.yaml"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        assert status_proc.returncode == 0, "core/apisix/apisix.yaml phải được liệt kê trong .gitignore"
    else:
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        assert "core/apisix/apisix.yaml" in gitignore, "core/apisix/apisix.yaml phải được liệt kê trong .gitignore"

    # 3. Kiểm tra render_realm_dxos hỗ trợ nhiều IP LAN từ PUBLIC_BASE_URL
    from scripts.init import render_realm_dxos

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_realm_out = Path(tmpdir) / "realm-test.json"
        env_test = {
            "PUBLIC_BASE_URL": "http://localhost:8080,http://192.168.1.88:8080",
            "DEMO_MODE": "false",
            "APISIX_OIDC_SECRET": "test_apisix_secret",
            "DX_SEED_SECRET": "test_seed_secret",
        }
        render_realm_dxos(
            root / "core" / "keycloak" / "realm-dxos.template.json",
            tmp_realm_out,
            env_test,
        )
        assert tmp_realm_out.exists(), "Phải kết xuất được realm JSON"
        realm_data = json.loads(tmp_realm_out.read_text(encoding="utf-8"))

        # Kiểm tra dxos-web
        dxos_web = next((c for c in realm_data["clients"] if c["clientId"] == "dxos-web"), None)
        assert dxos_web is not None
        assert dxos_web["directAccessGrantsEnabled"] is False
        assert "http://192.168.1.88:8080/*" in dxos_web["redirectUris"]
        assert "http://192.168.1.88:8080" in dxos_web["webOrigins"]

        # Kiểm tra dx-test bị loại bỏ khi DEMO_MODE=false
        dx_test = next((c for c in realm_data["clients"] if c["clientId"] == "dx-test"), None)
        assert dx_test is None, "Khi DEMO_MODE=false, dx-test không được tạo"


def test_N09_public_client_password_grant_disabled():
    """
    Kiểm tra bảo mật N-09:
    - POST /auth/realms/dxos/protocol/openid-connect/token với client_id=dxos-web và grant_type=password
      phải trả về lỗi 400 (hoặc 401) unauthorized_client.
    - POST với client_id=dx-test và grant_type=password phải thành công trả về access_token.
    """
    gateway_url = "http://localhost:8080"
    token_endpoint = f"{gateway_url}/auth/realms/dxos/protocol/openid-connect/token"

    passwords = load_demo_accounts()
    test_password = passwords.get("ld.hoa", "dev_test_password_2026")

    # 1. Thử đăng nhập bằng password grant qua client công khai dxos-web -> Phải bị từ chối
    with httpx.Client(timeout=10.0) as client:
        res_web = client.post(
            token_endpoint,
            data={
                "client_id": "dxos-web",
                "grant_type": "password",
                "username": "ld.hoa",
                "password": test_password,
            },
        )
        assert res_web.status_code in (400, 401), (
            f"Client công khai dxos-web không được phép dùng password grant, mong đợi 400/401: {res_web.status_code} {res_web.text}"
        )
        body = res_web.json()
        assert body.get("error") == "unauthorized_client", (
            f"Mong đợi lỗi 'unauthorized_client', thực tế: {body}"
        )

        # 2. Thử đăng nhập qua client kiểm thử dx-test -> Thành công nhận JWT
        res_test = client.post(
            token_endpoint,
            data={
                "client_id": "dx-test",
                "grant_type": "password",
                "username": "ld.hoa",
                "password": test_password,
            },
        )
        assert res_test.status_code == 200, (
            f"Client dx-test phải đăng nhập được trong môi trường demo: {res_test.status_code} {res_test.text}"
        )
        assert "access_token" in res_test.json(), "dx-test phải trả về access_token hợp lệ"

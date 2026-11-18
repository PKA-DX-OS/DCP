# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy cho lỗi P-05:
- Danh bạ cán bộ core.users_directory được đồng bộ động từ Keycloak IdP.
- Tạo cán bộ mới td.moi với vai trò tham-dinh và tenant phuong-a.
- Sau khi đồng bộ, ld.hoa gọi ds_can_bo('tham-dinh') thấy td.moi.
- Khi td.moi bị vô hiệu hóa trên Keycloak, sau khi đồng bộ, td.moi không còn xuất hiện trong ds_can_bo.
"""

import secrets
import subprocess

import httpx

from tests.integration._auth import GATEWAY_URL, ROOT, get_token


def _env(key: str) -> str | None:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return None


def get_keycloak_admin_token() -> tuple[httpx.Client, str]:
    pw = _env("KEYCLOAK_ADMIN_PASSWORD")
    assert pw, "Thiếu KEYCLOAK_ADMIN_PASSWORD trong .env"
    user = _env("KEYCLOAK_ADMIN") or "admin"
    last = None
    for base in ("http://127.0.0.1:8081/auth", "http://localhost:8080/auth"):
        client = httpx.Client(base_url=base, timeout=10.0)
        try:
            r = client.post(
                "/realms/master/protocol/openid-connect/token",
                data={"client_id": "admin-cli", "username": user, "password": pw, "grant_type": "password"},
            )
            if r.status_code == 200:
                return client, r.json()["access_token"]
            last = f"{base}: HTTP {r.status_code}"
        except httpx.HTTPError as e:
            last = f"{base}: {e}"
        client.close()
    raise AssertionError(f"Không lấy được token quản trị Keycloak ({last})")


def run_sync_command():
    """Chạy lệnh đồng bộ người dùng sync-users thông qua tools container."""
    cmd = ["docker", "compose", "--profile", "tools", "run", "--rm", "-T", "tools", "scripts/sync_users.py"]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, f"sync_users lỗi: {res.stderr[-500:]}"
    return res.stdout


def test_P05_sync_users_keycloak_to_directory():
    kc_client, admin_token = get_keycloak_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    test_username = "td.moi"
    user_id = None

    try:
        # 1. Dọn dẹp tài khoản cũ nếu có từ lần chạy trước
        old_users_res = kc_client.get(f"/admin/realms/dxos/users?username={test_username}", headers=headers)
        if old_users_res.status_code == 200:
            for u in old_users_res.json():
                if u.get("username") == test_username:
                    kc_client.delete(f"/admin/realms/dxos/users/{u['id']}", headers=headers)

        # 2. Tạo người dùng mới td.moi trên Keycloak
        create_payload = {
            "username": test_username,
            "enabled": True,
            "firstName": "Thẩm Định",
            "lastName": "Mới",
            "email": "td.moi@phuonga.gov.vn",
            "attributes": {
                "tenant": ["phuong-a"]
            },
            "credentials": [{
                "type": "password",
                "value": secrets.token_urlsafe(16) + "Aa1!",
                "temporary": False
            }]
        }
        res_create = kc_client.post("/admin/realms/dxos/users", json=create_payload, headers=headers)
        assert res_create.status_code in (200, 201), f"Lỗi tạo user trên Keycloak: {res_create.status_code} - {res_create.text}"

        # Lấy ID của user vừa tạo
        get_user_res = kc_client.get(f"/admin/realms/dxos/users?username={test_username}", headers=headers)
        assert get_user_res.status_code == 200 and get_user_res.json(), "Không tìm thấy user vừa tạo trên Keycloak"
        user_obj = [u for u in get_user_res.json() if u.get("username") == test_username][0]
        user_id = user_obj["id"]

        # 3. Gán vai trò app:cap-phep:tham-dinh cho td.moi
        roles_res = kc_client.get("/admin/realms/dxos/roles", headers=headers)
        assert roles_res.status_code == 200, "Lỗi đọc danh sách vai trò Keycloak"
        role_candidates = [r for r in roles_res.json() if r.get("name") in ("app:cap-phep:tham-dinh", "tham-dinh")]
        assert role_candidates, "Không tìm thấy vai trò tham định trong Keycloak realm dxos"
        role_to_assign = role_candidates[0]

        assign_res = kc_client.post(
            f"/admin/realms/dxos/users/{user_id}/role-mappings/realm",
            json=[role_to_assign],
            headers=headers
        )
        assert assign_res.status_code in (200, 204), f"Lỗi gán vai trò: {assign_res.text}"

        # 4. Thực thi đồng bộ danh bạ
        sync_out = run_sync_command()
        assert "[PASS]" in sync_out or "thành công" in sync_out, f"Đồng bộ thất bại: {sync_out}"

        # 5. ld.hoa gọi ds_can_bo('tham-dinh') -> phải thấy td.moi
        token_ld = get_token("ld.hoa")
        with httpx.Client(base_url=GATEWAY_URL, timeout=10.0) as client:
            resp_active = client.post(
                "/api/v1/rest/rpc/ds_can_bo",
                headers={"Authorization": f"Bearer {token_ld}", "Content-Type": "application/json"},
                json={"p_vai": "tham-dinh"}
            )
            assert resp_active.status_code == 200, f"ld.hoa gọi ds_can_bo lỗi: {resp_active.status_code} - {resp_active.text}"
            active_list = resp_active.json()
            active_usernames = [u.get("username") for u in active_list]
            assert test_username in active_usernames, f"Kỳ vọng {test_username} có trong danh bạ cán bộ, thực tế: {active_usernames}"

        # 6. Vô hiệu hóa td.moi trên Keycloak (enabled = False)
        disable_res = kc_client.put(
            f"/admin/realms/dxos/users/{user_id}",
            json={"enabled": False},
            headers=headers
        )
        assert disable_res.status_code in (200, 204), f"Lỗi vô hiệu hóa user: {disable_res.text}"

        # 7. Đồng bộ lại danh bạ
        run_sync_command()

        # 8. ld.hoa gọi lại ds_can_bo('tham-dinh') -> td.moi không còn xuất hiện
        with httpx.Client(base_url=GATEWAY_URL, timeout=10.0) as client:
            resp_disabled = client.post(
                "/api/v1/rest/rpc/ds_can_bo",
                headers={"Authorization": f"Bearer {token_ld}", "Content-Type": "application/json"},
                json={"p_vai": "tham-dinh"}
            )
            assert resp_disabled.status_code == 200, f"ld.hoa gọi ds_can_bo lỗi: {resp_disabled.status_code} - {resp_disabled.text}"
            disabled_list = resp_disabled.json()
            disabled_usernames = [u.get("username") for u in disabled_list]
            assert test_username not in disabled_usernames, f"Kỳ vọng {test_username} KHÔNG có trong danh bạ sau khi bị vô hiệu hóa, thực tế: {disabled_usernames}"

    finally:
        # Dọn dẹp: Xóa user khỏi Keycloak và đồng bộ lại để dọn danh bạ
        if user_id:
            try:
                kc_client.delete(f"/admin/realms/dxos/users/{user_id}", headers=headers)
                run_sync_command()
            except Exception:
                pass
        kc_client.close()

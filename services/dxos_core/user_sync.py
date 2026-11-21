# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Mô-đun đồng bộ danh mục người dùng từ Keycloak IdP sang core.users_directory (P-05).
- Đồng bộ các thuộc tính người dùng: id, username, email, full_name, tenant, roles, active.
- Tự động đặt active = false khi người dùng bị vô hiệu hóa (enabled = false) hoặc xóa khỏi Keycloak.
- Đồng bộ cấu hình bảo mật cho client dxos-web (chống rò rỉ mã token, dynamic origins).
- Đồng bộ cài đặt giao diện/ngôn ngữ của realm từ core/keycloak/realm-dxos.template.json: realm chỉ
  được import lần đầu, nên realm đã tạo trước đó không nhận theme đăng nhập và tiếng Việt nếu không đồng bộ.
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import List, Optional, Tuple
import httpx
from dxos_core.config import settings
from dxos_core.db import get_db_pool

logger = logging.getLogger("dxos.user_sync")


async def get_admin_client() -> Tuple[Optional[httpx.AsyncClient], Optional[str], Optional[str]]:
    """Lấy client HTTP và access token quản trị Keycloak."""
    candidate_urls = [
        settings.keycloak_internal_url,
        "http://keycloak:8080/auth",
        "http://localhost:8081/auth",
        "http://localhost:8080/auth",
        settings.keycloak_url,
    ]
    kc_admin = settings.keycloak_admin or "admin"
    kc_password = settings.keycloak_admin_password
    if not kc_password:
        for p in [Path(".env"), Path("/app/.env"), Path(__file__).resolve().parent.parent.parent / ".env"]:
            if p.exists():
                try:
                    for line in p.read_text(encoding="utf-8").splitlines():
                        if line.startswith("KEYCLOAK_ADMIN_PASSWORD="):
                            kc_password = line.split("=", 1)[1].strip()
                        elif line.startswith("KEYCLOAK_ADMIN="):
                            kc_admin = line.split("=", 1)[1].strip()
                    if kc_password:
                        break
                except Exception as read_err:
                    logger.debug("Không thể đọc tệp bí mật %s: %s", p, read_err)

    for base in candidate_urls:
        if not base:
            continue
        clean_base = base.rstrip("/")
        client = httpx.AsyncClient(timeout=10.0)

        # 1. Thử xác thực với tài khoản admin-cli
        try:
            token_url = f"{clean_base}/realms/master/protocol/openid-connect/token"
            tok_res = await client.post(
                token_url,
                data={
                    "client_id": "admin-cli",
                    "username": kc_admin,
                    "password": kc_password,
                    "grant_type": "password",
                },
            )
            if tok_res.status_code == 200:
                admin_token = tok_res.json()["access_token"]
                return client, clean_base, admin_token
        except Exception as auth_err:
            logger.debug("Không thể xác thực qua admin-cli: %s", auth_err)

        # 2. Thử xác thực với client credentials của dx-seed nếu có
        seed_secret = os.getenv("DX_SEED_SECRET") or os.getenv("KEYCLOAK_SEED_SECRET")
        if seed_secret:
            try:
                seed_token_url = f"{clean_base}/realms/{settings.keycloak_realm}/protocol/openid-connect/token"
                tok_res = await client.post(
                    seed_token_url,
                    data={
                        "client_id": "dx-seed",
                        "client_secret": seed_secret,
                        "grant_type": "client_credentials",
                    },
                )
                if tok_res.status_code == 200:
                    admin_token = tok_res.json()["access_token"]
                    return client, clean_base, admin_token
            except Exception as seed_err:
                logger.debug("Không thể xác thực qua dx-seed: %s", seed_err)

        await client.aclose()

    return None, None, None


# Chỉ các khóa giao diện/ngôn ngữ; không ghi đè chính sách bảo mật hay client của realm đang chạy
REALM_KEYS = ("loginTheme", "internationalizationEnabled", "supportedLocales", "defaultLocale")
REALM_TEMPLATE = Path(__file__).resolve().parent.parent.parent / "core" / "keycloak" / "realm-dxos.template.json"


def realm_settings_from_template(path: Path = REALM_TEMPLATE) -> dict:
    """Lấy các khóa REALM_KEYS có trong template; không có tệp thì trả rỗng."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.warning("Không đọc được %s: %s", path, e)
        return {}
    return {k: data[k] for k in REALM_KEYS if k in data}


def realm_settings_diff(current: dict, wanted: dict) -> dict:
    """Khóa cần cập nhật: giá trị trên realm khác template (danh sách so không theo thứ tự)."""
    def chuan(v):
        return sorted(v) if isinstance(v, list) else v

    return {k: v for k, v in wanted.items() if chuan(current.get(k)) != chuan(v)}


async def sync_realm_settings(client: httpx.AsyncClient, base_url: str, admin_token: str) -> dict:
    """Đặt theme đăng nhập và ngôn ngữ của realm theo template; trả về các khóa đã đổi."""
    wanted = realm_settings_from_template()
    if not wanted:
        return {}
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    realm_url = f"{base_url}/admin/realms/{settings.keycloak_realm}"
    try:
        res = await client.get(realm_url, headers=headers)
        if res.status_code != 200:
            logger.warning("Không đọc được cấu hình realm: HTTP %s", res.status_code)
            return {}
        doi = realm_settings_diff(res.json(), wanted)
        if not doi:
            return {}
        put_res = await client.put(realm_url, json=doi, headers=headers)
        if put_res.status_code in (200, 204):
            logger.info("Đã cập nhật cài đặt realm: %s", ", ".join(sorted(doi)))
            return doi
        logger.warning("Không cập nhật được realm: HTTP %s", put_res.status_code)
    except Exception as e:
        logger.warning(f"Lỗi khi đồng bộ cài đặt realm: {e}")
    return {}


async def sync_clients(client: httpx.AsyncClient, base_url: str, admin_token: str) -> None:
    """Cập nhật chính sách bảo mật cho các Keycloak client (N-08, N-09)."""
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    clients_url = f"{base_url}/admin/realms/{settings.keycloak_realm}/clients"
    try:
        res = await client.get(f"{clients_url}?clientId=dxos-web", headers=headers)
        if res.status_code == 200 and res.json():
            c_obj = res.json()[0]
            c_id = c_obj["id"]
            c_obj["directAccessGrantsEnabled"] = False
            raw_pub = os.getenv("PUBLIC_BASE_URL", "http://localhost:8080")
            pub_urls = [u.strip().rstrip("/") for u in raw_pub.split(",") if u.strip()]
            redirects = ["http://localhost:8080/*", "http://127.0.0.1:8080/*"]
            origins = ["http://localhost:8080", "http://127.0.0.1:8080", "+"]
            for u in pub_urls:
                r = f"{u}/*"
                if r not in redirects:
                    redirects.append(r)
                if u not in origins:
                    origins.append(u)
            c_obj["redirectUris"] = redirects
            c_obj["webOrigins"] = origins
            put_res = await client.put(f"{clients_url}/{c_id}", json=c_obj, headers=headers)
            if put_res.status_code in (200, 204):
                logger.info("Đã cập nhật cấu hình bảo mật client dxos-web.")
    except Exception as e:
        logger.warning(f"Lỗi khi đồng bộ cấu hình client dxos-web: {e}")


async def sync_realm_roles(client: httpx.AsyncClient, base_url: str, admin_token: str) -> None:
    """Đảm bảo các vai chuẩn của realm tồn tại và gán vai mẫu nếu cần."""
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    roles_url = f"{base_url}/admin/realms/{settings.keycloak_realm}/roles"
    try:
        res = await client.get(roles_url, headers=headers)
        existing = {}
        if res.status_code == 200:
            existing = {r.get("name"): r for r in res.json()}

        steward_role_name = "dx:data-steward"
        steward_role = existing.get(steward_role_name)
        if not steward_role:
            create_payload = {
                "name": steward_role_name,
                "description": "Chủ quản dữ liệu (Data Steward)",
            }
            c_res = await client.post(roles_url, json=create_payload, headers=headers)
            if c_res.status_code in (201, 204):
                logger.info("Đã tạo vai %s trên realm %s", steward_role_name, settings.keycloak_realm)
                get_r = await client.get(f"{roles_url}/{steward_role_name}", headers=headers)
                if get_r.status_code == 200:
                    steward_role = get_r.json()
            elif c_res.status_code == 409:
                get_r = await client.get(f"{roles_url}/{steward_role_name}", headers=headers)
                if get_r.status_code == 200:
                    steward_role = get_r.json()
            else:
                logger.warning("Không tạo được vai %s: HTTP %s", steward_role_name, c_res.status_code)

        # Gán vai cho tài khoản demo mc.thu nếu chưa có
        if steward_role:
            target_username = "mc.thu"
            users_url = f"{base_url}/admin/realms/{settings.keycloak_realm}/users"
            u_res = await client.get(f"{users_url}?username={target_username}", headers=headers)
            if u_res.status_code == 200 and u_res.json():
                matched_users = [u for u in u_res.json() if u.get("username") == target_username]
                if matched_users:
                    user_obj = matched_users[0]
                    user_id = user_obj["id"]
                    user_roles_url = f"{users_url}/{user_id}/role-mappings/realm"
                    ur_res = await client.get(user_roles_url, headers=headers)
                    if ur_res.status_code == 200:
                        has_steward = any(r.get("name") == steward_role_name for r in ur_res.json())
                        if not has_steward:
                            assign_res = await client.post(user_roles_url, json=[steward_role], headers=headers)
                            if assign_res.status_code in (200, 204):
                                logger.info("Đã gán vai %s cho tài khoản demo %s", steward_role_name, target_username)
                            else:
                                logger.warning(
                                    "Không gán được vai %s cho %s: HTTP %s",
                                    steward_role_name, target_username, assign_res.status_code,
                                )
    except Exception as e:
        logger.warning(f"Lỗi khi đồng bộ vai realm: {e}")


async def sync_keycloak_users() -> dict:
    """Đồng bộ toàn bộ danh mục người dùng từ Keycloak IdP sang core.users_directory."""
    client, base_url, admin_token = await get_admin_client()
    if not client or not admin_token:
        err_msg = "Không kết nối được Keycloak admin API để đồng bộ người dùng!"
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    try:
        realm_doi = await sync_realm_settings(client, base_url, admin_token)
        await sync_clients(client, base_url, admin_token)
        await sync_realm_roles(client, base_url, admin_token)
        users_url = f"{base_url}/admin/realms/{settings.keycloak_realm}/users"
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

        u_res = await client.get(f"{users_url}?max=1000", headers=headers)
        if u_res.status_code != 200:
            err_msg = f"Không lấy được danh sách người dùng từ Keycloak: HTTP {u_res.status_code}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        users = u_res.json()
        logger.info(f"Tìm thấy {len(users)} người dùng trên Keycloak.")

        pool = await get_db_pool()
        if not pool:
            err_msg = "Không kết nối được cơ sở dữ liệu để đồng bộ người dùng!"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        synced_count = 0
        keycloak_user_ids: List[uuid.UUID] = []

        async with pool.acquire() as conn:
            for u in users:
                user_id_raw = u.get("id")
                if not user_id_raw:
                    continue
                try:
                    uid = uuid.UUID(str(user_id_raw))
                except (ValueError, TypeError):
                    continue

                keycloak_user_ids.append(uid)
                username = u.get("username", "")
                first_name = u.get("firstName", "")
                last_name = u.get("lastName", "")
                full_name = f"{first_name} {last_name}".strip() or username
                email = u.get("email", "")
                active = bool(u.get("enabled", True))

                # Lấy thông tin tenant từ thuộc tính người dùng
                attrs = u.get("attributes", {})
                tenant_list = attrs.get("tenant", [])
                tenant = tenant_list[0] if (isinstance(tenant_list, list) and tenant_list) else ""
                if not tenant:
                    # Không tự gán địa bàn mặc định cho người dùng chưa khai báo tenant
                    logger.info(f"Bỏ qua {username}: chưa có thuộc tính tenant")
                    continue

                # Lấy danh sách vai trò người dùng trong realm
                roles: List[str] = []
                try:
                    r_res = await client.get(f"{users_url}/{user_id_raw}/role-mappings/realm", headers=headers)
                    if r_res.status_code == 200:
                        roles = [r["name"] for r in r_res.json() if "name" in r]
                except Exception as r_err:
                    logger.warning(f"Lỗi khi đọc vai trò của {username}: {r_err}")

                try:
                    await conn.execute("""
                        INSERT INTO core.users_directory (id, tenant, username, full_name, email, roles, active)
                        VALUES ($1::uuid, $2, $3, $4, $5, $6::text[], $7)
                        ON CONFLICT (tenant, username) DO UPDATE SET
                            id = EXCLUDED.id,
                            full_name = EXCLUDED.full_name,
                            email = EXCLUDED.email,
                            roles = EXCLUDED.roles,
                            active = EXCLUDED.active;
                    """, uid, tenant, username, full_name, email, roles, active)
                    synced_count += 1
                except Exception as ex:
                    logger.warning(f"Không thể cập nhật danh bạ cho {username}: {ex}")

            # Đặt active = false cho bất kỳ người dùng nào không còn tồn tại trên Keycloak
            deactivated_count = 0
            if keycloak_user_ids:
                deact_res = await conn.execute("""
                    UPDATE core.users_directory
                    SET active = false
                    WHERE NOT (id = ANY($1::uuid[])) AND active = true;
                """, keycloak_user_ids)
                try:
                    deactivated_count = int(deact_res.split(" ")[-1])
                except (ValueError, IndexError, AttributeError) as deact_err:
                    logger.debug("Không thể phân tích số lượng vô hiệu hóa: %s", deact_err)

        res_summary = {
            "total_keycloak_users": len(users),
            "synced_count": synced_count,
            "realm_updated": sorted(realm_doi),
            "deactivated_count": deactivated_count,
        }
        logger.info(f"Hoàn thành đồng bộ danh bạ: {res_summary}")
        return res_summary

    finally:
        await client.aclose()

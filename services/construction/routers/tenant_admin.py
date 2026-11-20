# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-PLAT-01: quản trị phường/tenant và gán vai Keycloak.

- Chỉ `dx:platform-admin` được tạo tenant và gán mọi vai.
- `dx:tenant-admin` chỉ thấy tenant của mình và chỉ gán vai nghiệp vụ `app:cap-phep:*`.
- Vai thật nằm ở Keycloak; bảng `core.users_directory.roles` được đồng bộ để hiển thị/tra cứu.
"""

import time
from typing import Any, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from dxos_core.audit import log_audit_event
from dxos_core.config import settings
from dxos_core.db import get_db_connection
from dxos_core.jwt import verify_jwt_token

router = APIRouter(prefix="/api/v1/admin", tags=["Quản trị địa bàn"])

PLATFORM_ROLES = ("dx:platform-admin",)
TENANT_ADMIN_ROLES = ("dx:platform-admin", "dx:tenant-admin")
TENANT_PATTERN = r"^[a-z0-9][a-z0-9-]{1,62}$"
NGHIEP_VU_PREFIX = "app:cap-phep:"
# Vai hệ thống của Keycloak không hiển thị trong danh sách gán vai.
KEYCLOAK_NOI_BO = {"default-roles-dxos", "offline_access", "uma_authorization"}

_keycloak_token: Optional[tuple[str, float]] = None


class TenantCreate(BaseModel):
    tenant: str = Field(pattern=TENANT_PATTERN)
    ten: str = Field(min_length=1, max_length=200)
    ma_dvhc: Optional[str] = Field(default=None, max_length=20)


class RoleChange(BaseModel):
    role: str = Field(min_length=3, max_length=100)
    action: str = Field(pattern="^(add|remove)$")


def _co_vai(claims, roles: tuple[str, ...]) -> bool:
    return any(r in claims.roles for r in roles)


def _yeu_cau(claims, roles: tuple[str, ...] = TENANT_ADMIN_ROLES) -> None:
    if not _co_vai(claims, roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Chỉ quản trị địa bàn được thực hiện thao tác này"},
        )


def _la_platform(claims) -> bool:
    return _co_vai(claims, PLATFORM_ROLES)


async def _admin_token() -> str:
    global _keycloak_token

    if _keycloak_token and _keycloak_token[1] > time.time() + 30:
        return _keycloak_token[0]
    url = f"{settings.keycloak_internal_url.rstrip('/')}/realms/master/protocol/openid-connect/token"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url,
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": settings.keycloak_admin,
                "password": settings.keycloak_admin_password,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail={"loi": "Không lấy được quyền quản trị Keycloak"})
    data = resp.json()
    _keycloak_token = (data["access_token"], time.time() + int(data.get("expires_in", 60)))
    return data["access_token"]


async def _keycloak(method: str, path: str, json_body: Any = None) -> httpx.Response:
    token = await _admin_token()
    base = f"{settings.keycloak_internal_url.rstrip('/')}/admin/realms/{settings.keycloak_realm}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        return await client.request(
            method,
            base + path,
            headers={"Authorization": f"Bearer {token}"},
            json=json_body,
        )


async def _keycloak_user_id(username: str) -> str:
    resp = await _keycloak("GET", f"/users?username={quote(username)}&exact=true")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail={"loi": "Không đọc được người dùng từ Keycloak"})
    rows = resp.json()
    if not rows:
        raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy người dùng trong Keycloak"})
    return rows[0]["id"]


async def _keycloak_role(role: str) -> dict:
    # Dấu ':' hợp lệ trong một path segment; giữ nguyên để Keycloak nhận đúng tên vai.
    resp = await _keycloak("GET", f"/roles/{quote(role, safe=':')}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail={"loi": f"Vai {role} không tồn tại trong Keycloak"})
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail={"loi": "Không đọc được vai từ Keycloak"})
    return resp.json()


async def _dem_ho_so(tenants: list[str]) -> dict[str, int]:
    """Đếm hồ sơ bằng kết nối dịch vụ, chỉ cho các địa bàn đã được phép nhìn thấy."""
    if not tenants:
        return {}
    async with get_db_connection() as conn:
        rows = await conn.fetch(
            "SELECT tenant, count(*) AS so_ho_so FROM app_cap_phep.ho_so "
            "WHERE tenant = ANY($1::text[]) GROUP BY tenant",
            tenants,
        )
    return {r["tenant"]: r["so_ho_so"] for r in rows}


async def _kiem_tra_nguoi_dung(claims, tenant: str, username: str) -> None:
    """Chỉ cho đổi vai người đã có trong danh mục của đúng địa bàn."""
    async with get_db_connection(claims) as conn:
        ton_tai = await conn.fetchval(
            "SELECT 1 FROM core.users_directory WHERE tenant = $1 AND username = $2",
            tenant,
            username,
        )
    if not ton_tai:
        raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy người dùng trong địa bàn"})


@router.get("/tenants")
async def danh_sach_tenant(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    _yeu_cau(claims)
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT t.tenant, t.ten, t.ma_dvhc, t.active, t.created_at,
                   (SELECT count(*) FROM core.users_directory u WHERE u.tenant = t.tenant) AS so_nguoi_dung
            FROM core.tenants t
            WHERE core.has_role('dx:platform-admin') OR t.tenant = core.jwt_tenant()
            ORDER BY t.tenant
            """
        )
        items = [dict(r) for r in rows]
    counts = await _dem_ho_so([r["tenant"] for r in items])
    for item in items:
        item["so_ho_so"] = counts.get(item["tenant"], 0)
    return {"items": items}


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def tao_tenant(body: TenantCreate, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    _yeu_cau(claims, PLATFORM_ROLES)
    async with get_db_connection(claims) as conn:
        ton_tai = await conn.fetchval("SELECT 1 FROM core.tenants WHERE tenant = $1", body.tenant)
        if ton_tai:
            raise HTTPException(status_code=409, detail={"loi": "Mã địa bàn đã tồn tại"})
        row = await conn.fetchrow(
            """
            INSERT INTO core.tenants (tenant, ten, ma_dvhc, created_by)
            VALUES ($1, $2, $3, $4)
            RETURNING tenant, ten, ma_dvhc, active, created_at
            """,
            body.tenant,
            body.ten.strip(),
            body.ma_dvhc,
            claims.sub,
        )
    await log_audit_event(
        tenant=body.tenant,
        action="tenant.created",
        actor_sub=claims.sub,
        object_type="tenant",
        object_id=body.tenant,
        detail={"ten": body.ten, "ma_dvhc": body.ma_dvhc},
    )
    return dict(row)


@router.get("/tenants/{tenant}/users")
async def danh_sach_nguoi_dung(tenant: str, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    _yeu_cau(claims)
    if not _la_platform(claims) and tenant != claims.tenant:
        raise HTTPException(status_code=403, detail={"loi": "Chỉ quản trị địa bàn của mình"})
    async with get_db_connection(claims) as conn:
        rows = await conn.fetch(
            """
            SELECT id::text AS sub, username, full_name, email, roles, active, created_at
            FROM core.users_directory
            WHERE tenant = $1
            ORDER BY username
            """,
            tenant,
        )
    return {"tenant": tenant, "items": [dict(r) for r in rows]}


@router.get("/roles")
async def danh_sach_vai(authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    _yeu_cau(claims)
    resp = await _keycloak("GET", "/roles")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail={"loi": "Không đọc được danh sách vai từ Keycloak"})
    items = []
    for r in resp.json():
        ten = r.get("name", "")
        if not ten or ten in KEYCLOAK_NOI_BO:
            continue
        if not _la_platform(claims) and not ten.startswith(NGHIEP_VU_PREFIX):
            continue
        items.append({"role": ten, "description": r.get("description") or ""})
    items.sort(key=lambda x: x["role"])
    return {"items": items}


@router.post("/tenants/{tenant}/users/{username}/roles")
async def doi_vai(tenant: str, username: str, body: RoleChange, authorization: str = Header(...)):
    claims = verify_jwt_token(authorization)
    _yeu_cau(claims)
    if not _la_platform(claims):
        if tenant != claims.tenant:
            raise HTTPException(status_code=403, detail={"loi": "Chỉ quản trị địa bàn của mình"})
        if not body.role.startswith(NGHIEP_VU_PREFIX):
            raise HTTPException(status_code=403, detail={"loi": "Quản trị địa bàn chỉ được gán vai nghiệp vụ"})

    await _kiem_tra_nguoi_dung(claims, tenant, username)
    user_id = await _keycloak_user_id(username)
    role = await _keycloak_role(body.role)
    if body.action == "add":
        resp = await _keycloak("POST", f"/users/{user_id}/role-mappings/realm", [role])
    else:
        resp = await _keycloak("DELETE", f"/users/{user_id}/role-mappings/realm", [role])
    if resp.status_code not in (200, 201, 204):
        raise HTTPException(status_code=502, detail={"loi": f"Keycloak từ chối đổi vai ({resp.status_code})"})

    # Đồng bộ bảng danh mục bằng kết nối dịch vụ: web_user chỉ có quyền đọc,
    # tránh mở đường ghi trực tiếp qua PostgREST.
    async with get_db_connection() as conn:
        if body.action == "add":
            await conn.execute(
                "UPDATE core.users_directory SET roles = array_append(roles, $3) "
                "WHERE tenant = $1 AND username = $2 AND NOT ($3 = ANY(roles))",
                tenant,
                username,
                body.role,
            )
        else:
            await conn.execute(
                "UPDATE core.users_directory SET roles = array_remove(roles, $3) "
                "WHERE tenant = $1 AND username = $2",
                tenant,
                username,
                body.role,
            )
        roles = await conn.fetchval(
            "SELECT roles FROM core.users_directory WHERE tenant = $1 AND username = $2",
            tenant,
            username,
        )
    await log_audit_event(
        tenant=tenant,
        action="user.role_changed",
        actor_sub=claims.sub,
        object_type="user",
        object_id=username,
        detail={"role": body.role, "action": body.action},
    )
    return {
        "status": "ok",
        "tenant": tenant,
        "username": username,
        "role": body.role,
        "action": body.action,
        "roles": list(roles or []),
    }


@router.get("/isolation")
async def kiem_tra_cach_ly(authorization: str = Header(...)):
    """Minh họa cách ly dữ liệu: RLS bật/forced và số địa bàn mà token hiện tại truy vấn được."""
    claims = verify_jwt_token(authorization)
    _yeu_cau(claims)
    vai_db = "svc" if ("dx:service" in claims.roles or claims.tenant == "global") else "web_user"
    async with get_db_connection(claims) as conn:
        rls = await conn.fetchrow(
            """
            SELECT
                (SELECT relrowsecurity FROM pg_class WHERE oid = 'core.tenants'::regclass) AS tenants_rls,
                (SELECT relforcerowsecurity FROM pg_class WHERE oid = 'core.tenants'::regclass) AS tenants_force,
                (SELECT relrowsecurity FROM pg_class WHERE oid = 'core.users_directory'::regclass) AS users_rls,
                (SELECT relforcerowsecurity FROM pg_class WHERE oid = 'core.users_directory'::regclass) AS users_force
            """
        )
        visible = await conn.fetch("SELECT tenant, ten FROM core.tenants ORDER BY tenant")
    visible_tenants = [r["tenant"] for r in visible]
    counts = await _dem_ho_so(visible_tenants)
    return {
        "tenant": claims.tenant,
        "vai_db": vai_db,
        "rls": dict(rls) if rls else {},
        "visible_tenants": visible_tenants,
        "so_dia_ban_thay_duoc": len(visible_tenants),
        "so_ho_so_theo_dia_ban": counts,
    }

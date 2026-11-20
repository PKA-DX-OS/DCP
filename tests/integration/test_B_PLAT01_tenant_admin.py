# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-PLAT-01: quản trị địa bàn, gán vai và cách ly dữ liệu."""

import uuid

import httpx
import pytest

from tests.integration._auth import GATEWAY_URL, get_keycloak_admin_client, get_token
from tests.integration._ho_so import run_sql

BASE = f"{GATEWAY_URL}/api/v1/admin"


def _h(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {get_token(username)}"}


def _tao_tenant_admin() -> tuple[str, str, httpx.Client, str]:
    """Tạo người dùng tạm có dx:tenant-admin ở phuong-a; trả (username, sub, client)."""
    client, token = get_keycloak_admin_client()
    admin_h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    username = f"qa.ta.{uuid.uuid4().hex[:8]}"
    payload = {
        "username": username,
        "enabled": True,
        "emailVerified": True,
        "firstName": "QA",
        "lastName": "Tenant Admin",
        "email": f"{username}@example.org",
        "attributes": {"tenant": ["phuong-a"]},
        "credentials": [{"type": "password", "value": "Demo@123456", "temporary": False}],
    }
    res = client.post("/admin/realms/dxos/users", json=payload, headers=admin_h)
    assert res.status_code == 201, res.text
    uid = client.get("/admin/realms/dxos/users", params={"username": username}, headers=admin_h).json()[0]["id"]
    role = client.get("/admin/realms/dxos/roles/dx:tenant-admin", headers=admin_h).json()
    res = client.post(
        f"/admin/realms/dxos/users/{uid}/role-mappings/realm",
        json=[{"id": role["id"], "name": role["name"]}],
        headers=admin_h,
    )
    assert res.status_code in (204, 201), res.text
    run_sql(
        "INSERT INTO core.users_directory (id, tenant, username, full_name, email, roles, active) "
        f"VALUES ('{uid}', 'phuong-a', '{username}', 'QA Tenant Admin', '{username}@example.org', "
        "ARRAY['dx:tenant-admin'], true) "
        "ON CONFLICT (tenant, username) DO UPDATE SET roles = EXCLUDED.roles;"
    )
    return username, uid, client, token


def _xoa_tenant_admin(username: str, uid: str, client: httpx.Client, token: str) -> None:
    client.delete(f"/admin/realms/dxos/users/{uid}", headers={"Authorization": f"Bearer {token}"})
    run_sql(f"DELETE FROM core.users_directory WHERE username = '{username}';")


def test_BPLAT01_platform_admin_tao_va_xem_dia_ban():
    h = _h("admin")

    r = httpx.get(f"{BASE}/tenants", headers=h, timeout=20.0)
    assert r.status_code == 200, r.text
    ma = {x["tenant"] for x in r.json()["items"]}
    assert {"global", "phuong-a", "phuong-b"} <= ma
    phuong_a = next(x for x in r.json()["items"] if x["tenant"] == "phuong-a")
    assert phuong_a["so_nguoi_dung"] >= 1
    assert phuong_a["so_ho_so"] >= 1

    r = httpx.get(f"{BASE}/roles", headers=h, timeout=20.0)
    assert r.status_code == 200, r.text
    vai = {x["role"] for x in r.json()["items"]}
    assert "app:cap-phep:tham-dinh" in vai
    assert "dx:platform-admin" in vai
    assert "default-roles-dxos" not in vai

    iso = httpx.get(f"{BASE}/isolation", headers=h, timeout=20.0)
    assert iso.status_code == 200, iso.text
    body = iso.json()
    assert body["rls"]["tenants_rls"] is True
    assert body["rls"]["tenants_force"] is True
    assert {"phuong-a", "phuong-b"} <= set(body["visible_tenants"])

    ma_moi = f"qa-plat-{uuid.uuid4().hex[:6]}"
    try:
        r = httpx.post(
            f"{BASE}/tenants",
            headers=h,
            json={"tenant": ma_moi, "ten": "QA Platform", "ma_dvhc": "799999"},
            timeout=20.0,
        )
        assert r.status_code == 201, r.text
        assert r.json()["tenant"] == ma_moi

        lai = httpx.get(f"{BASE}/tenants", headers=h, timeout=20.0)
        assert ma_moi in {x["tenant"] for x in lai.json()["items"]}

        trung = httpx.post(
            f"{BASE}/tenants",
            headers=h,
            json={"tenant": ma_moi, "ten": "QA Platform"},
            timeout=20.0,
        )
        assert trung.status_code == 409, trung.text
    finally:
        run_sql(f"DELETE FROM core.tenants WHERE tenant = '{ma_moi}';")


def test_BPLAT01_tenant_admin_chi_quan_tri_dia_ban_cua_minh():
    username, uid, client, admin_token = _tao_tenant_admin()
    try:
        h = _h(username)

        ds = httpx.get(f"{BASE}/tenants", headers=h, timeout=20.0)
        assert ds.status_code == 200, ds.text
        assert [x["tenant"] for x in ds.json()["items"]] == ["phuong-a"]

        vai = httpx.get(f"{BASE}/roles", headers=h, timeout=20.0)
        assert vai.status_code == 200, vai.text
        ten_vai = {x["role"] for x in vai.json()["items"]}
        assert ten_vai and all(v.startswith("app:cap-phep:") for v in ten_vai)

        iso = httpx.get(f"{BASE}/isolation", headers=h, timeout=20.0)
        assert iso.status_code == 200, iso.text
        assert iso.json()["visible_tenants"] == ["phuong-a"]
        assert iso.json()["vai_db"] == "web_user"

        cheo = httpx.get(f"{BASE}/tenants/phuong-b/users", headers=h, timeout=20.0)
        assert cheo.status_code == 403, cheo.text

        tao = httpx.post(
            f"{BASE}/tenants",
            headers=h,
            json={"tenant": f"qa-cam-{uuid.uuid4().hex[:6]}", "ten": "QA Cấm"},
            timeout=20.0,
        )
        assert tao.status_code == 403, tao.text

        vai_he_thong = httpx.post(
            f"{BASE}/tenants/phuong-a/users/{username}/roles",
            headers=h,
            json={"role": "dx:auditor", "action": "add"},
            timeout=20.0,
        )
        assert vai_he_thong.status_code == 403, vai_he_thong.text

        gan = httpx.post(
            f"{BASE}/tenants/phuong-a/users/{username}/roles",
            headers=h,
            json={"role": "app:cap-phep:tham-dinh", "action": "add"},
            timeout=20.0,
        )
        assert gan.status_code == 200, gan.text
        assert "app:cap-phep:tham-dinh" in gan.json()["roles"]

        thu_hoi = httpx.post(
            f"{BASE}/tenants/phuong-a/users/{username}/roles",
            headers=h,
            json={"role": "app:cap-phep:tham-dinh", "action": "remove"},
            timeout=20.0,
        )
        assert thu_hoi.status_code == 200, thu_hoi.text
        assert "app:cap-phep:tham-dinh" not in thu_hoi.json()["roles"]
    finally:
        _xoa_tenant_admin(username, uid, client, admin_token)
        client.close()


@pytest.mark.parametrize("username", ["cdt.minh", "ld.hoa", "kt.an"])
def test_BPLAT01_vai_khac_khong_vao_duoc_quan_tri(username: str):
    r = httpx.get(f"{BASE}/tenants", headers=_h(username), timeout=20.0)
    assert r.status_code == 403, r.text

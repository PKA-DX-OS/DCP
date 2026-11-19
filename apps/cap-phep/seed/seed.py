#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kịch bản nạp dữ liệu mẫu (make seed) cho ứng dụng cấp phép xây dựng C3:
1. Tạo 11 tài khoản demo theo vai và 1 tài khoản quản trị trong Keycloak SSO, mật khẩu sinh ngẫu nhiên
   ghi vào secrets/demo-accounts.txt (F-41).
2. Nạp 8 hồ sơ mẫu (6 tại phường A, 2 tại phường B) với chu_dau_tu_sub là UUID Keycloak thật (F-29).
3. Khởi chạy tiến trình BPMN Flowable thật và đẩy từng hồ sơ đến đúng trạng thái kịch bản (F-42).
4. Nạp 1 công trình đang thi công CT-01 (phường A). Không tạo giấy phép hoặc phiếu kiểm tra.
Tri thức RAG do scripts/app_manager.py nạp khi cài ứng dụng, seed không nạp.

Chạy lặp an toàn: nếu dữ liệu mẫu của tenant đã đủ thì bỏ qua, không tạo bản ghi trùng.
Chỉ xóa dữ liệu mẫu (theo mã hồ sơ mẫu và CT-01), không đụng dữ liệu khác.

Dùng:
    python apps/cap-phep/seed/seed.py                       # cả hai phường
    python apps/cap-phep/seed/seed.py --tenant phuong-a     # một phường
    python apps/cap-phep/seed/seed.py --tenant phuong-a --reset   # xóa dữ liệu mẫu rồi nạp lại
    python apps/cap-phep/seed/seed.py --chi-xoa             # chỉ xóa dữ liệu mẫu
"""

import argparse
import asyncio
import secrets
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any

# Ensure UTF-8 output on all platforms
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception) as _e:
        _ = _e

import httpx
from dxos_core.config import settings
from dxos_core.db import get_db_pool

ACCOUNTS = [
    {"username": "cdt.minh", "name": "Trần Văn Minh (mẫu)", "role": "app:cap-phep:chu-dau-tu", "tenant": "phuong-a"},
    {"username": "cdt.lan", "name": "Lê Thị Lan (mẫu)", "role": "app:cap-phep:chu-dau-tu", "tenant": "phuong-a"},
    {"username": "mc.thu", "name": "Nguyễn Thị Thu (mẫu)", "role": "app:cap-phep:mot-cua", "tenant": "phuong-a"},
    {"username": "td.binh", "name": "Hoàng Văn Bình (mẫu)", "role": "app:cap-phep:tham-dinh", "tenant": "phuong-a"},
    {"username": "td.cuong", "name": "Vũ Quốc Cường (mẫu)", "role": "app:cap-phep:tham-dinh", "tenant": "phuong-a"},
    {"username": "ld.hoa", "name": "Phạm Thanh Hoa (mẫu)", "role": "app:cap-phep:lanh-dao", "tenant": "phuong-a"},
    {"username": "tt.khanh", "name": "Đặng Quốc Khánh (mẫu)", "role": "app:cap-phep:trat-tu-xd", "tenant": "phuong-a"},
    {"username": "mc.phuongb", "name": "Bùi Minh Phương (mẫu)", "role": "app:cap-phep:mot-cua", "tenant": "phuong-b"},
    {"username": "ld.phuongb", "name": "Nguyễn Văn Lãnh B (mẫu)", "role": "app:cap-phep:lanh-dao", "tenant": "phuong-b"},
    {"username": "td.phuongb", "name": "Trần Thị Thẩm B (mẫu)", "role": "app:cap-phep:tham-dinh", "tenant": "phuong-b"},
    {"username": "kt.an", "name": "Đỗ Văn An (mẫu)", "role": "dx:auditor", "tenant": "phuong-a"},
    {"username": "admin", "name": "Quản trị Toàn cục (mẫu)", "role": "dx:platform-admin", "tenant": "global"},
]

TENANTS = ("phuong-a", "phuong-b")
# Phạm vi dữ liệu mẫu: chỉ những mã này bị xóa / nạp lại.
SEED_HO_SO = {
    "phuong-a": ["CP-2026-000101", "CP-2026-000102", "CP-2026-000103",
                 "CP-2026-000104", "CP-2026-000105", "CP-2026-000106"],
    "phuong-b": ["CP-2026-000201", "CP-2026-000202"],
}
SEED_CONG_TRINH = {"phuong-a": ["CT-01"], "phuong-b": []}


def load_or_generate_demo_passwords() -> Dict[str, str]:
    """Sinh ngẫu nhiên mật khẩu cho từng tài khoản và ghi vào secrets/demo-accounts.txt (F-41)."""
    accounts_file = Path("secrets/demo-accounts.txt")
    passwords = {}
    if accounts_file.exists():
        for line in accounts_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and ":" in line and not line.startswith("#"):
                parts = line.split(":")
                if len(parts) >= 2:
                    passwords[parts[0].strip()] = parts[1].strip()

    account_lines = [
        "# DX-OS Open-Core Demo Accounts (F-41) - Mật khẩu sinh ngẫu nhiên",
        "# Định dạng: username:password:role:tenant",
    ]
    for acc in ACCOUNTS:
        u = acc["username"]
        if u not in passwords:
            passwords[u] = "Demo@" + secrets.token_urlsafe(8) + "!"
        account_lines.append(f"{u}:{passwords[u]}:{acc['role']}:{acc['tenant']}")

    accounts_file.parent.mkdir(parents=True, exist_ok=True)
    accounts_file.write_text("\n".join(account_lines) + "\n", encoding="utf-8")
    return passwords


async def seed_keycloak_users(passwords: Dict[str, str], accounts: List[Dict[str, str]]) -> Dict[str, str]:
    """Tạo người dùng trong Keycloak Realm dxos và gán vai trò, tenant (F-41). Trả về map username -> sub."""
    print(f"--> 1. Nạp và đồng bộ {len(accounts)} tài khoản mẫu vào Keycloak SSO (F-41)...")
    token_url = f"{settings.keycloak_internal_url}/realms/master/protocol/openid-connect/token"
    roles_url = f"{settings.keycloak_internal_url}/admin/realms/{settings.keycloak_realm}/roles"
    users_url = f"{settings.keycloak_internal_url}/admin/realms/{settings.keycloak_realm}/users"
    up_url = f"{settings.keycloak_internal_url}/admin/realms/{settings.keycloak_realm}/users/profile"

    user_sub_map = {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                token_url,
                data={
                    "client_id": "admin-cli",
                    "username": settings.keycloak_admin,
                    "password": settings.keycloak_admin_password,
                    "grant_type": "password",
                },
            )
            if token_resp.status_code != 200:
                print(f"[ERROR] Không lấy được Keycloak admin token ({token_resp.status_code}: {token_resp.text})", file=sys.stderr)
                sys.exit(1)

            admin_token = token_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

            # Đảm bảo User Profile trong Keycloak chấp nhận thuộc tính tenant
            try:
                up_res = await client.get(up_url, headers=headers)
                if up_res.status_code == 200:
                    profile = up_res.json()
                    attr_names = [a.get("name") for a in profile.get("attributes", [])]
                    if "tenant" not in attr_names:
                        profile.setdefault("attributes", []).append({
                            "name": "tenant",
                            "displayName": "Tenant ID",
                            "permissions": {"view": ["admin", "user"], "edit": ["admin"]},
                            "multivalued": False,
                        })
                    profile["unmanagedAttributePolicy"] = "ENABLED"
                    await client.put(up_url, headers=headers, json=profile)
            except Exception as e:
                print(f"  [WARN] Không thể cấu hình User Profile: {e}")

            # Đảm bảo các vai trò realm cần thiết đã tồn tại
            roles_resp = await client.get(roles_url, headers=headers)
            existing_roles = {r["name"]: r for r in roles_resp.json()} if roles_resp.status_code == 200 else {}

            for acc in accounts:
                role_name = acc["role"]
                if role_name not in existing_roles:
                    create_role_resp = await client.post(roles_url, headers=headers, json={"name": role_name, "description": f"Role {role_name}"})
                    if create_role_resp.status_code in (201, 204):
                        get_r = await client.get(f"{roles_url}/{role_name}", headers=headers)
                        if get_r.status_code == 200:
                            existing_roles[role_name] = get_r.json()

            # Tạo người dùng và gán vai trò, tenant, mật khẩu
            for acc in accounts:
                u_resp = await client.get(f"{users_url}?username={acc['username']}", headers=headers)
                users = u_resp.json() if u_resp.status_code == 200 else []

                clean_name = acc["name"].replace("(mẫu)", "").replace("(", "").replace(")", "").strip()
                parts = clean_name.split()
                first_n = parts[0] if parts else acc["username"]
                last_n = " ".join(parts[1:]) if len(parts) > 1 else acc["username"]
                user_payload = {
                    "username": acc["username"],
                    "enabled": True,
                    "emailVerified": True,
                    "requiredActions": [],
                    "firstName": first_n,
                    "lastName": last_n,
                    "email": f"{acc['username']}@phuonga.example.org",
                    "attributes": {"tenant": [acc["tenant"]]},
                }

                user_id = None
                if users:
                    user_id = users[0]["id"]
                    await client.put(f"{users_url}/{user_id}", headers=headers, json=user_payload)
                else:
                    user_payload["credentials"] = [{"type": "password", "value": passwords[acc["username"]], "temporary": False}]
                    create_resp = await client.post(users_url, headers=headers, json=user_payload)
                    if create_resp.status_code == 201:
                        u_resp2 = await client.get(f"{users_url}?username={acc['username']}", headers=headers)
                        if u_resp2.status_code == 200 and u_resp2.json():
                            user_id = u_resp2.json()[0]["id"]

                if user_id:
                    user_sub_map[acc["username"]] = user_id
                    # Cập nhật mật khẩu chuẩn theo secrets/demo-accounts.txt
                    await client.put(
                        f"{users_url}/{user_id}/reset-password",
                        headers=headers,
                        json={"type": "password", "value": passwords[acc["username"]], "temporary": False},
                    )
                    # Gán vai trò tương ứng cho user
                    role_name = acc["role"]
                    if role_name in existing_roles:
                        role_obj = existing_roles[role_name]
                        await client.post(
                            f"{users_url}/{user_id}/role-mappings/realm",
                            headers=headers,
                            json=[{"id": role_obj["id"], "name": role_obj["name"]}],
                        )

            # Đồng bộ sang bảng core.users_directory (N-06)
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                for acc in accounts:
                    u_id = user_sub_map.get(acc["username"])
                    if u_id:
                        clean_name = acc["name"].replace("(mẫu)", "").replace("(", "").replace(")", "").strip()
                        await conn.execute("""
                            INSERT INTO core.users_directory (id, tenant, username, full_name, email, roles, active)
                            VALUES ($1::uuid, $2, $3, $4, $5, ARRAY[$6]::text[], true)
                            ON CONFLICT (tenant, username) DO UPDATE SET
                                id = EXCLUDED.id,
                                full_name = EXCLUDED.full_name,
                                email = EXCLUDED.email,
                                roles = EXCLUDED.roles,
                                active = EXCLUDED.active;
                        """, uuid.UUID(str(u_id)), acc["tenant"], acc["username"], clean_name, f"{acc['username']}@phuonga.example.org", acc["role"])

            print(f"  - Đã nạp và đồng bộ {len(user_sub_map)} tài khoản vào Keycloak và core.users_directory.")
            return user_sub_map
    except Exception as e:
        print(f"[ERROR] Không kết nối được Keycloak admin API ({e})! Quá trình nạp dữ liệu người dùng thất bại.", file=sys.stderr)
        sys.exit(1)


async def seed_flowable_processes(sample_apps: List[Dict[str, Any]], user_sub_map: Dict[str, str], tenants: List[str]) -> Dict[str, str]:
    """
    F-42: Khởi chạy tiến trình BPMN Flowable thật và đẩy từng hồ sơ đến đúng trạng thái kịch bản.
    Trả về dict {ma_ho_so: process_instance_id}
    """
    print(f"--> 2. Khởi tạo và đồng bộ tiến trình BPMN Flowable thật cho {len(sample_apps)} hồ sơ mẫu (F-42)...")
    flowable_auth = (settings.flowable_user, settings.flowable_password)
    proc_map = {}

    td_binh_sub = user_sub_map.get("td.binh", "td.binh")
    td_cuong_sub = user_sub_map.get("td.cuong", "td.cuong")

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Đảm bảo BPMN đã được deploy trên Flowable cho các tenant
        for t in tenants:
            dep_res = await client.get(f"{settings.flowable_url}/service/repository/process-definitions?key=cap-phep&tenantId={t}", auth=flowable_auth)
            if dep_res.status_code != 200 or not dep_res.json().get("data"):
                bpmn_file = Path("apps/cap-phep/bpmn/cap-phep.bpmn20.xml")
                if bpmn_file.exists():
                    files = {"file": (bpmn_file.name, bpmn_file.read_bytes(), "text/xml")}
                    dep_post = await client.post(f"{settings.flowable_url}/service/repository/deployments", auth=flowable_auth, files=files, data={"tenantId": t})
                    if dep_post.status_code in (200, 201):
                        print(f"  - Đã deploy quy trình BPMN cap-phep vào Flowable cho tenant {t}.")
                    else:
                        print(f"  [ERROR] Lỗi deploy BPMN cap-phep cho tenant {t}: {dep_post.status_code} - {dep_post.text}")

        for app in sample_apps:
            ma_ho_so = app["ma_ho_so"]
            tenant = app["tenant"]
            chu_dau_tu_sub = app["chu_dau_tu_sub"]
            dien_tich = app["dien_tich_san_m2"]
            khu_ql = app["khu_quan_ly_kien_truc"]
            trang_thai = app["trang_thai"]

            # Khởi tạo process instance
            start_payload = {
                "processDefinitionKey": "cap-phep",
                "businessKey": ma_ho_so,
                "tenantId": tenant,
                "variables": [
                    {"name": "ma_ho_so", "value": ma_ho_so},
                    {"name": "tenant", "value": tenant},
                    {"name": "chu_dau_tu_sub", "value": chu_dau_tu_sub},
                    {"name": "dien_tich_san_m2", "value": float(dien_tich)},
                    {"name": "khu_quan_ly_kien_truc", "value": bool(khu_ql)},
                    {"name": "nguoiThamDinh", "value": td_binh_sub},
                ],
            }
            start_res = await client.post(f"{settings.flowable_url}/service/runtime/process-instances", auth=flowable_auth, json=start_payload)
            if start_res.status_code not in (200, 201):
                print(f"  [WARN] Không thể khởi tạo Flowable instance cho {ma_ho_so}: {start_res.text}")
                continue

            proc_id = start_res.json()["id"]
            proc_map[ma_ho_so] = proc_id

            # Đẩy instance đến trạng thái tương ứng trong kịch bản
            if trang_thai in ("TIEP_NHAN", "DUOC_PHAN_CONG", "DANG_THAM_DINH", "CHO_DUYET", "DA_CAP"):
                tasks_res = await client.get(f"{settings.flowable_url}/service/runtime/tasks?processInstanceId={proc_id}", auth=flowable_auth)
                tasks = tasks_res.json().get("data", [])
                if tasks and tasks[0]["taskDefinitionKey"] == "taskKiemTraHopLe":
                    await client.post(f"{settings.flowable_url}/service/runtime/tasks/{tasks[0]['id']}", auth=flowable_auth, json={"action": "complete"})

            if trang_thai in ("DUOC_PHAN_CONG", "DANG_THAM_DINH", "CHO_DUYET", "DA_CAP"):
                tasks_res = await client.get(f"{settings.flowable_url}/service/runtime/tasks?processInstanceId={proc_id}", auth=flowable_auth)
                tasks = tasks_res.json().get("data", [])
                if tasks and tasks[0]["taskDefinitionKey"] == "taskPhanCong":
                    assignee_sub = td_cuong_sub if ma_ho_so == "CP-2026-000104" else td_binh_sub
                    await client.post(
                        f"{settings.flowable_url}/service/runtime/tasks/{tasks[0]['id']}",
                        auth=flowable_auth,
                        json={
                            "action": "complete",
                            "variables": [
                                {"name": "nguoiThamDinh", "value": assignee_sub},
                                {"name": "dien_tich_san_m2", "value": float(dien_tich)},
                                {"name": "khu_quan_ly_kien_truc", "value": bool(khu_ql)},
                            ],
                        },
                    )

            if trang_thai in ("CHO_DUYET", "DA_CAP"):
                tasks_res = await client.get(f"{settings.flowable_url}/service/runtime/tasks?processInstanceId={proc_id}", auth=flowable_auth)
                tasks = tasks_res.json().get("data", [])
                if tasks and tasks[0]["taskDefinitionKey"] in ("taskThamDinh", "taskThamDinhNhanh"):
                    await client.post(
                        f"{settings.flowable_url}/service/runtime/tasks/{tasks[0]['id']}",
                        auth=flowable_auth,
                        json={"action": "complete", "variables": [{"name": "ket_qua_tham_dinh", "value": "DAT"}]},
                    )

            if trang_thai == "DA_CAP":
                tasks_res = await client.get(f"{settings.flowable_url}/service/runtime/tasks?processInstanceId={proc_id}", auth=flowable_auth)
                tasks = tasks_res.json().get("data", [])
                if tasks and tasks[0]["taskDefinitionKey"] == "taskDuyetCapPhep":
                    await client.post(
                        f"{settings.flowable_url}/service/runtime/tasks/{tasks[0]['id']}",
                        auth=flowable_auth,
                        json={"action": "complete", "variables": [{"name": "ket_qua_duyet", "value": "PHE_DUYET"}]},
                    )

    print(f"  - Đã khởi chạy và đồng bộ thành công {len(proc_map)} quy trình BPMN Flowable.")
    return proc_map


async def dem_du_lieu_mau(tenants: List[str]) -> Dict[str, int]:
    """Đếm số hồ sơ mẫu đã có theo từng tenant."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        dem = {}
        for t in tenants:
            dem[t] = await conn.fetchval(
                "SELECT count(*) FROM app_cap_phep.ho_so WHERE tenant = $1 AND ma_ho_so = ANY($2::text[])",
                t, SEED_HO_SO[t],
            )
        return dem


async def xoa_du_lieu_mau(tenants: List[str]) -> None:
    """Xóa đúng dữ liệu mẫu của các tenant đã chọn: hồ sơ mẫu (kèm tệp, lịch sử, phân công,
    giấy phép phát sinh khi demo), công trình mẫu (kèm phiếu kiểm tra)
    và process instance Flowable của hồ sơ mẫu. Không đụng dữ liệu khác."""
    print(f"--> 0. Xóa dữ liệu mẫu của {', '.join(tenants)}...")
    pool = await get_db_pool()
    if not pool:
        print("[ERROR] Không thể kết nối cơ sở dữ liệu PostgreSQL!", file=sys.stderr)
        sys.exit(1)
    flowable_auth = (settings.flowable_user, settings.flowable_password)
    async with pool.acquire() as conn:
        proc_ids = []
        for t in tenants:
            rows = await conn.fetch(
                "SELECT process_instance_id FROM app_cap_phep.ho_so "
                "WHERE tenant = $1 AND ma_ho_so = ANY($2::text[]) AND process_instance_id IS NOT NULL",
                t, SEED_HO_SO[t],
            )
            proc_ids += [r["process_instance_id"] for r in rows]

        async with conn.transaction():
            for t in tenants:
                ho_so_ids = [r["id"] for r in await conn.fetch(
                    "SELECT id FROM app_cap_phep.ho_so WHERE tenant = $1 AND ma_ho_so = ANY($2::text[])",
                    t, SEED_HO_SO[t],
                )]
                giay_phep_ids = [r["id"] for r in await conn.fetch(
                    "SELECT id FROM app_cap_phep.giay_phep WHERE ho_so_id = ANY($1::uuid[])", ho_so_ids,
                )]
                cong_trinh_ids = [r["id"] for r in await conn.fetch(
                    "SELECT id FROM app_cap_phep.cong_trinh WHERE tenant = $1 "
                    "AND (ma_cong_trinh = ANY($2::text[]) OR giay_phep_id = ANY($3::uuid[]))",
                    t, SEED_CONG_TRINH[t], giay_phep_ids,
                )]
                await conn.execute("DELETE FROM app_cap_phep.phieu_kiem_tra WHERE cong_trinh_id = ANY($1::uuid[])", cong_trinh_ids)
                await conn.execute("DELETE FROM app_cap_phep.cong_trinh WHERE id = ANY($1::uuid[])", cong_trinh_ids)
                await conn.execute("DELETE FROM app_cap_phep.giay_phep WHERE id = ANY($1::uuid[])", giay_phep_ids)
                await conn.execute("DELETE FROM app_cap_phep.ho_so_lich_su WHERE ho_so_id = ANY($1::uuid[])", ho_so_ids)
                await conn.execute(
                    "DELETE FROM core.assignments WHERE object_type = 'ho_so' AND object_id = ANY($1::uuid[])", ho_so_ids,
                )
                await conn.execute("DELETE FROM app_cap_phep.ho_so WHERE id = ANY($1::uuid[])", ho_so_ids)
                print(f"  - {t}: xóa {len(ho_so_ids)} hồ sơ mẫu, {len(cong_trinh_ids)} công trình mẫu, {len(giay_phep_ids)} giấy phép phát sinh.")

    if proc_ids:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for pid in proc_ids:
                r = await client.delete(
                    f"{settings.flowable_url}/service/runtime/process-instances/{pid}",
                    params={"deleteReason": "seed-reset"}, auth=flowable_auth,
                )
                if r.status_code not in (204, 404):
                    print(f"  [WARN] Không xóa được process instance {pid}: {r.status_code}")
        print(f"  - Đã dọn {len(proc_ids)} process instance Flowable của hồ sơ mẫu.")


async def seed_database(user_sub_map: Dict[str, str], proc_map: Dict[str, str], tenants: List[str]):
    """Nạp dữ liệu nghiệp vụ vào PostgreSQL sử dụng UUID sub từ Keycloak (F-29) và Flowable process_instance_id (F-42)."""
    print("--> 3. Nạp dữ liệu hồ sơ và công trình mẫu vào cơ sở dữ liệu...")
    pool = await get_db_pool()
    if not pool:
        print("[ERROR] Không thể kết nối cơ sở dữ liệu PostgreSQL! Quá trình nạp dữ liệu thất bại.", file=sys.stderr)
        sys.exit(1)
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn, conn.transaction():
        # 1. Nạp 8 hồ sơ mẫu (F-29: chu_dau_tu_sub là UUID Keycloak)
        sample_apps = [
            ("CP-2026-000101", "phuong-a", user_sub_map.get("cdt.minh", "cdt.minh"), "Trần Văn Minh (mẫu)", "001099001234", "0901234567", "Số 123 Đường Hoa Phượng (mẫu)", "Thửa 12, Tờ 4", 3, 120.0, "DA_NOP", "tiep_nhan", 7),
            ("CP-2026-000102", "phuong-a", user_sub_map.get("cdt.lan", "cdt.lan"), "Lê Thị Lan (mẫu)", "001099005678", "0912345678", "Số 45 Đường Bằng Lăng (mẫu)", "Thửa 88, Tờ 2", 2, 85.0, "TIEP_NHAN", "phan_cong", 6),
            ("CP-2026-000103", "phuong-a", user_sub_map.get("cdt.minh", "cdt.minh"), "Trần Văn Minh (mẫu)", "001099001234", "0901234567", "Số 78 Đường Hoàng Lan (mẫu)", "Thửa 10, Tờ 1", 4, 160.0, "DUOC_PHAN_CONG", "tham_dinh", 5),
            ("CP-2026-000104", "phuong-a", user_sub_map.get("cdt.lan", "cdt.lan"), "Lê Thị Lan (mẫu)", "001099005678", "0912345678", "Số 99 Đường Cẩm Tú (mẫu)", "Thửa 34, Tờ 5", 3, 110.0, "DANG_THAM_DINH", "tham_dinh", 4),
            ("CP-2026-000105", "phuong-a", user_sub_map.get("cdt.minh", "cdt.minh"), "Trần Văn Minh (mẫu)", "001099001234", "0901234567", "Số 12 Đường Hướng Dương (mẫu)", "Thửa 5, Tờ 3", 2, 90.0, "CHO_DUYET", "phe_duyet", 2),
            ("CP-2026-000106", "phuong-a", user_sub_map.get("cdt.lan", "cdt.lan"), "Lê Thị Lan (mẫu)", "001099005678", "0912345678", "Số 88 Đường Dạ Lan (mẫu)", "Thửa 9, Tờ 7", 5, 250.0, "DA_CAP", "hoan_thanh", 0),
            # 2 hồ sơ tại Phường B để kiểm tra cách ly đa thuê ước
            ("CP-2026-000201", "phuong-b", user_sub_map.get("mc.phuongb", "cdt.phuongb1"), "Nguyễn Văn Nam (mẫu)", "001099009999", "0988776655", "Số 15 Phố Phường B (mẫu)", "Thửa 1, Tờ 1", 3, 130.0, "DA_NOP", "tiep_nhan", 7),
            ("CP-2026-000202", "phuong-b", user_sub_map.get("mc.phuongb", "cdt.phuongb2"), "Phạm Thị Mai (mẫu)", "001099008888", "0977665544", "Số 20 Phố Phường B (mẫu)", "Thửa 2, Tờ 1", 2, 95.0, "DANG_THAM_DINH", "tham_dinh", 4),
        ]

        sample_apps = [item for item in sample_apps if item[1] in tenants]
        app_ids = {}
        for item in sample_apps:
            app_id = uuid.uuid4()
            app_ids[item[0]] = app_id
            han_tong = now + timedelta(days=item[12])
            proc_id = proc_map.get(item[0])
            await conn.execute(
                """
                INSERT INTO app_cap_phep.ho_so (
                    id, ma_ho_so, tenant, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
                    dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2,
                    trang_thai, buoc, han_tong_at, process_instance_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                """,
                app_id, item[0], item[1], item[2], item[3], item[4], item[5],
                item[6], item[7], item[8], item[9], item[10], item[11], han_tong, proc_id,
            )

        if "phuong-a" not in tenants:
            print(f"  - Đã nạp {len(sample_apps)} hồ sơ mẫu vào PostgreSQL.")
            return

        # Phân công hồ sơ demo CP-2026-000103 cho td.binh (F-29: user_sub là UUID)
        td_binh_sub = user_sub_map.get("td.binh", "td.binh")
        await conn.execute(
            """
            INSERT INTO core.assignments (tenant, object_type, object_id, user_sub, role)
            VALUES ('phuong-a', 'ho_so', $1, $2, 'app:cap-phep:tham-dinh')
            """,
            app_ids["CP-2026-000103"],
            td_binh_sub,
        )

        # 2. Nạp công trình thi công mẫu
        ct_id1 = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO app_cap_phep.cong_trinh (id, tenant, ma_cong_trinh, entity_id, dia_chi, trang_thai_thi_cong)
            VALUES ($1, 'phuong-a', 'CT-01', 'urn:ngsi-ld:Site:CT-01', 'Số 123 Đường Hoa Phượng (mẫu)', 'DANG_THI_CONG')
            """,
            ct_id1,
        )

    print(f"  - Đã nạp {len(sample_apps)} hồ sơ mẫu, công trình CT-01 vào PostgreSQL.")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Nạp dữ liệu mẫu cấp phép cho hai phường.")
    ap.add_argument("--tenant", choices=[*TENANTS, "all"], default="all",
                    help="Phường cần nạp (mặc định: cả hai).")
    nhom = ap.add_mutually_exclusive_group()
    nhom.add_argument("--reset", action="store_true",
                      help="Xóa dữ liệu mẫu của phường đã chọn rồi nạp lại.")
    nhom.add_argument("--chi-xoa", action="store_true",
                      help="Chỉ xóa dữ liệu mẫu của phường đã chọn, không nạp lại.")
    return ap.parse_args(argv)


async def main(argv=None):
    args = parse_args(argv)
    tenants = list(TENANTS) if args.tenant == "all" else [args.tenant]
    print("=================================================================")
    print(" [DX-OS] BẮT ĐẦU NẠP DỮ LIỆU MẪU & TÀI KHOẢN DEMO (make seed) ")
    print(f" Phường: {', '.join(tenants)}")
    print("=================================================================")

    if args.chi_xoa:
        await xoa_du_lieu_mau(tenants)
        print(" [DX-OS] ĐÃ XÓA DỮ LIỆU MẪU.")
        return

    # Tenant nào chưa đủ dữ liệu mẫu (hoặc --reset) thì dọn phạm vi mẫu rồi nạp lại; đủ rồi thì bỏ qua.
    dem = await dem_du_lieu_mau(tenants)
    can_nap = tenants if args.reset else [t for t in tenants if dem[t] != len(SEED_HO_SO[t])]
    if can_nap:
        await xoa_du_lieu_mau(can_nap)

    # 1. Sinh ngẫu nhiên mật khẩu vào secrets/demo-accounts.txt (F-41)
    passwords = load_or_generate_demo_passwords()

    # 2. Tạo tài khoản trong Keycloak SSO (F-41), chạy lại chỉ cập nhật
    accounts = [a for a in ACCOUNTS if a["tenant"] in tenants or a["tenant"] == "global"]
    user_sub_map = await seed_keycloak_users(passwords, accounts)

    if not can_nap:
        print(f"--> Dữ liệu mẫu của {', '.join(tenants)} đã đủ, bỏ qua (dùng --reset để nạp lại).")
        return

    # 3. Chuẩn bị danh sách hồ sơ mẫu
    sample_data = [
        {"ma_ho_so": "CP-2026-000101", "tenant": "phuong-a", "chu_dau_tu_sub": user_sub_map.get("cdt.minh", "cdt.minh"), "dien_tich_san_m2": 120.0, "khu_quan_ly_kien_truc": True, "trang_thai": "DA_NOP"},
        {"ma_ho_so": "CP-2026-000102", "tenant": "phuong-a", "chu_dau_tu_sub": user_sub_map.get("cdt.lan", "cdt.lan"), "dien_tich_san_m2": 85.0, "khu_quan_ly_kien_truc": True, "trang_thai": "TIEP_NHAN"},
        {"ma_ho_so": "CP-2026-000103", "tenant": "phuong-a", "chu_dau_tu_sub": user_sub_map.get("cdt.minh", "cdt.minh"), "dien_tich_san_m2": 160.0, "khu_quan_ly_kien_truc": True, "trang_thai": "DUOC_PHAN_CONG"},
        {"ma_ho_so": "CP-2026-000104", "tenant": "phuong-a", "chu_dau_tu_sub": user_sub_map.get("cdt.lan", "cdt.lan"), "dien_tich_san_m2": 110.0, "khu_quan_ly_kien_truc": True, "trang_thai": "DANG_THAM_DINH"},
        {"ma_ho_so": "CP-2026-000105", "tenant": "phuong-a", "chu_dau_tu_sub": user_sub_map.get("cdt.minh", "cdt.minh"), "dien_tich_san_m2": 90.0, "khu_quan_ly_kien_truc": True, "trang_thai": "CHO_DUYET"},
        {"ma_ho_so": "CP-2026-000106", "tenant": "phuong-a", "chu_dau_tu_sub": user_sub_map.get("cdt.lan", "cdt.lan"), "dien_tich_san_m2": 250.0, "khu_quan_ly_kien_truc": True, "trang_thai": "DA_CAP"},
        {"ma_ho_so": "CP-2026-000201", "tenant": "phuong-b", "chu_dau_tu_sub": user_sub_map.get("mc.phuongb", "cdt.phuongb1"), "dien_tich_san_m2": 130.0, "khu_quan_ly_kien_truc": True, "trang_thai": "DA_NOP"},
        {"ma_ho_so": "CP-2026-000202", "tenant": "phuong-b", "chu_dau_tu_sub": user_sub_map.get("mc.phuongb", "cdt.phuongb2"), "dien_tich_san_m2": 95.0, "khu_quan_ly_kien_truc": True, "trang_thai": "DANG_THAM_DINH"},
    ]

    sample_data = [d for d in sample_data if d["tenant"] in can_nap]

    # 4. Khởi chạy tiến trình BPMN Flowable thật (F-42)
    proc_map = await seed_flowable_processes(sample_data, user_sub_map, can_nap)

    # 5. Nạp dữ liệu vào PostgreSQL (F-29, F-42)
    await seed_database(user_sub_map, proc_map, can_nap)

    print("=================================================================")
    print(" [DX-OS] HOÀN TẤT NẠP DỮ LIỆU MẪU! THÔNG TIN ĐĂNG NHẬP:")
    print(" Danh sách tài khoản và mật khẩu đã lưu tại: secrets/demo-accounts.txt")
    print("-----------------------------------------------------------------")
    for acc in accounts:
        u = acc["username"]
        pw = passwords.get(u, "")
        print(f"  * Tài khoản: {u:<12} | Mật khẩu: {pw:<16} | Vai: {acc['role']}")
    print("=================================================================")


if __name__ == "__main__":
    asyncio.run(main())

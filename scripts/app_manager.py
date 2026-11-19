#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Công cụ quản lý vòng đời gói ứng dụng (Application Package Manager):
- Cài đặt gói ứng dụng: `python scripts/app_manager.py install cap-phep`
  (tương đương `install --app cap-phep`; thêm `--tenant phuong-a` để chỉ đăng ký một phường,
  `--seed` để nạp dữ liệu mẫu sau khi cài)
- Nâng cấp: `python scripts/app_manager.py upgrade cap-phep` (chạy lại các bước, idempotent)
- Gỡ bỏ gói ứng dụng: `python scripts/app_manager.py uninstall cap-phep`
  (chỉ xóa schema, tri thức và chính sách của chính ứng dụng)

Mã thoát: 0 thành công; 1 lỗi cài đặt/hạ tầng; 2 tham số sai.
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Ensure UTF-8 output on all platforms
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception) as _e:
        _ = _e

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services"))

import httpx
import asyncpg
import yaml
from typing import List, Optional
from dxos_core.app_contract import load_app_manifest
from dxos_core.config import settings

_OWNER_POOL: Optional[asyncpg.Pool] = None


async def get_owner_db_pool() -> Optional[asyncpg.Pool]:
    """Kết nối PostgreSQL với quyền dxos_owner chuyên dụng cho migration ứng dụng (V3-01)."""
    global _OWNER_POOL
    if _OWNER_POOL is not None:
        return _OWNER_POOL

    owner_user = os.getenv("DXOS_OWNER_USER", "dxos_owner")
    owner_password = os.getenv("DXOS_OWNER_PASSWORD", "")
    if not owner_password:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("DXOS_OWNER_PASSWORD="):
                    owner_password = line.split("=", 1)[1].strip()
                    break

    dsn = f"postgresql://{owner_user}:{owner_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    for attempt in range(5):
        try:
            _OWNER_POOL = await asyncpg.create_pool(
                dsn=dsn,
                min_size=1,
                max_size=5,
                command_timeout=15.0,
                timeout=5.0,
            )
            return _OWNER_POOL
        except Exception as e:
            if attempt == 4:
                print(f"[ERROR] Không thể kết nối DB với tài khoản {owner_user}: {e}", file=sys.stderr)
                return None
            await asyncio.sleep(0.5)
    return None


def app_tenants(app_dir: Path) -> List[str]:
    """Danh sách phường khai báo trong app.yaml (khóa `tenants`)."""
    data = yaml.safe_load((app_dir / "app.yaml").read_text(encoding="utf-8")) or {}
    return list(data.get("tenants") or ["phuong-a", "phuong-b"])


async def deploy_if_changed(client: httpx.AsyncClient, bpmn_path: Path, tenant: str) -> bool:
    """Deploy tệp BPMN cho một tenant; bỏ qua nếu bản mới nhất đã giống hệt (không tạo deployment trùng)."""
    auth = (settings.flowable_user, settings.flowable_password)
    base = f"{settings.flowable_url}/service/repository/deployments"
    content = bpmn_path.read_bytes()
    # Flowable đặt tên deployment theo tên tệp bỏ đuôi .bpmn20.xml
    dep_name = bpmn_path.name.removesuffix(".bpmn20.xml")
    params = {"name": dep_name, "sort": "deployTime", "order": "desc", "size": 1}
    if tenant:
        params["tenantId"] = tenant
    else:
        params["withoutTenantId"] = "true"
    found = await client.get(base, params=params, auth=auth)
    if found.status_code == 200 and found.json().get("data"):
        dep_id = found.json()["data"][0]["id"]
        old = await client.get(f"{base}/{dep_id}/resourcedata/{bpmn_path.name}", auth=auth)
        if old.status_code == 200 and old.content == content:
            return False
    files = {"file": (bpmn_path.name, content, "text/xml")}
    data = {"tenantId": tenant} if tenant else {}
    resp = await client.post(base, auth=auth, files=files, data=data)
    if resp.status_code not in (200, 201):
        print(f"[ERROR] Flowable từ chối deploy {bpmn_path.name} (tenant={tenant}): HTTP {resp.status_code}", file=sys.stderr)
        sys.exit(1)
    return True


def run_seed(root: Path, app_dir: Path, manifest, tenant: Optional[str]) -> None:
    """Chạy kịch bản seed khai báo trong app.yaml (seed.script)."""
    if not manifest.seed or not getattr(manifest.seed, "script", None):
        print("--> 6. Ứng dụng không khai báo seed, bỏ qua.")
        return
    script = app_dir / manifest.seed.script
    print(f"--> 6. Nạp dữ liệu mẫu bằng {script.relative_to(root)}...")
    cmd = [sys.executable, str(script)] + (["--tenant", tenant] if tenant else [])
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(root / "services"), str(root), env.get("PYTHONPATH", "")]))
    code = subprocess.call(cmd, cwd=str(root), env=env)
    if code != 0:
        print(f"[ERROR] Seed thất bại (mã {code}).", file=sys.stderr)
        sys.exit(1)


async def install_app(app_code: str, tenant: Optional[str] = None, seed: bool = False):
    root = Path(__file__).resolve().parent.parent
    app_dir = root / "apps" / app_code
    if not app_dir.exists():
        print(f"[ERROR] Không tìm thấy thư mục ứng dụng tại {app_dir}", file=sys.stderr)
        sys.exit(1)
    declared = app_tenants(app_dir)
    if tenant and tenant not in declared:
        print(f"[ERROR] Tenant '{tenant}' không có trong app.yaml (tenants: {', '.join(declared)})", file=sys.stderr)
        sys.exit(2)
    target_tenants = [tenant] if tenant else declared

    print("==========================================================")
    print(f" [APP-INSTALL] BẮT ĐẦU CÀI ĐẶT GÓI ỨNG DỤNG: {app_code} ")
    print("==========================================================")

    manifest = load_app_manifest(app_dir)
    print(f"  * Tên ứng dụng: {manifest.name}")
    print(f"  * Phiên bản: {manifest.version}")
    print(f"  * Schema cơ sở dữ liệu: {manifest.schema_name}")
    print(f"  * Tenant: {', '.join(target_tenants)}")

    pool = await get_owner_db_pool()

    # 1. Chạy các tệp kịch bản SQL migration
    raw = yaml.safe_load((app_dir / "app.yaml").read_text(encoding="utf-8")) or {}
    migrations_dir = app_dir / raw.get("migrations", "db/migrations")
    if migrations_dir.exists():
        print("--> 1. Thực thi các tệp SQL migration...")
        if not pool:
            print("[ERROR] Cơ sở dữ liệu PostgreSQL không sẵn sàng! Quá trình cài đặt gói ứng dụng thất bại.", file=sys.stderr)
            sys.exit(1)
        async with pool.acquire() as conn:
            # Khởi tạo schema với quyền sở hữu của dxos_owner (V3-01)
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {manifest.schema_name} AUTHORIZATION dxos_owner;")
            for sql_file in sorted(migrations_dir.glob("*.sql")):
                print(f"  - Đang chạy migration {sql_file.name}...")
                sql_content = sql_file.read_text(encoding="utf-8")
                await conn.execute(sql_content)
            # F-43: Báo hiệu PostgREST nạp lại schema mới ngay lập tức
            await conn.execute("NOTIFY pgrst, 'reload schema'")
            print("  [PASS] Đã hoàn thành khởi tạo schema và gửi NOTIFY pgrst reload schema.")

    # 1b. Đồng bộ manifest giấy tờ bắt buộc từ app.yaml (P1)
    if getattr(manifest, "document_manifest", None) and pool:
        print("--> 1b. Đồng bộ manifest giấy tờ bắt buộc (P1)...")
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM app_cap_phep.document_requirements")
            for idx, req in enumerate(manifest.document_manifest.requirements, start=1):
                await conn.execute(
                    """
                    INSERT INTO app_cap_phep.document_requirements
                        (loai, ten, bat_buoc, yeu_cau_hieu_luc, thong_tin, mo_ta, thu_tu,
                         legal_citation_key, mau_bieu, doi_tuong, updated_at)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10, now())
                    """,
                    req.loai,
                    req.ten,
                    bool(req.bat_buoc),
                    bool(req.yeu_cau_hieu_luc),
                    json.dumps(req.thong_tin or [], ensure_ascii=False),
                    req.mo_ta,
                    idx,
                    req.legal_citation_key,
                    req.mau_bieu,
                    req.doi_tuong,
                )
            await conn.execute("NOTIFY pgrst, 'reload schema'")
            print(f"  [PASS] Đã nạp {len(manifest.document_manifest.requirements)} loại giấy tờ vào manifest.")

    # 2. Deploy các tệp quy trình BPMN vào Flowable cho các tenant và global
    print("--> 2. Triển khai quy trình BPMN vào Flowable Engine...")
    tenants = [""] + target_tenants
    all_bpmn_files = [app_dir / bp for bp in manifest.bpmn if (app_dir / bp).exists()]
    core_flow_dir = root / "core" / "flowable"
    if core_flow_dir.exists():
        for bpmn_f in core_flow_dir.glob("*.bpmn20.xml"):
            if bpmn_f not in all_bpmn_files:
                all_bpmn_files.append(bpmn_f)

    for bpmn_path in all_bpmn_files:
        if bpmn_path.exists():
            print(f"  - Đang deploy {bpmn_path.name}...")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    moi = [t or "global" for t in tenants if await deploy_if_changed(client, bpmn_path, t)]
                    if moi:
                        print(f"    [OK] Đã deploy {bpmn_path.name} cho: {', '.join(moi)}.")
                    else:
                        print(f"    [OK] {bpmn_path.name} không đổi, bỏ qua.")
            except httpx.HTTPError as e:
                print(f"[ERROR] Không thể kết nối tới Flowable REST ({e}) để deploy quy trình BPMN! Quá trình cài đặt thất bại.", file=sys.stderr)
                sys.exit(1)

    # 3. Đồng bộ vai trò vào Keycloak Realm (F-40)
    print(f"--> 3. Đồng bộ {len(manifest.roles)} vai trò nghiệp vụ vào Keycloak...")
    token_url = f"{settings.keycloak_internal_url}/realms/master/protocol/openid-connect/token"
    roles_url = f"{settings.keycloak_internal_url}/admin/realms/{settings.keycloak_realm}/roles"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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
                print(f"[ERROR] Không lấy được admin token để tạo roles: {token_resp.text}", file=sys.stderr)
                sys.exit(1)

            admin_token = token_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
            existing_roles_resp = await client.get(roles_url, headers=headers)
            existing = {r["name"] for r in existing_roles_resp.json()} if existing_roles_resp.status_code == 200 else set()

            for role in manifest.roles:
                full_role_code = f"app:{app_code}:{role.code}"
                if full_role_code not in existing:
                    resp = await client.post(
                        roles_url,
                        headers=headers,
                        json={"name": full_role_code, "description": role.name},
                    )
                    if resp.status_code in (201, 204):
                        print(f"  [OK] Đã tạo vai trò: {full_role_code} ({role.name})")
                else:
                    print(f"  [OK] Vai trò đã tồn tại: {full_role_code}")
    except Exception as e:
        print(f"[ERROR] Không thể kết nối Keycloak Admin API để đồng bộ vai trò: {e}", file=sys.stderr)
        sys.exit(1)

    # 4. Nạp tài liệu tri thức RAG vào core.knowledge_chunks
    if manifest.knowledge:
        knowledge_dir = app_dir / manifest.knowledge.dir
        if knowledge_dir.exists():
            print("--> 4. Nạp tài liệu tri thức phục vụ Trợ lý AI (RAG)...")
            if pool:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM core.knowledge_chunks WHERE app = $1 AND tenant = ANY($2::text[])",
                        app_code, target_tenants,
                    )
            for md_file in sorted(knowledge_dir.glob("*.md")):
                content = md_file.read_text(encoding="utf-8")
                # Bỏ header SPDX/HTML comment để câu trả lời RAG không bị nhiễu
                content = re.sub(r"<!--.*?-->", "", content, flags=re.S)
                content = "\n".join(
                    line for line in content.splitlines()
                    if not line.strip().startswith("# SPDX-")
                )
                parts = content.split("## ")
                chunks = [f"## {c.strip()}" for c in parts[1:] if c.strip()] or [content.strip()]
                if pool:
                    async with pool.acquire() as conn:
                        for t in target_tenants:
                            for chunk in chunks:
                                await conn.execute(
                                    """
                                    INSERT INTO core.knowledge_chunks (tenant, app, source, chunk)
                                    VALUES ($1, $2, $3, $4)
                                    """,
                                    t,
                                    app_code,
                                    md_file.name,
                                    chunk,
                                )
                print(f"  - Đã nạp {len(chunks)} đoạn tri thức từ {md_file.name} cho {', '.join(target_tenants)}")

            # 4b. Nạp trích dẫn pháp lý (A-LEGAL-01) để trợ lý trả citation có điều/khoản.
            legal_dir = root / "core" / "legal"
            citations_file = legal_dir / "citations.json"
            docs_file = legal_dir / "danh_muc_van_ban.json"
            if citations_file.exists() and docs_file.exists() and pool:
                citations = json.loads(citations_file.read_text(encoding="utf-8"))
                docs = {d["document_id"]: d for d in json.loads(docs_file.read_text(encoding="utf-8"))}
                async with pool.acquire() as conn:
                    for cit in citations:
                        doc = docs.get(cit["document_id"])
                        if not doc:
                            continue
                        pos = " ".join(x for x in [cit.get("clause"), cit.get("point")] if x)
                        chunk = (
                            f"Văn bản {doc['code']} ({doc['title']}) — {cit['article']}"
                            f"{', ' + pos if pos else ''}: {cit['summary']} "
                            f"Trạng thái hiệu lực: {doc.get('status') or 'cần đối chiếu'}; "
                            f"ngày hiệu lực: {doc.get('effective_date') or 'chưa xác định'}."
                        )
                        for t in target_tenants:
                            await conn.execute(
                                "INSERT INTO core.knowledge_chunks (tenant, app, source, chunk) VALUES ($1, $2, $3, $4)",
                                t, app_code, f"legal/{cit['citation_key']}", chunk,
                            )
                print(f"  - Đã nạp {len(citations)} trích dẫn pháp lý cho {', '.join(target_tenants)}")

    # 5. Lưu trữ chính sách hợp đồng vào core.app_policies (V2-08)
    if pool:
        print("--> 5. Nạp chính sách ứng dụng vào core.app_policies...")
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM core.app_policies WHERE app_code = $1", app_code)

            for obj_type, func_name in (manifest.object_access or {}).items():
                await conn.execute(
                    """
                    INSERT INTO core.app_policies (app_code, policy_type, policy_key, policy_data)
                    VALUES ($1, 'object_access', $2, $3::jsonb)
                    ON CONFLICT (app_code, policy_type, policy_key) DO UPDATE SET policy_data = EXCLUDED.policy_data
                    """,
                    app_code,
                    obj_type,
                    json.dumps({"function_name": func_name}),
                )

            if manifest.flow_policies:
                await conn.execute(
                    """
                    INSERT INTO core.app_policies (app_code, policy_type, policy_key, policy_data)
                    VALUES ($1, 'flow_policies', 'default', $2::jsonb)
                    ON CONFLICT (app_code, policy_type, policy_key) DO UPDATE SET policy_data = EXCLUDED.policy_data
                    """,
                    app_code,
                    json.dumps(manifest.flow_policies),
                )

            for doc_type, signer_cfg in (manifest.doc_signers or {}).items():
                await conn.execute(
                    """
                    INSERT INTO core.app_policies (app_code, policy_type, policy_key, policy_data)
                    VALUES ($1, 'doc_signers', $2, $3::jsonb)
                    ON CONFLICT (app_code, policy_type, policy_key) DO UPDATE SET policy_data = EXCLUDED.policy_data
                    """,
                    app_code,
                    doc_type,
                    json.dumps(signer_cfg),
                )

            if manifest.break_glass:
                await conn.execute(
                    """
                    INSERT INTO core.app_policies (app_code, policy_type, policy_key, policy_data)
                    VALUES ($1, 'break_glass', 'config', $2::jsonb)
                    ON CONFLICT (app_code, policy_type, policy_key) DO UPDATE SET policy_data = EXCLUDED.policy_data
                    """,
                    app_code,
                    json.dumps(manifest.break_glass),
                )

            for thu_tu, m in enumerate(manifest.metrics, start=1):
                await conn.execute(
                    """
                    INSERT INTO core.app_policies (app_code, policy_type, policy_key, policy_data)
                    VALUES ($1, 'metrics', $2, $3::jsonb)
                    ON CONFLICT (app_code, policy_type, policy_key) DO UPDATE SET policy_data = EXCLUDED.policy_data
                    """,
                    app_code,
                    m.code,
                    json.dumps({**m.model_dump(), "thu_tu": thu_tu}, ensure_ascii=False),
                )
            print("  [PASS] Đã đồng bộ chính sách app policies vào core.")

    if seed:
        run_seed(root, app_dir, manifest, tenant)

    print("==========================================================")
    print(f" [APP-INSTALL] CÀI ĐẶT THÀNH CÔNG GÓI ỨNG DỤNG {app_code}! ")
    print("==========================================================")


async def uninstall_app(app_code: str):
    root = Path(__file__).resolve().parent.parent
    app_dir = root / "apps" / app_code
    if not app_dir.exists():
        print(f"[ERROR] Không tìm thấy thư mục ứng dụng tại {app_dir}", file=sys.stderr)
        sys.exit(1)

    print("==========================================================")
    print(f" [APP-UNINSTALL] BẮT ĐẦU GỠ BỎ GÓI ỨNG DỤNG: {app_code} ")
    print("==========================================================")

    manifest = load_app_manifest(app_dir)
    pool = await get_owner_db_pool()

    if not pool:
        print(f"[ERROR] Cơ sở dữ liệu PostgreSQL không sẵn sàng! Không thể gỡ bỏ schema {manifest.schema_name}.", file=sys.stderr)
        sys.exit(1)

    async with pool.acquire() as conn:
        print(f"--> Xóa bỏ schema cơ sở dữ liệu: {manifest.schema_name}...")
        await conn.execute(f"DROP SCHEMA IF EXISTS {manifest.schema_name} CASCADE")

        print(f"--> Xóa bỏ tài liệu tri thức của ứng dụng {app_code}...")
        await conn.execute("DELETE FROM core.knowledge_chunks WHERE app = $1", app_code)

        print("--> Xóa bỏ chính sách ứng dụng trong core.app_policies...")
        await conn.execute("DELETE FROM core.app_policies WHERE app_code = $1", app_code)

    print("==========================================================")
    print(f" [APP-UNINSTALL] ĐÃ GỠ BỎ HOÀN TOÀN GÓI ỨNG DỤNG {app_code}! ")
    print(" LÕI TẦNG 1 VẪN HOẠT ĐỘNG HOÀN TOÀN ĐỘC LẬP VÀ BÌNH THƯỜNG.")
    print("==========================================================")


def main(argv=None):
    parser = argparse.ArgumentParser(description="DX-OS App Package Manager")
    parser.add_argument("action", choices=["install", "upgrade", "uninstall"],
                        help="install / upgrade (chạy lại, idempotent) / uninstall")
    parser.add_argument("app", nargs="?", help="Mã ứng dụng (ví dụ: cap-phep)")
    parser.add_argument("--app", dest="app_opt", help="Mã ứng dụng (cách viết khác của tham số app)")
    parser.add_argument("--tenant", help="Chỉ đăng ký một phường (mặc định: mọi phường trong app.yaml)")
    parser.add_argument("--seed", action="store_true", help="Nạp dữ liệu mẫu sau khi cài")
    args = parser.parse_args(argv)
    app = args.app_opt or args.app
    if not app or (args.app and args.app_opt and args.app != args.app_opt):
        parser.error("cần đúng một mã ứng dụng: `install cap-phep` hoặc `install --app cap-phep`")

    if args.action in ("install", "upgrade"):
        asyncio.run(install_app(app, tenant=args.tenant, seed=args.seed))
    else:
        asyncio.run(uninstall_app(app))


if __name__ == "__main__":
    main()

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Script tự động quét lộ lọt dữ liệu theo bảng và vai trò (Q-03).

Tự động liệt kê từ pg_class và pg_proc:
- Toàn bộ bảng, khung nhìn trong app_cap_phep và core_api mà web_user đọc được.
- Toàn bộ hàm/thủ tục trong app_cap_phep và core_api mà web_user gọi được.

Kiểm tra trên 4 vai mẫu với dữ liệu được tạo đủ trên 2 phường:
1. cdtX: Chủ đầu tư không có hồ sơ nào ở phường A (kỳ vọng: 0 dòng ở mọi bảng gốc).
2. cdt.minh: Chủ đầu tư sở hữu hồ sơ tại phường A (kỳ vọng: chỉ thấy dữ liệu của mình).
3. td.chua_phan_cong: Thẩm định viên chưa phân công tại phường A (kỳ vọng: không thấy hồ sơ chưa phân công, không thấy phiếu kiểm tra).
4. mc.phuongb: Cán bộ một cửa phường B (kỳ vọng: tuyệt đối không thấy bất kỳ dữ liệu nào của phường A).

Ngoại lệ hợp lệ duy nhất: view công khai cong_khai_giay_phep (chỉ gồm dữ liệu không nhạy cảm phục vụ cộng đồng theo Q-02).
"""

import asyncio
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Cấu hình kết nối DB
def get_db_params():
    env_file = ROOT / ".env"
    env_vars = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip("'\"")

    host = os.getenv("POSTGRES_HOST") or env_vars.get("POSTGRES_HOST") or "localhost"
    port = int(os.getenv("POSTGRES_PORT") or env_vars.get("POSTGRES_PORT") or "5432")
    user = os.getenv("POSTGRES_SUPERUSER") or env_vars.get("POSTGRES_SUPERUSER") or "postgres"
    password = (
        os.getenv("POSTGRES_SUPERUSER_PASSWORD")
        or os.getenv("PGPASSWORD")
        or env_vars.get("POSTGRES_SUPERUSER_PASSWORD")
        or ""
    )
    database = os.getenv("POSTGRES_DB") or env_vars.get("POSTGRES_DB") or "dxos"

    pw_file = ROOT / "secrets" / "postgres-password.txt"
    if not password and pw_file.exists():
        password = pw_file.read_text(encoding="utf-8").strip()

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


def make_claims(sub: str, tenant: str, roles: list[str]) -> str:
    return json.dumps({"sub": sub, "tenant": tenant, "roles": roles})


# 4 personas theo yêu cầu của Q-03
PERSONAS = {
    "cdtX": {
        "name": "Chủ đầu tư chưa có hồ sơ",
        "tenant": "phuong-a",
        "sub": "cdtX-sub-0000",
        "roles": ["app:cap-phep:chu-dau-tu"],
    },
    "cdt.minh": {
        "name": "Chủ đầu tư có hồ sơ tại phường A",
        "tenant": "phuong-a",
        "sub": "cdt.minh-sub-0001",
        "roles": ["app:cap-phep:chu-dau-tu"],
    },
    "td.chua_phan_cong": {
        "name": "Thẩm định viên chưa phân công (A)",
        "tenant": "phuong-a",
        "sub": "td.chua_phan_cong-sub-0002",
        "roles": ["app:cap-phep:tham-dinh"],
    },
    "mc.phuongb": {
        "name": "Cán bộ một cửa phường B",
        "tenant": "phuong-b",
        "sub": "mc.phuongb-sub-0003",
        "roles": ["app:cap-phep:mot-cua"],
    },
}

# Ngoại lệ được phép công khai theo quy định pháp lý (Q-02)
PUBLIC_VIEW_ALLOWLIST = {
    "app_cap_phep.cong_khai_giay_phep": "Khung nhìn công khai giấy phép xây dựng theo Điều 53 Luật Xây dựng (Q-02)",
    "app_cap_phep.document_requirements": "Danh mục manifest giấy tờ công khai theo thủ tục, không chứa PII hay dữ liệu hồ sơ",
}


async def seed_test_data(conn, test_ids):
    """Tạo dữ liệu mẫu đầy đủ trên 2 phường: hồ sơ, tệp, giấy phép, công trình, phiếu kiểm tra, break-glass, DSAR, consents."""
    # 1. Hồ sơ phường A và phường B
    for t, p_key in [("phuong-a", "A"), ("phuong-b", "B")]:
        hs_id = test_ids[f"hs_{p_key}"]
        owner_sub = PERSONAS["cdt.minh"]["sub"] if p_key == "A" else "cdtB-other-sub"
        ma_hs = f"CP-SCAN-{p_key}-{uuid.uuid4().hex[:6].upper()}"
        so_gp = f"GP-SCAN-{p_key}-{uuid.uuid4().hex[:6].upper()}"
        ma_ct = f"CT-SCAN-{p_key}-{uuid.uuid4().hex[:6].upper()}"

        await conn.execute(
            """
            INSERT INTO app_cap_phep.ho_so (
                id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
                dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2,
                khu_quan_ly_kien_truc, trang_thai, buoc, han_tong_at
            ) VALUES (
                $1, $2, $3, $4, $5, '001099009999', '0909999999',
                'Địa chỉ kiểm thử quét lộ lọt', 'Thửa scan', 2, 100.0,
                true, 'DA_CAP', 'hoan_tat', now() + interval '30 days'
            ) ON CONFLICT DO NOTHING;
            """,
            hs_id, t, ma_hs, owner_sub, f"Chủ sở hữu {p_key}"
        )

        # File & hồ sơ tệp
        fid = test_ids[f"file_{p_key}"]
        await conn.execute(
            """
            INSERT INTO core.files (id, tenant, owner_sub, object_key, sha256, size, mime)
            VALUES ($1, $2, $3, $4, 'sha-scan', 1024, 'application/pdf')
            ON CONFLICT DO NOTHING;
            """,
            fid, t, owner_sub, f"scan/{fid}"
        )
        await conn.execute(
            """
            INSERT INTO app_cap_phep.ho_so_tep (id, ho_so_id, file_id, loai)
            VALUES ($1, $2, $3, 'ban_ve')
            ON CONFLICT DO NOTHING;
            """,
            test_ids[f"hst_{p_key}"], hs_id, fid
        )

        # Giấy phép
        gp_id = test_ids[f"gp_{p_key}"]
        await conn.execute(
            """
            INSERT INTO app_cap_phep.giay_phep (id, tenant, ho_so_id, so_giay_phep, signed_doc_id, trang_thai, ngay_cap)
            VALUES ($1, $2, $3, $4, gen_random_uuid(), 'hieu_luc', now())
            ON CONFLICT DO NOTHING;
            """,
            gp_id, t, hs_id, so_gp
        )

        # Công trình
        ct_id = test_ids[f"ct_{p_key}"]
        await conn.execute(
            """
            INSERT INTO app_cap_phep.cong_trinh (id, tenant, giay_phep_id, ma_cong_trinh, entity_id, dia_chi, trang_thai_thi_cong)
            VALUES ($1, $2, $3, $4, 'urn:ngsi-ld:Site:' || $4, 'Đường Scan', 'DANG_THI_CONG')
            ON CONFLICT DO NOTHING;
            """,
            ct_id, t, gp_id, ma_ct
        )

        # Phiếu kiểm tra
        pkt_id = test_ids[f"pkt_{p_key}"]
        await conn.execute(
            """
            INSERT INTO app_cap_phep.phieu_kiem_tra (id, tenant, cong_trinh_id, nguon, chi_so, gia_tri, nguong, trang_thai, ket_luan)
            VALUES ($1, $2, $3, 'cam_bien', 'laeq_dba', 80.0, 70.0, 'CHO_KIEM_TRA', 'Chờ xử lý')
            ON CONFLICT DO NOTHING;
            """,
            pkt_id, t, ct_id
        )

        # Break-glass
        bg_id = test_ids[f"bg_{p_key}"]
        await conn.execute(
            """
            INSERT INTO core.break_glass (id, tenant, requester_sub, object_type, object_id, reason, status, expires_at)
            VALUES ($1, $2, 'canbo-other', 'ho_so', $3, 'Quét lộ lọt', 'pending', now() + interval '2 hours')
            ON CONFLICT DO NOTHING;
            """,
            bg_id, t, hs_id
        )

        # DSAR
        dsar_id = test_ids[f"dsar_{p_key}"]
        await conn.execute(
            """
            INSERT INTO core.dsar_requests (id, tenant, subject_sub, type, status, ack_due_at, due_at, legal_basis_note)
            VALUES ($1, $2, $3, 'access', 'received', now() + interval '2 days', now() + interval '10 days', 'Quét quyền riêng tư')
            ON CONFLICT DO NOTHING;
            """,
            dsar_id, t, owner_sub
        )

        # Consents
        await conn.execute(
            """
            INSERT INTO core.consents (id, tenant, subject_sub, purpose, text_version, granted_at)
            VALUES (gen_random_uuid(), $1, $2, 'scan_purpose', 'v1.0', now())
            ON CONFLICT DO NOTHING;
            """,
            t, owner_sub
        )


async def query_as_persona(conn, claims_json, sql):
    tr = conn.transaction()
    await tr.start()
    try:
        await conn.execute("SET LOCAL ROLE web_user")
        await conn.execute("SELECT set_config('request.jwt.claims', $1, true)", claims_json)
        rows = await conn.fetch(sql)
        await tr.rollback()
        return True, rows
    except Exception as e:
        await tr.rollback()
        return False, str(e)


async def run_scan():
    params = get_db_params()

    import asyncpg
    import shutil
    try:
        conn = await asyncpg.connect(**params)
    except Exception as e:
        # Nếu đang ở trong container hoặc không có lệnh docker, báo lỗi trực tiếp
        if Path("/.dockerenv").exists() or not shutil.which("docker"):
            print(f"[scan_exposure] Lỗi kết nối CSDL trong container: {e}")
            sys.exit(1)
        # Nếu chạy trên host Windows không map port, tự động chạy qua container tools
        cmd = ["docker", "compose", "run", "--rm", "tools", "python", "scripts/scan_exposure.py"]
        res = subprocess.run(cmd)  # noqa: ASYNC221
        sys.exit(res.returncode)

    # 1. Chuẩn bị IDs cho dữ liệu test
    test_ids = {
        "hs_A": uuid.uuid4(), "file_A": uuid.uuid4(), "hst_A": uuid.uuid4(),
        "gp_A": uuid.uuid4(), "ct_A": uuid.uuid4(), "pkt_A": uuid.uuid4(),
        "bg_A": uuid.uuid4(), "dsar_A": uuid.uuid4(),
        "hs_B": uuid.uuid4(), "file_B": uuid.uuid4(), "hst_B": uuid.uuid4(),
        "gp_B": uuid.uuid4(), "ct_B": uuid.uuid4(), "pkt_B": uuid.uuid4(),
        "bg_B": uuid.uuid4(), "dsar_B": uuid.uuid4(),
    }

    # 2. Tạo dữ liệu mẫu 2 phường
    await seed_test_data(conn, test_ids)

    # 3. Tự động liệt kê bảng và view có quyền SELECT cho web_user từ pg_class
    target_relations = await conn.fetch("""
        SELECT n.nspname AS schema_name, c.relname AS rel_name, c.relkind AS rel_kind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('app_cap_phep', 'core_api')
          AND c.relkind IN ('r', 'v', 'm')
          AND has_table_privilege('web_user', c.oid, 'SELECT')
        ORDER BY n.nspname, c.relname;
    """)

    # 4. Tự động liệt kê hàm/RPC có quyền EXECUTE cho web_user từ pg_proc
    target_procs = await conn.fetch("""
        SELECT n.nspname AS schema_name, p.proname AS proc_name,
               pg_get_function_identity_arguments(p.oid) AS args
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname IN ('app_cap_phep', 'core_api')
          AND has_function_privilege('web_user', p.oid, 'EXECUTE')
        ORDER BY n.nspname, p.proname;
    """)

    print("# BÁO CÁO RÀ SOÁT TỰ ĐỘNG LỘ LỌT DỮ LIỆU & PHÂN QUYỀN (Q-03)")
    print(f"- **Thời điểm quét:** {asyncio.get_event_loop().time()}")
    print(f"- **Tổng số quan hệ (bảng/view) mở cho `web_user`:** {len(target_relations)}")
    print(f"- **Tổng số hàm/RPC mở cho `web_user`:** {len(target_procs)}")
    print()

    print("## 1. Kết quả kiểm tra bảng & khung nhìn qua 4 vai mẫu")
    print()
    print("| Quan hệ | Loại | Vai kiểm thử | Tổng thấy | Dòng hợp lệ | Lộ lọt trái phép | Đánh giá | Ghi chú |")
    print("|---|---|---|---|---|---|---|---|")

    total_violations = 0

    for rel in target_relations:
        schema = rel["schema_name"]
        rel_name = rel["rel_name"]
        full_name = f"{schema}.{rel_name}"
        kind_str = "Bảng" if rel["rel_kind"] == "r" else "Khung nhìn"

        # Lấy danh sách cột để nhận biết các trường nhạy cảm
        cols = [r["column_name"] for r in await conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
        """, schema, rel_name)]

        for p_key, p_info in PERSONAS.items():
            claims_json = make_claims(p_info["sub"], p_info["tenant"], p_info["roles"])
            ok, rows = await query_as_persona(conn, claims_json, f"SELECT * FROM {full_name}")

            if not ok:
                print(f"| `{full_name}` | {kind_str} | `{p_key}` | Lỗi | 0 | 0 | **FAIL** | Lỗi truy vấn: {rows} |")
                total_violations += 1
                continue

            total_seen = len(rows)
            unauthorized_count = 0
            reason = "Đạt kiểm tra"

            # Đánh giá dòng không thuộc về:
            if full_name in PUBLIC_VIEW_ALLOWLIST:
                # View công khai: cho phép mọi vai đọc nếu không lộ khóa nhạy cảm
                leak_keys = [k for k in ("ho_so_id", "signed_doc_id", "cccd", "dien_thoai") if k in cols]
                if leak_keys:
                    unauthorized_count = total_seen
                    reason = f"Lộ khóa nhạy cảm trong view công khai: {leak_keys}"
                else:
                    unauthorized_count = 0
                    reason = "Công khai hợp lệ (không chứa khóa nhạy cảm)"

            elif p_key == "cdtX":
                # Chủ đầu tư không có hồ sơ: mọi dòng nhìn thấy ở bảng nghiệp vụ đều là vi phạm
                if total_seen > 0:
                    unauthorized_count = total_seen
                    reason = f"Chủ đầu tư không hồ sơ nhưng thấy {total_seen} dòng"

            elif p_key == "cdt.minh":
                # Chỉ được thấy dữ liệu thuộc hồ sơ của chính mình (tenant phường A)
                for r in rows:
                    r_dict = dict(r)
                    if "tenant" in r_dict and r_dict["tenant"] != "phuong-a":
                        unauthorized_count += 1
                    elif "chu_dau_tu_sub" in r_dict and r_dict["chu_dau_tu_sub"] != p_info["sub"]:
                        unauthorized_count += 1
                    elif "subject_sub" in r_dict and r_dict["subject_sub"] != p_info["sub"]:
                        unauthorized_count += 1
                if unauthorized_count > 0:
                    reason = f"Lộ {unauthorized_count} dòng của người khác hoặc phường khác"

            elif p_key == "td.chua_phan_cong":
                # Thẩm định viên chưa phân công: không thấy hồ sơ ở bảng gốc, không thấy phiếu kiểm tra, không thấy phường B
                for r in rows:
                    r_dict = dict(r)
                    if "tenant" in r_dict and r_dict["tenant"] != "phuong-a":
                        unauthorized_count += 1
                if full_name == "app_cap_phep.ho_so" and total_seen > 0:
                    unauthorized_count += total_seen
                    reason = "Bảng gốc ho_so lộ cho thẩm định viên chưa phân công"
                elif full_name == "app_cap_phep.phieu_kiem_tra" and total_seen > 0:
                    unauthorized_count += total_seen
                    reason = "Phiếu kiểm tra lộ cho thẩm định viên (thiếu vai trật tự XD)"
                elif unauthorized_count > 0:
                    reason = f"Lộ {unauthorized_count} dòng ngoài phường A"

            elif p_key == "mc.phuongb":
                # Cán bộ phường B: tuyệt đối không được thấy bất kỳ bản ghi nào của phường A
                for r in rows:
                    r_dict = dict(r)
                    if "tenant" in r_dict and r_dict["tenant"] == "phuong-a":
                        unauthorized_count += 1
                if unauthorized_count > 0:
                    reason = f"Vi phạm ranh giới đa thuê ước: thấy {unauthorized_count} dòng phường A"

            status = "**FAIL**" if unauthorized_count > 0 else "PASS"
            if unauthorized_count > 0:
                total_violations += 1

            valid_count = total_seen - unauthorized_count
            print(f"| `{full_name}` | {kind_str} | `{p_key}` | {total_seen} | {valid_count} | {unauthorized_count} | {status} | {reason} |")

    print()
    print("## 2. Kiểm toán các hàm & thủ tục (RPC) mở cho `web_user`")
    print()
    print("| Schema | Tên hàm | Tham số | Cơ chế thực thi | Đánh giá an toàn |")
    print("|---|---|---|---|---|")

    # Danh sách các hàm nhạy cảm tuyệt đối KHÔNG được mở cho web_user
    FORBIDDEN_FUNCS = {
        "sync_flow_state", "ghi_qua_han", "du_lieu_giay_phep",
        "cap_giay_phep", "tao_phieu_kiem_tra", "can_access_ho_so",
        "record_audit",
    }

    for pr in target_procs:
        fn = pr["proc_name"]
        schema = pr["schema_name"]
        args = pr["args"]
        if fn in FORBIDDEN_FUNCS:
            print(f"| `{schema}` | `{fn}` | `{args}` | EXECUTE | **FAIL (LỘ HÀM NỘI BỘ)** |")
            total_violations += 1
        else:
            print(f"| `{schema}` | `{fn}` | `{args}` | EXECUTE | PASS (API RPC hợp lệ) |")

    await conn.close()

    print()
    print("## 3. Tổng kết rà soát")
    if total_violations == 0:
        print("- **KẾT QUẢ:** **100% TUÂN THỦ (0 vi phạm lộ lọt dữ liệu)**")
        sys.exit(0)
    else:
        print(f"- **KẾT QUẢ:** **PHÁT HIỆN {total_violations} VI PHẠM LỘ LỌT DỮ LIỆU!**")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_scan())

#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Nạp hồ sơ "hero" phục vụ demo Track A (A-PLAN-08, A-ACC-05).

- CP-HERO-2026-001: hồ sơ 5 tầng tại TD-A-01 để demo quy hoạch fail → sửa 3 tầng pass.
- CP-HERO-ACC-2026-001: hồ sơ đã cấp phép, có mốc móng fail → khắc phục → đạt.
- Idempotent theo mã hồ sơ; không xóa dữ liệu khác.
- CP-HERO-2026-001 có quy trình cap-phep thật đang ở bước thẩm định, giao td.binh, để hồ sơ
  hiện trong Bàn làm việc của thẩm định viên (FIX-V11-08), có phân công và trạng thái như luồng
  thật nhờ chạy sync_flow_state cho các bước đã qua (FIX-V11-10). Cần Flowable ở 127.0.0.1:8082
  (FLOWABLE_HOST_URL) và FLOWABLE_PASSWORD trong môi trường hoặc .env; thiếu thì chỉ cảnh báo.

Chạy:
    py -3 scripts/seed_hero.py
    py -3 scripts/seed_hero.py --no-docker --psql "C:\\...\\psql.exe"
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception):
        pass

ROOT = Path(__file__).resolve().parent.parent

SQL = """
BEGIN;

-- 1. Hồ sơ hero quy hoạch: 5 tầng, 600 m2, tại TD-A-01.
INSERT INTO app_cap_phep.ho_so
    (tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai, dia_chi_cong_trinh,
     thua_dat, so_tang, dien_tich_san_m2, khu_quan_ly_kien_truc, trang_thai, buoc,
     han_tong_at, doi_tuong, loai_cong_trinh, ma_dinh_danh_dia_diem, loai_dat)
SELECT
    'phuong-a', 'CP-HERO-2026-001', u.id, 'Nguyễn Văn Minh', '001099000001', '0901234567',
    'Số 18 Đường Hòa Bình, phường A', 'TD-A-01', 5, 600.0, false, 'TIEP_NHAN', 'tham_dinh',
    now() + interval '7 days', 'ho_gia_dinh_ca_nhan', 'nha_o_rieng_le', '790101000001', 'dat_o'
FROM core.users_directory u
WHERE u.tenant = 'phuong-a' AND u.username = 'cdt.minh'
ON CONFLICT (ma_ho_so) DO UPDATE
SET ho_ten = EXCLUDED.ho_ten, dia_chi_cong_trinh = EXCLUDED.dia_chi_cong_trinh,
    thua_dat = EXCLUDED.thua_dat, so_tang = EXCLUDED.so_tang,
    dien_tich_san_m2 = EXCLUDED.dien_tich_san_m2, trang_thai = EXCLUDED.trang_thai,
    buoc = EXCLUDED.buoc, doi_tuong = EXCLUDED.doi_tuong,
    loai_cong_trinh = EXCLUDED.loai_cong_trinh,
    ma_dinh_danh_dia_diem = EXCLUDED.ma_dinh_danh_dia_diem,
    loai_dat = EXCLUDED.loai_dat, created_at = now(), updated_at = now();

-- 2. Hồ sơ hero nghiệm thu: đã cấp phép.
INSERT INTO app_cap_phep.ho_so
    (tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai, dia_chi_cong_trinh,
     thua_dat, so_tang, dien_tich_san_m2, khu_quan_ly_kien_truc, trang_thai, buoc,
     han_tong_at, doi_tuong, loai_cong_trinh, ma_dinh_danh_dia_diem, loai_dat)
SELECT
    'phuong-a', 'CP-HERO-ACC-2026-001', u.id, 'Trần Thị Hồng', '001099000002', '0902345678',
    'Số 20 Đường Hòa Bình, phường A', 'TD-A-02', 3, 420.0, true, 'DA_CAP', 'da_cap',
    now() + interval '7 days', 'ho_gia_dinh_ca_nhan', 'nha_o_rieng_le', '790101000002', 'dat_o'
FROM core.users_directory u
WHERE u.tenant = 'phuong-a' AND u.username = 'cdt.minh'
ON CONFLICT (ma_ho_so) DO UPDATE
SET ho_ten = EXCLUDED.ho_ten, dia_chi_cong_trinh = EXCLUDED.dia_chi_cong_trinh,
    thua_dat = EXCLUDED.thua_dat, so_tang = EXCLUDED.so_tang,
    dien_tich_san_m2 = EXCLUDED.dien_tich_san_m2, trang_thai = EXCLUDED.trang_thai,
    buoc = EXCLUDED.buoc, ma_dinh_danh_dia_diem = EXCLUDED.ma_dinh_danh_dia_diem,
    updated_at = now();

-- 3. Mốc nghiệm thu hero: móng fail (v1) → đạt (v2), kết cấu đạt.
WITH h AS (SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so = 'CP-HERO-ACC-2026-001')
INSERT INTO app_construction.moc_nghiem_thu
    (tenant, ho_so_id, loai_moc, version, ngay_nghiem_thu, ket_qua, nguoi_thuc_hien, ghi_chu, created_by)
SELECT 'phuong-a', h.id, v.loai, v.version, v.ngay::date, v.ket_qua, 'td.binh', v.ghi_chu, 'seed'
FROM h, (VALUES
    ('mong', 1, '2026-10-01', 'khong_dat', 'Cao độ đáy móng thấp hơn thiết kế 12 cm'),
    ('mong', 2, '2026-10-05', 'dat', 'Đã khắc phục và nghiệm thu lại'),
    ('ket_cau', 1, '2026-10-20', 'dat', 'Kết cấu đạt yêu cầu')
) AS v(loai, version, ngay, ket_qua, ghi_chu)
ON CONFLICT (tenant, ho_so_id, loai_moc, version) DO UPDATE
SET ket_qua = EXCLUDED.ket_qua, ghi_chu = EXCLUDED.ghi_chu, updated_at = now();

INSERT INTO app_construction.bien_ban_nghiem_thu
    (tenant, moc_id, so_bien_ban, ket_luan, nguoi_ky, created_by)
SELECT 'phuong-a', m.id, 'BB-HERO-MONG-01', 'Yêu cầu khắc phục cao độ móng', 'td.binh', 'seed'
FROM app_construction.moc_nghiem_thu m
JOIN app_cap_phep.ho_so h ON h.id = m.ho_so_id
WHERE h.ma_ho_so = 'CP-HERO-ACC-2026-001' AND m.loai_moc = 'mong' AND m.version = 1
ON CONFLICT (tenant, so_bien_ban) DO UPDATE SET ket_luan = EXCLUDED.ket_luan;

INSERT INTO app_construction.bien_ban_nghiem_thu
    (tenant, moc_id, so_bien_ban, ket_luan, nguoi_ky, created_by)
SELECT 'phuong-a', m.id, 'BB-HERO-MONG-02', 'Móng đạt yêu cầu sau khắc phục', 'td.binh', 'seed'
FROM app_construction.moc_nghiem_thu m
JOIN app_cap_phep.ho_so h ON h.id = m.ho_so_id
WHERE h.ma_ho_so = 'CP-HERO-ACC-2026-001' AND m.loai_moc = 'mong' AND m.version = 2
ON CONFLICT (tenant, so_bien_ban) DO UPDATE SET ket_luan = EXCLUDED.ket_luan;

-- 4. Thẩm định thiết kế 5.2: v1 thiếu kết cấu + MEP không đạt, v2 đủ 3 bộ môn đạt.
DELETE FROM app_cap_phep.nhan_xet_tham_dinh
WHERE phien_ban_id IN (
    'b2000000-0000-4000-8000-000000000001',
    'b2000000-0000-4000-8000-000000000002'
);
DELETE FROM app_cap_phep.ban_ve
WHERE phien_ban_id IN (
    'b2000000-0000-4000-8000-000000000001',
    'b2000000-0000-4000-8000-000000000002'
);
DELETE FROM app_cap_phep.phien_ban_thiet_ke
WHERE id IN (
    'b2000000-0000-4000-8000-000000000001',
    'b2000000-0000-4000-8000-000000000002'
);
DELETE FROM core.files
WHERE id IN (
    'b1000000-0000-4000-8000-000000000001',
    'b1000000-0000-4000-8000-000000000002',
    'b1000000-0000-4000-8000-000000000003'
);

INSERT INTO core.files (id, tenant, owner_sub, object_type, object_id, object_key, sha256, size, mime, status)
SELECT f.id, 'phuong-a',
       (SELECT id::text FROM core.users_directory WHERE tenant = 'phuong-a' AND username = 'cdt.minh'),
       'ho_so', h.id::text,
       COALESCE((SELECT object_key FROM core.files WHERE tenant = 'phuong-a' AND mime = 'application/pdf' AND status = 'clean' ORDER BY created_at LIMIT 1), 'seed/design-review.pdf'),
       f.sha, 1024, 'application/pdf', 'clean'
FROM app_cap_phep.ho_so h,
(VALUES
    ('b1000000-0000-4000-8000-000000000001'::uuid, repeat('1', 64)),
    ('b1000000-0000-4000-8000-000000000002'::uuid, repeat('2', 64)),
    ('b1000000-0000-4000-8000-000000000003'::uuid, repeat('3', 64))
) AS f(id, sha)
WHERE h.ma_ho_so = 'CP-HERO-2026-001';

INSERT INTO app_cap_phep.phien_ban_thiet_ke
    (id, tenant, ho_so_id, so_phien_ban, mo_ta_thay_doi, trang_thai, created_by, created_at, updated_at)
SELECT v.id, 'phuong-a', h.id, v.so, v.mo_ta, v.trang_thai,
       (SELECT id::text FROM core.users_directory WHERE tenant = 'phuong-a' AND username = 'cdt.minh'),
       now() - v.tuoi, now() - v.tuoi
FROM app_cap_phep.ho_so h,
(VALUES
    ('b2000000-0000-4000-8000-000000000001'::uuid, 1, 'Hồ sơ thiết kế ban đầu', 'khong_dat', interval '3 days'),
    ('b2000000-0000-4000-8000-000000000002'::uuid, 2, 'Bổ sung kết cấu và sửa sơ đồ cấp điện', 'dat', interval '1 day')
) AS v(id, so, mo_ta, trang_thai, tuoi)
WHERE h.ma_ho_so = 'CP-HERO-2026-001';

INSERT INTO app_cap_phep.ban_ve
    (id, tenant, phien_ban_id, ho_so_id, bo_mon, ten, file_id, sha256, kich_thuoc,
     trang_thai, nguoi_tham_dinh, ngay_tham_dinh, created_by, created_at)
SELECT v.id, 'phuong-a', v.phien_ban_id, h.id, v.bo_mon, v.ten, v.file_id, v.sha, 1024,
       v.trang_thai, v.nguoi, now() - interval '1 day',
       (SELECT id::text FROM core.users_directory WHERE tenant = 'phuong-a' AND username = 'cdt.minh'),
       now() - interval '2 days'
FROM app_cap_phep.ho_so h,
(VALUES
    ('b3000000-0000-4000-8000-000000000001'::uuid, 'b2000000-0000-4000-8000-000000000001'::uuid, 'kien_truc', 'KT-01 Mặt bằng tầng 1', 'b1000000-0000-4000-8000-000000000001'::uuid, repeat('1', 64), 'dat', 'Hoàng Văn Bình'),
    ('b3000000-0000-4000-8000-000000000002'::uuid, 'b2000000-0000-4000-8000-000000000001'::uuid, 'mep', 'MEP-01 Sơ đồ cấp điện', 'b1000000-0000-4000-8000-000000000002'::uuid, repeat('2', 64), 'khong_dat', 'Hoàng Văn Bình'),
    ('b3000000-0000-4000-8000-000000000003'::uuid, 'b2000000-0000-4000-8000-000000000002'::uuid, 'kien_truc', 'KT-01 Mặt bằng tầng 1', 'b1000000-0000-4000-8000-000000000001'::uuid, repeat('1', 64), 'dat', 'Hoàng Văn Bình'),
    ('b3000000-0000-4000-8000-000000000004'::uuid, 'b2000000-0000-4000-8000-000000000002'::uuid, 'ket_cau', 'KC-01 Mặt bằng kết cấu', 'b1000000-0000-4000-8000-000000000003'::uuid, repeat('3', 64), 'dat', 'Hoàng Văn Bình'),
    ('b3000000-0000-4000-8000-000000000005'::uuid, 'b2000000-0000-4000-8000-000000000002'::uuid, 'mep', 'MEP-02 Sơ đồ cấp điện sửa', 'b1000000-0000-4000-8000-000000000002'::uuid, repeat('2', 64), 'dat', 'Hoàng Văn Bình')
) AS v(id, phien_ban_id, bo_mon, ten, file_id, sha, trang_thai, nguoi)
WHERE h.ma_ho_so = 'CP-HERO-2026-001';

INSERT INTO app_cap_phep.nhan_xet_tham_dinh
    (id, tenant, ban_ve_id, phien_ban_id, bo_mon, nguoi_sub, nguoi, noi_dung, muc_do,
     trang_thai, created_at)
VALUES
    ('b4000000-0000-4000-8000-000000000001', 'phuong-a',
     'b3000000-0000-4000-8000-000000000002', 'b2000000-0000-4000-8000-000000000001',
     'mep',
     (SELECT id::text FROM core.users_directory WHERE tenant = 'phuong-a' AND username = 'td.binh'),
     'Hoàng Văn Bình', 'Bổ sung sơ đồ cấp điện và ghi rõ công suất phụ tải.', 'loi', 'mo',
     now() - interval '2 days');

-- 5. Thông báo mẫu cho chuông B-UX-04.
DELETE FROM core.notifications
WHERE tenant = 'phuong-a'
  AND title IN ('Có nhận xét thẩm định mới', 'Hồ sơ CP-HERO-2026-001 đã được thẩm định');
INSERT INTO core.notifications (tenant, user_sub, title, body, link)
SELECT 'phuong-a', u.id, 'Có nhận xét thẩm định mới',
       'Hồ sơ CP-HERO-2026-001 có nhận xét mức lỗi ở bộ môn MEP.', '/?tab=ban-lam-viec'
FROM core.users_directory u
WHERE u.tenant = 'phuong-a' AND u.username = 'cdt.minh';
INSERT INTO core.notifications (tenant, user_sub, title, body, link)
SELECT 'phuong-a', u.id, 'Hồ sơ CP-HERO-2026-001 đã được thẩm định',
       'Phiên bản thiết kế v2 đã đủ bộ môn bắt buộc và đạt.', '/?tab=ban-lam-viec'
FROM core.users_directory u
WHERE u.tenant = 'phuong-a' AND u.username = 'td.binh';

COMMIT;
"""


HERO_MA = "CP-HERO-2026-001"
HERO_TENANT = "phuong-a"
THAM_DINH_VIEN = "td.binh"


def doc_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


class Flowable:
    """Client REST tối giản (thư viện chuẩn) tới Flowable của stack."""

    def __init__(self, url: str, user: str, password: str) -> None:
        self.url = url.rstrip("/")
        self.auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()

    def goi(self, method: str, path: str, body: Optional[dict] = None) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method)
        req.add_header("Authorization", self.auth)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                raw = res.read()
                return res.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            return e.code, None

    def viec_dang_mo(self, proc_id: str) -> list[dict]:
        code, data = self.goi("GET", f"/service/runtime/tasks?processInstanceId={proc_id}")
        return (data or {}).get("data", []) if code == 200 else []

    def hoan_thanh(self, task_id: str, bien: dict[str, Any]) -> None:
        code, _ = self.goi(
            "POST",
            f"/service/runtime/tasks/{task_id}",
            {"action": "complete", "variables": [{"name": k, "value": v} for k, v in bien.items()]},
        )
        if code not in (200, 204):
            raise RuntimeError(f"Flowable không hoàn thành được việc {task_id} (HTTP {code})")


def psql_gia_tri(base_cmd: list[str], sql: str) -> str:
    res = subprocess.run(base_cmd + ["-tA", "-c", sql], capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(res.stderr or res.stdout)
    return res.stdout.strip()


def dong_bo_buoc(base_cmd: list[str], proc_id: str, buoc: str, bien: dict[str, Any]) -> None:
    """Chạy hàm đồng bộ của app như dịch vụ flow làm khi hoàn thành việc (trạng thái, phân công, thông báo)."""
    payload = json.dumps(bien, ensure_ascii=False).replace("'", "''")
    psql_gia_tri(
        base_cmd,
        f"SELECT app_cap_phep_private.sync_flow_state('{proc_id}', '{buoc}', '{payload}'::jsonb)",
    )


def da_phan_cong(base_cmd: list[str], ho_so_id: str, td_sub: str) -> bool:
    return psql_gia_tri(
        base_cmd,
        "SELECT count(*) FROM core.assignments WHERE object_type = 'ho_so' AND active "
        f"AND object_id = '{ho_so_id}' AND user_sub = '{td_sub}' AND role = 'tham-dinh'",
    ) not in ("", "0")


def gan_quy_trinh_hero(base_cmd: list[str]) -> str:
    """Đưa hồ sơ hero vào bước taskThamDinh giao td.binh; trả về thông điệp kết quả."""
    env = doc_env(ROOT / ".env")
    password = os.environ.get("FLOWABLE_PASSWORD") or env.get("FLOWABLE_PASSWORD")
    if not password:
        return "[CẢNH BÁO] Thiếu FLOWABLE_PASSWORD: hồ sơ hero chưa có việc thẩm định trong Bàn làm việc."
    fl = Flowable(
        os.environ.get("FLOWABLE_HOST_URL", "http://localhost:8082/flowable-rest"),
        os.environ.get("FLOWABLE_USER") or env.get("FLOWABLE_USER") or "rest-admin",
        password,
    )

    dong = psql_gia_tri(
        base_cmd,
        "SELECT h.id || '|' || COALESCE(h.process_instance_id, '') || '|' || COALESCE(h.chu_dau_tu_sub, '') "
        "|| '|' || COALESCE((SELECT u.id::text FROM core.users_directory u "
        f"WHERE u.tenant = '{HERO_TENANT}' AND u.username = '{THAM_DINH_VIEN}'), '') "
        f"FROM app_cap_phep.ho_so h WHERE h.ma_ho_so = '{HERO_MA}'",
    )
    if not dong:
        return f"[CẢNH BÁO] Không thấy {HERO_MA} sau khi nạp."
    ho_so_id, proc_cu, cdt_sub, td_sub = dong.split("|")
    if not td_sub:
        return f"[CẢNH BÁO] Chưa có {THAM_DINH_VIEN} trong danh bạ phường: chạy lại sau khi đồng bộ người dùng."

    try:
        if proc_cu:
            viec = fl.viec_dang_mo(proc_cu)
            if any(v.get("taskDefinitionKey") == "taskThamDinh" for v in viec):
                if not da_phan_cong(base_cmd, ho_so_id, td_sub):
                    # Bản seed trước FIX-V11-10 không chạy đồng bộ nên thiếu phân công
                    dong_bo_buoc(base_cmd, proc_cu, "taskPhanCong", {"ma_ho_so": HERO_MA, "ho_so_id": ho_so_id, "nguoiThamDinh": td_sub})
                    return f"[PASS] {HERO_MA} đã có việc thẩm định; bổ sung phân công {THAM_DINH_VIEN}."
                return f"[PASS] {HERO_MA} đã có việc thẩm định của {THAM_DINH_VIEN}."
            # Quy trình cũ đã đi tiếp (sau một lần demo): bỏ để làm lại từ bước thẩm định
            fl.goi("DELETE", f"/service/runtime/process-instances/{proc_cu}?deleteReason=seed_hero")

        code, data = fl.goi("POST", "/service/runtime/process-instances", {
            "processDefinitionKey": "cap-phep",
            "businessKey": HERO_MA,
            "tenantId": HERO_TENANT,
            "variables": [
                {"name": "ma_ho_so", "value": HERO_MA},
                {"name": "ho_so_id", "value": ho_so_id},
                {"name": "tenant", "value": HERO_TENANT},
                {"name": "chu_dau_tu_sub", "value": cdt_sub},
                {"name": "dia_chi_cong_trinh", "value": "Số 18 Đường Hòa Bình, phường A"},
                {"name": "dien_tich_san_m2", "value": 600.0},
                {"name": "khu_quan_ly_kien_truc", "value": False},
            ],
        })
        if code not in (200, 201) or not data:
            return f"[CẢNH BÁO] Flowable không mở được quy trình cho {HERO_MA} (HTTP {code})."
        proc_id = data["id"]

        for buoc, bien in (
            ("taskKiemTraHopLe", {"hoSoHopLe": True}),
            ("taskPhanCong", {"nguoiThamDinh": td_sub}),
        ):
            viec = [v for v in fl.viec_dang_mo(proc_id) if v.get("taskDefinitionKey") == buoc]
            if not viec:
                return f"[CẢNH BÁO] Quy trình {proc_id} không dừng ở {buoc} như mong đợi."
            fl.hoan_thanh(viec[0]["id"], bien)

        if not any(v.get("taskDefinitionKey") == "taskThamDinh" for v in fl.viec_dang_mo(proc_id)):
            return f"[CẢNH BÁO] Quy trình {proc_id} chưa tới bước thẩm định."
        psql_gia_tri(
            base_cmd,
            f"UPDATE app_cap_phep.ho_so SET process_instance_id = '{proc_id}' WHERE ma_ho_so = '{HERO_MA}'",
        )
        goc = {"ma_ho_so": HERO_MA, "ho_so_id": ho_so_id}
        dong_bo_buoc(base_cmd, proc_id, "taskKiemTraHopLe", {**goc, "hoSoHopLe": True})
        dong_bo_buoc(base_cmd, proc_id, "taskPhanCong", {**goc, "nguoiThamDinh": td_sub})
    except (urllib.error.URLError, OSError, RuntimeError) as e:
        return f"[CẢNH BÁO] Không gắn được quy trình cho {HERO_MA}: {e}"
    return f"[PASS] {HERO_MA} ở bước thẩm định, giao {THAM_DINH_VIEN}."


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Nạp hồ sơ hero Track A")
    parser.add_argument("--no-docker", action="store_true")
    parser.add_argument("--psql")
    parser.add_argument("--container", default="dxos-postgres")
    parser.add_argument("--user", default="dxos_owner")
    parser.add_argument("--database", default="dxos")
    parser.add_argument("--khong-quy-trinh", action="store_true", help="Chỉ nạp dữ liệu, không mở quy trình Flowable")
    args = parser.parse_args(argv)

    if args.no_docker:
        psql = args.psql or shutil.which("psql")
        if not psql:
            raise SystemExit("Không tìm thấy psql.")
        base_cmd = [psql, "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1"]
    else:
        base_cmd = ["docker", "exec", "-i", args.container, "psql", "-U", args.user, "-d", args.database, "-v", "ON_ERROR_STOP=1"]
    cmd = base_cmd + ["-f", "-"]

    res = subprocess.run(cmd, input=SQL, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        loi = res.stderr or res.stdout
        print(loi, file=sys.stderr)
        if "does not exist" in loi:
            print(
                "[GỢI Ý] CSDL chưa có migration của app cap-phep. Chạy `.\\dx.ps1 app-install` "
                "(hoặc `.\\dx.ps1 up`, gồm build lại image và cài app) rồi chạy lại.",
                file=sys.stderr,
            )
        return 1
    print("[PASS] Đã nạp hồ sơ hero: CP-HERO-2026-001 (5 tầng) và CP-HERO-ACC-2026-001 (nghiệm thu).")
    if not args.khong_quy_trinh:
        print(gan_quy_trinh_hero(base_cmd))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Đo mốc (baseline) H và D trên stack đang chạy, trước khi làm kế hoạch D & H (D-P0-02).

Chỉ đọc (trừ khi có --save: ghi chỉ số H vào core.h_baseline làm mốc cho API chỉ số), chỉ in số đếm và tỷ lệ: không in CCCD, họ tên, điện thoại hay mã hồ sơ.

H — thao tác của người:
- thao tác thủ công trên mỗi hồ sơ: dòng audit `actor_type = 'user'` gắn với hồ sơ;
- lần chuyển tay: số lần người sửa hồ sơ đổi sang người khác (theo `ho_so_lich_su`);
- làm lại: hồ sơ phải bổ sung và số vòng bổ sung;
- tự phục vụ: phần thao tác do chính chủ đầu tư làm;
- thời gian xử lý: dùng lại `scripts/impact_metrics.py`;
- trích xuất tự động: chưa có OCR thì là 0.

D — chất lượng dữ liệu hồ sơ:
- thiếu hoặc sai dạng: CCCD, điện thoại, mã định danh địa điểm, thửa đất;
- trùng: một CCCD gắn với nhiều họ tên khác nhau; cùng CCCD nộp trùng thửa đất;
- phả hệ: số job có sự kiện lineage.

Thao tác trên task Flowable (`flow.task_completed`) chưa gắn được với hồ sơ (audit chỉ có task_id),
nên chỉ đếm tổng và ghi rõ; D-MET-00 sẽ bổ sung.

Chạy:
    python scripts/dh_baseline.py                       # phường A, qua docker exec dxos-postgres
    python scripts/dh_baseline.py --tenant phuong-b --json
    python scripts/dh_baseline.py --markdown > docs/data/baseline-v1.1.md
"""

import argparse
import importlib.util
import json
import shutil
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("impact_metrics", ROOT / "scripts" / "impact_metrics.py")
im = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(im)

BANG_TUY_CHON = ("app_cap_phep.ocr_extractions", "core.mdm_subject")

SQL_BANG = "SELECT json_object_agg(t, to_regclass(t) IS NOT NULL) FROM unnest(ARRAY[{ds}]) AS t;"


def sql_baseline(co_bang: Dict[str, bool]) -> str:
    """Một câu truy vấn chỉ đọc, trả JSON số đếm theo phường (không có dữ liệu định danh)."""
    ocr = (
        "(SELECT count(*) FROM app_cap_phep.ocr_extractions WHERE tenant = :'tenant')"
        if co_bang.get("app_cap_phep.ocr_extractions") else "0"
    )
    mdm = (
        "(SELECT count(*) FROM core.mdm_subject WHERE tenant = :'tenant')"
        if co_bang.get("core.mdm_subject") else "0"
    )
    return f"""
WITH hs AS (SELECT * FROM app_cap_phep.ho_so WHERE tenant = :'tenant'),
tt AS (
    SELECT a.object_id, a.actor_sub, a.action
    FROM core.audit_log a
    WHERE a.tenant = :'tenant' AND a.actor_type = 'user' AND a.actor_sub IS NOT NULL
      AND a.object_type = 'ho_so'
),
tt_hs AS (
    SELECT h.id, count(t.object_id) AS n
    FROM hs h LEFT JOIN tt t ON t.object_id = h.id::text
    GROUP BY h.id
),
ls AS (
    SELECT l.ho_so_id, l.changed_by,
           lag(l.changed_by) OVER (PARTITION BY l.ho_so_id ORDER BY l.changed_at, l.id) AS truoc
    FROM app_cap_phep.ho_so_lich_su l JOIN hs ON hs.id = l.ho_so_id
    WHERE l.changed_by IS NOT NULL
),
chuyen AS (
    SELECT h.id, count(*) FILTER (WHERE ls.truoc IS NOT NULL AND ls.truoc <> ls.changed_by) AS n
    FROM hs h LEFT JOIN ls ON ls.ho_so_id = h.id
    GROUP BY h.id
),
bs AS (
    SELECT object_id, count(*) AS n FROM tt WHERE action = 'ho_so.bo_sung' GROUP BY object_id
),
cccd AS (
    SELECT cccd, count(DISTINCT lower(btrim(ho_ten))) AS so_ten FROM hs GROUP BY cccd
)
SELECT json_build_object(
    'tong_ho_so', (SELECT count(*) FROM hs),
    'thao_tac_moi_ho_so', (SELECT coalesce(json_agg(n ORDER BY n), '[]'::json) FROM tt_hs),
    'chuyen_tay_moi_ho_so', (SELECT coalesce(json_agg(n ORDER BY n), '[]'::json) FROM chuyen),
    'thao_tac_chu_dau_tu', (SELECT count(*) FROM tt JOIN hs ON hs.id::text = tt.object_id
                             WHERE tt.actor_sub = hs.chu_dau_tu_sub),
    'thao_tac_nguoi_dung', (SELECT count(*) FROM tt JOIN hs ON hs.id::text = tt.object_id),
    'task_hoan_thanh', (SELECT count(*) FROM core.audit_log WHERE tenant = :'tenant'
                        AND action = 'flow.task_completed' AND actor_type = 'user'),
    'ho_so_phai_bo_sung', (SELECT count(*) FROM bs),
    'vong_bo_sung', (SELECT coalesce(sum(n), 0) FROM bs),
    'ocr_trich_xuat', {ocr},
    'cccd_sai_dang', (SELECT count(*) FROM hs WHERE cccd !~ '^[0-9]{{12}}$'),
    'dien_thoai_sai_dang', (SELECT count(*) FROM hs WHERE regexp_replace(dien_thoai, '[ .-]', '', 'g') !~ '^(0|\\+84)[0-9]{{9}}$'),
    'thieu_ma_dia_diem', (SELECT count(*) FROM hs WHERE ma_dinh_danh_dia_diem IS NULL),
    'thieu_thua_dat', (SELECT count(*) FROM hs WHERE btrim(coalesce(thua_dat, '')) = ''),
    'cccd_nhieu_ten', (SELECT count(*) FROM cccd WHERE so_ten > 1),
    'ho_so_trung_cccd_thua', (SELECT coalesce(sum(n - 1), 0) FROM (
        SELECT count(*) AS n FROM hs GROUP BY cccd, lower(btrim(thua_dat)) HAVING count(*) > 1) x),
    'job_lineage', (SELECT count(DISTINCT job) FROM core.lineage_events),
    'mdm_subject', {mdm}
);
"""


def _pct(a: Optional[int], b: int) -> Optional[float]:
    if a is None or not b:
        return None
    return round(100.0 * a / b, 1)


def _tb(ds: List[int]) -> Optional[float]:
    return round(statistics.mean(ds), 2) if ds else None


def _trung_vi(ds: List[int]) -> Optional[float]:
    return float(statistics.median(ds)) if ds else None


def tinh(raw: Dict[str, Any], tac_dong: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Từ số đếm thô ra chỉ số mốc (hàm thuần, test được)."""
    tong = int(raw.get("tong_ho_so") or 0)
    tt = [int(x) for x in raw.get("thao_tac_moi_ho_so") or []]
    ct = [int(x) for x in raw.get("chuyen_tay_moi_ho_so") or []]
    nguoi = int(raw.get("thao_tac_nguoi_dung") or 0)
    d = (tac_dong or {}).get("do_duoc", {})

    def so(k: str) -> int:
        return int(raw.get(k) or 0)

    return {
        "h": {
            "tong_ho_so": tong,
            "thao_tac_thu_cong_tb": _tb(tt),
            "thao_tac_thu_cong_trung_vi": _trung_vi(tt),
            "chuyen_tay_tb": _tb(ct),
            "ty_le_ho_so_phai_bo_sung_pct": _pct(so("ho_so_phai_bo_sung"), tong),
            "vong_bo_sung_tb_tren_ho_so_bo_sung": (
                round(so("vong_bo_sung") / so("ho_so_phai_bo_sung"), 2) if so("ho_so_phai_bo_sung") else None
            ),
            "ty_le_tu_phuc_vu_pct": _pct(so("thao_tac_chu_dau_tu"), nguoi),
            "task_hoan_thanh_chua_gan_ho_so": so("task_hoan_thanh"),
            "trich_xuat_tu_dong": so("ocr_trich_xuat"),
            "thoi_gian_xu_ly_tb_ngay_lam_viec": d.get("thoi_gian_xu_ly_tb_ngay_lam_viec"),
            "ty_le_ky_dung_han_pct": d.get("ty_le_ky_dung_han_pct"),
        },
        "d": {
            "cccd_sai_dang_pct": _pct(so("cccd_sai_dang"), tong),
            "dien_thoai_sai_dang_pct": _pct(so("dien_thoai_sai_dang"), tong),
            "thieu_ma_dinh_danh_dia_diem_pct": _pct(so("thieu_ma_dia_diem"), tong),
            "thieu_thua_dat_pct": _pct(so("thieu_thua_dat"), tong),
            "cccd_gan_nhieu_ho_ten": so("cccd_nhieu_ten"),
            "ho_so_trung_cccd_va_thua_dat": so("ho_so_trung_cccd_thua"),
            "ty_le_trung_pct": _pct(so("ho_so_trung_cccd_thua"), tong),
            "so_job_co_lineage": so("job_lineage"),
            "ban_ghi_mdm": so("mdm_subject"),
        },
    }


NHAN_H = [
    ("tong_ho_so", "Hồ sơ trong phường", ""),
    ("thao_tac_thu_cong_tb", "Thao tác thủ công / hồ sơ (TB)", ""),
    ("thao_tac_thu_cong_trung_vi", "Thao tác thủ công / hồ sơ (trung vị)", ""),
    ("chuyen_tay_tb", "Lần chuyển tay / hồ sơ (TB)", ""),
    ("ty_le_ho_so_phai_bo_sung_pct", "Hồ sơ phải bổ sung", "%"),
    ("vong_bo_sung_tb_tren_ho_so_bo_sung", "Vòng bổ sung / hồ sơ phải bổ sung", ""),
    ("ty_le_tu_phuc_vu_pct", "Thao tác do chủ đầu tư tự làm", "%"),
    ("task_hoan_thanh_chua_gan_ho_so", "Task Flowable hoàn thành (chưa gắn hồ sơ)", ""),
    ("trich_xuat_tu_dong", "Trích xuất tự động (OCR)", ""),
    ("thoi_gian_xu_ly_tb_ngay_lam_viec", "Thời gian nộp → ký (TB)", " ngày làm việc"),
    ("ty_le_ky_dung_han_pct", "Ký đúng hạn", "%"),
]
NHAN_D = [
    ("cccd_sai_dang_pct", "CCCD sai dạng 12 số", "%"),
    ("dien_thoai_sai_dang_pct", "Điện thoại sai dạng", "%"),
    ("thieu_ma_dinh_danh_dia_diem_pct", "Thiếu mã định danh địa điểm", "%"),
    ("thieu_thua_dat_pct", "Thiếu thửa đất", "%"),
    ("cccd_gan_nhieu_ho_ten", "CCCD gắn với nhiều họ tên", ""),
    ("ho_so_trung_cccd_va_thua_dat", "Hồ sơ trùng CCCD + thửa đất", ""),
    ("ty_le_trung_pct", "Tỷ lệ trùng", "%"),
    ("so_job_co_lineage", "Job có sự kiện lineage", ""),
    ("ban_ghi_mdm", "Bản ghi MDM", ""),
]


def _v(v: Any, dv: str) -> str:
    return "chưa có dữ liệu" if v is None else f"{v}{dv}"


def in_bang(tenant: str, kq: Dict[str, Any]) -> None:
    print(f"MỐC ĐO D & H: {tenant} (đo lúc {date.today().isoformat()}, dữ liệu demo tổng hợp)")
    for ten, khoa, nhan in (("H — THAO TÁC CỦA NGƯỜI", "h", NHAN_H), ("D — CHẤT LƯỢNG DỮ LIỆU", "d", NHAN_D)):
        print()
        print(ten)
        for k, t, dv in nhan:
            print(f"  {t} {'.' * max(2, 46 - len(t))} {_v(kq[khoa][k], dv)}")


def in_markdown(tenant: str, phien_ban: str, kq: Dict[str, Any]) -> None:
    print("<!--\nSPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors\nSPDX-License-Identifier: CC-BY-4.0\n-->\n")
    print(f"# Mốc đo D & H trên {phien_ban}\n")
    print(f"Đo bằng `python scripts/dh_baseline.py --tenant {tenant}` ngày {date.today().isoformat()}, "
          "trên dữ liệu demo tổng hợp (không phải số của một phường thật). Kế hoạch: "
          "[ke-hoach-dh.md](ke-hoach-dh.md), mục 10.\n")
    for ten, khoa, nhan in (("H — thao tác của người", "h", NHAN_H), ("D — chất lượng dữ liệu hồ sơ", "d", NHAN_D)):
        print(f"## {ten}\n")
        print("| Chỉ số | Mốc |\n| :--- | ---: |")
        for k, t, dv in nhan:
            print(f"| {t} | {_v(kq[khoa][k], dv)} |")
        print()
    print("## Giới hạn\n")
    print("- Thao tác trên task Flowable chưa gắn được với hồ sơ (audit chỉ có `task_id`); D-MET-00 bổ sung "
          "`ho_so_id` rồi đo lại.")
    print("- Chuyển tay đếm theo người sửa liên tiếp trong `ho_so_lich_su`; cập nhật do dịch vụ (không có `sub`) không tính.")


def _psql_cmd(a: argparse.Namespace) -> List[str]:
    if a.no_docker:
        psql = a.psql or shutil.which("psql")
        if not psql:
            raise SystemExit("Không tìm thấy psql.")
        return [psql, "-U", a.user, "-d", a.database]
    return ["docker", "exec", "-i", a.container, "psql", "-U", a.user, "-d", a.database]


SQL_LUU_MOC = """
INSERT INTO core.h_baseline (tenant, label, metrics) VALUES (:'tenant', :'nhan', :'du_lieu'::jsonb)
ON CONFLICT (tenant, label) DO UPDATE SET metrics = EXCLUDED.metrics, measured_at = now()
RETURNING json_build_object('label', label);
"""


def luu_moc(cmd_goc: List[str], tenant: str, nhan: str, h: Dict[str, Any]) -> None:
    """Ghi chỉ số H (chỉ số đếm, không dữ liệu định danh) làm mốc; chạy lại cùng nhãn thì ghi đè."""
    cmd = cmd_goc + ["-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-v", f"tenant={tenant}", "-v", f"nhan={nhan}",
                     "-v", "du_lieu=" + json.dumps(h, ensure_ascii=False), "-f", "-"]
    res = subprocess.run(cmd, input=SQL_LUU_MOC, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise SystemExit(f"Lỗi lưu mốc: {(res.stderr or res.stdout).strip()}")


def _git_mo_ta() -> str:
    try:
        r = subprocess.run(["git", "describe", "--tags", "--always"], cwd=ROOT, capture_output=True, text=True)
        return r.stdout.strip() or "không rõ"
    except OSError:
        return "không rõ"


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Đo mốc D & H từ stack DX-OS C3 (chỉ đọc)")
    p.add_argument("--tenant", default="phuong-a")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true", help="In JSON")
    g.add_argument("--markdown", action="store_true", help="In trang markdown cho docs/data/baseline-*.md")
    p.add_argument("--phien-ban", help="Ghi vào tiêu đề markdown; mặc định lấy từ git describe")
    p.add_argument("--no-docker", action="store_true", help="Gọi psql trên máy thay vì docker exec")
    p.add_argument("--psql")
    p.add_argument("--container", default="dxos-postgres")
    p.add_argument("--user", default="dxos_owner")
    p.add_argument("--database", default="dxos")
    p.add_argument("--save", metavar="NHAN",
                   help="Lưu chỉ số H làm mốc vào core.h_baseline với nhãn này (ví dụ v1.1); API /automation/metrics so với mốc")
    a = p.parse_args(argv)

    cmd = _psql_cmd(a)
    co_bang = im._psql(SQL_BANG.format(ds=", ".join(f"'{t}'" for t in BANG_TUY_CHON)), a.tenant, cmd)
    raw = im._psql(sql_baseline(co_bang), a.tenant, cmd)
    kq = tinh(raw, im.tinh(im.chay_sql(a.tenant, cmd)))

    if a.save:
        luu_moc(cmd, a.tenant, a.save, kq["h"])
        print(f"Đã lưu mốc '{a.save}' của {a.tenant} vào core.h_baseline", file=sys.stderr)
    if a.json:
        print(json.dumps({"tenant": a.tenant, "ngay_do": date.today().isoformat(), **kq}, ensure_ascii=False, indent=2))
    elif a.markdown:
        in_markdown(a.tenant, a.phien_ban or _git_mo_ta(), kq)
    else:
        in_bang(a.tenant, kq)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

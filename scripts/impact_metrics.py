#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Chỉ số tác động cho slide 9 (B-DEMO-04), tính từ dữ liệu của stack đang chạy.

Phần ĐO ĐƯỢC lấy thẳng từ PostgreSQL:
- thời gian xử lý (ngày làm việc từ lúc nộp đến lúc ký giấy phép), tỷ lệ đúng hạn;
- số lần kiểm tra tự động (quy hoạch, quét virus, đánh giá bản vẽ, ký số, nghiệm thu);
- số hồ sơ phát hiện lỗi sớm (quy hoạch không đạt, phải bổ sung) và số vòng sửa thiết kế.
Phần GIẢ ĐỊNH (giấy tờ giảm, mức hài lòng) in riêng, ghi rõ cách giả định.

Dữ liệu demo là dữ liệu tổng hợp: số in ra mô tả hệ thống trên bộ dữ liệu đó, không phải số đo
tại một phường thật.

Chạy:
    python scripts/impact_metrics.py                      # phường A, qua docker exec dxos-postgres
    python scripts/impact_metrics.py --tenant phuong-b --json
    python scripts/impact_metrics.py --no-docker --psql "C:\\...\\psql.exe"
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Điều 54 NĐ 217/2026/NĐ-CP: cấp GPXD mới nhà ở riêng lẻ trong 07 ngày làm việc
THOI_HAN_LUAT_NGAY_LAM_VIEC = 7
# Thành phần bắt buộc theo Điều 60 (apps/cap-phep/app.yaml, documents bat_buoc)
SO_THANH_PHAN_BAT_BUOC = 6

SQL = r"""
WITH hs AS (
    SELECT * FROM app_cap_phep.ho_so WHERE tenant = :'tenant'
),
cap AS (
    SELECT h.id, h.created_at, h.han_tong_at, g.ngay_cap
    FROM hs h JOIN app_cap_phep.giay_phep g ON g.ho_so_id = h.id
),
dong AS (
    SELECT id, qua_han FROM hs WHERE trang_thai IN ('DA_CAP', 'TU_CHOI')
)
SELECT json_build_object(
    'tong_ho_so', (SELECT count(*) FROM hs),
    'da_dong', (SELECT count(*) FROM dong),
    'dong_dung_han', (SELECT count(*) FROM dong WHERE NOT qua_han),
    'cap_phep', (SELECT coalesce(json_agg(json_build_object(
        'nop', created_at, 'han', han_tong_at, 'cap', ngay_cap)), '[]'::json) FROM cap),
    'kiem_tra_quy_hoach', (SELECT count(*) FROM app_construction.ket_qua_kiem_tra_quy_hoach WHERE tenant = :'tenant'),
    'quy_hoach_khong_dat', (SELECT count(*) FROM app_construction.ket_qua_kiem_tra_quy_hoach WHERE tenant = :'tenant' AND NOT pass),
    'ho_so_quy_hoach_khong_dat', (SELECT count(DISTINCT ho_so_id) FROM app_construction.ket_qua_kiem_tra_quy_hoach
                                  WHERE tenant = :'tenant' AND NOT pass AND ho_so_id IS NOT NULL),
    'tep_quet_virus', (SELECT count(*) FROM core.files WHERE tenant = :'tenant' AND status IN ('clean', 'infected')),
    'tep_nhiem_virus', (SELECT count(*) FROM core.files WHERE tenant = :'tenant' AND status = 'infected'),
    'ban_ve_da_danh_gia', (SELECT count(*) FROM app_cap_phep.ban_ve WHERE tenant = :'tenant' AND trang_thai IN ('dat', 'khong_dat')),
    'van_ban_ky_so', (SELECT count(*) FROM core.signed_docs WHERE tenant = :'tenant'),
    'moc_nghiem_thu', (SELECT count(*) FROM app_construction.moc_nghiem_thu WHERE tenant = :'tenant' AND ket_qua IN ('dat', 'khong_dat')),
    'nghiem_thu_khong_dat', (SELECT count(*) FROM app_construction.moc_nghiem_thu WHERE tenant = :'tenant' AND ket_qua = 'khong_dat'),
    'ho_so_tung_bo_sung', (SELECT count(DISTINCT l.ho_so_id) FROM app_cap_phep.ho_so_lich_su l
                           JOIN hs ON hs.id = l.ho_so_id WHERE l.snapshot->>'trang_thai' = 'CAN_BO_SUNG'),
    'ho_so_co_thiet_ke', (SELECT count(DISTINCT ho_so_id) FROM app_cap_phep.phien_ban_thiet_ke WHERE tenant = :'tenant'),
    'so_phien_ban_tb', (SELECT round(avg(n)::numeric, 2) FROM (
        SELECT max(so_phien_ban) AS n FROM app_cap_phep.phien_ban_thiet_ke WHERE tenant = :'tenant' GROUP BY ho_so_id) x)
);
"""


GIO_VN = timezone(timedelta(hours=7))


def ngay_lam_viec(tu: datetime, den: datetime) -> int:
    """Số ngày làm việc (thứ Hai đến thứ Sáu, theo giờ Việt Nam) sau ngày nộp đến hết ngày ký; không trừ ngày lễ."""
    a, b = tu.astimezone(GIO_VN).date(), den.astimezone(GIO_VN).date()
    if b <= a:
        return 0
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def _iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def tinh(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Từ số liệu thô của CSDL ra các chỉ số in trên slide (hàm thuần, test được)."""
    cap: List[Dict[str, Any]] = raw.get("cap_phep") or []
    so_ngay = [ngay_lam_viec(_iso(c["nop"]), _iso(c["cap"])) for c in cap if c.get("nop") and c.get("cap")]
    dung_han_ky = [c for c in cap if c.get("han") and c.get("cap") and _iso(c["cap"]) <= _iso(c["han"])]
    da_dong = int(raw.get("da_dong") or 0)

    def pct(a: int, b: int) -> Optional[float]:
        return round(100.0 * a / b, 1) if b else None

    kiem_tra_tu_dong = sum(int(raw.get(k) or 0) for k in (
        "kiem_tra_quy_hoach", "tep_quet_virus", "ban_ve_da_danh_gia", "van_ban_ky_so", "moc_nghiem_thu"))
    return {
        "do_duoc": {
            "tong_ho_so": int(raw.get("tong_ho_so") or 0),
            "giay_phep_da_ky": len(cap),
            "thoi_gian_xu_ly_tb_ngay_lam_viec": round(sum(so_ngay) / len(so_ngay), 1) if so_ngay else None,
            "thoi_gian_xu_ly_max_ngay_lam_viec": max(so_ngay) if so_ngay else None,
            "thoi_han_luat_ngay_lam_viec": THOI_HAN_LUAT_NGAY_LAM_VIEC,
            "ty_le_ky_dung_han_pct": pct(len(dung_han_ky), len(cap)),
            "ty_le_dong_dung_han_pct": pct(int(raw.get("dong_dung_han") or 0), da_dong),
            "ho_so_da_dong": da_dong,
            "so_kiem_tra_tu_dong": kiem_tra_tu_dong,
            "chi_tiet_kiem_tra": {
                "quy_hoach": int(raw.get("kiem_tra_quy_hoach") or 0),
                "quet_virus_tep": int(raw.get("tep_quet_virus") or 0),
                "danh_gia_ban_ve": int(raw.get("ban_ve_da_danh_gia") or 0),
                "ky_so": int(raw.get("van_ban_ky_so") or 0),
                "moc_nghiem_thu": int(raw.get("moc_nghiem_thu") or 0),
            },
            "ho_so_phat_hien_loi_quy_hoach_som": int(raw.get("ho_so_quy_hoach_khong_dat") or 0),
            "lan_kiem_tra_quy_hoach_khong_dat": int(raw.get("quy_hoach_khong_dat") or 0),
            "ho_so_phai_bo_sung": int(raw.get("ho_so_tung_bo_sung") or 0),
            "tep_bi_chan_vi_virus": int(raw.get("tep_nhiem_virus") or 0),
            "moc_nghiem_thu_khong_dat": int(raw.get("nghiem_thu_khong_dat") or 0),
            "ho_so_co_thiet_ke": int(raw.get("ho_so_co_thiet_ke") or 0),
            "so_vong_thiet_ke_tb": float(raw["so_phien_ban_tb"]) if raw.get("so_phien_ban_tb") is not None else None,
        },
        "gia_dinh": [
            {
                "chi_so": "Giấy tờ giảm",
                "gia_tri": f"{SO_THANH_PHAN_BAT_BUOC} tệp điện tử, nộp một lần",
                "cach_gia_dinh": (
                    "Giả định: trước đây mỗi thành phần nộp bản giấy kèm bản sao chứng thực và phải mang lại khi "
                    "thiếu; với C3 nộp 6 thành phần bắt buộc theo Điều 60 NĐ 217/2026 dưới dạng tệp, hệ thống báo "
                    "thiếu ngay khi nộp. Giấy tờ đất đã có trên CSDL quốc gia không phải nộp (Điều 56 khoản 3) khi "
                    "kết nối được CSDL đất đai, việc này chưa làm. Chưa đo tại phường thật."
                ),
            },
            {
                "chi_so": "Mức độ hài lòng",
                "gia_tri": "chưa đo",
                "cach_gia_dinh": (
                    "Không có số liệu. Đề xuất khảo sát 5 mức ngay sau khi người dân nhận kết quả; "
                    "không đưa con số hài lòng lên slide trước khi khảo sát."
                ),
            },
        ],
    }


def chay_sql(tenant: str, cmd_goc: List[str]) -> Dict[str, Any]:
    cmd = cmd_goc + ["-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-v", f"tenant={tenant}", "-f", "-"]
    res = subprocess.run(cmd, input=SQL, capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise SystemExit(f"Lỗi truy vấn: {(res.stderr or res.stdout).strip()}")
    dong = [x for x in res.stdout.splitlines() if x.strip().startswith("{")]
    if not dong:
        raise SystemExit("Không đọc được kết quả từ PostgreSQL.")
    return json.loads(dong[-1])


def _fmt(v: Any, don_vi: str = "") -> str:
    if v is None:
        return "chưa có dữ liệu"
    return f"{v}{don_vi}"


def in_bang(tenant: str, kq: Dict[str, Any]) -> None:
    d = kq["do_duoc"]
    ct = d["chi_tiet_kiem_tra"]
    print(f"CHỈ SỐ TÁC ĐỘNG: {tenant} (đo lúc {date.today().isoformat()}, dữ liệu demo tổng hợp)")
    print()
    print("ĐO TỪ HỆ THỐNG")
    print(f"  Hồ sơ trong hệ thống ................ {d['tong_ho_so']}")
    print(f"  Giấy phép đã ký số .................. {d['giay_phep_da_ky']}")
    print(f"  Thời gian nộp -> ký (TB / tối đa) ... {_fmt(d['thoi_gian_xu_ly_tb_ngay_lam_viec'])} / "
          f"{_fmt(d['thoi_gian_xu_ly_max_ngay_lam_viec'])} ngày làm việc (luật: {d['thoi_han_luat_ngay_lam_viec']})")
    print(f"  Ký đúng hạn ......................... {_fmt(d['ty_le_ky_dung_han_pct'], '%')}")
    print(f"  Hồ sơ đã đóng đúng hạn .............. {_fmt(d['ty_le_dong_dung_han_pct'], '%')} trên {d['ho_so_da_dong']} hồ sơ")
    print(f"  Kiểm tra tự động .................... {d['so_kiem_tra_tu_dong']} lần "
          f"(quy hoạch {ct['quy_hoach']}, quét virus {ct['quet_virus_tep']}, bản vẽ {ct['danh_gia_ban_ve']}, "
          f"ký số {ct['ky_so']}, nghiệm thu {ct['moc_nghiem_thu']})")
    print(f"  Hồ sơ phát hiện sai quy hoạch sớm ... {d['ho_so_phat_hien_loi_quy_hoach_som']} "
          f"({d['lan_kiem_tra_quy_hoach_khong_dat']} lần kiểm tra không đạt)")
    print(f"  Hồ sơ phải bổ sung .................. {d['ho_so_phai_bo_sung']}")
    print(f"  Tệp bị chặn vì virus ................ {d['tep_bi_chan_vi_virus']}")
    print(f"  Mốc nghiệm thu không đạt ............ {d['moc_nghiem_thu_khong_dat']}")
    print(f"  Số vòng thiết kế trung bình ......... {_fmt(d['so_vong_thiet_ke_tb'])} trên {d['ho_so_co_thiet_ke']} hồ sơ")
    print()
    print("GIẢ ĐỊNH (không phải số đo)")
    for g in kq["gia_dinh"]:
        print(f"  {g['chi_so']}: {g['gia_tri']}")
        print(f"    {g['cach_gia_dinh']}")


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Chỉ số tác động đo từ stack DX-OS C3")
    p.add_argument("--tenant", default="phuong-a")
    p.add_argument("--json", action="store_true", help="In JSON thay cho bảng")
    p.add_argument("--no-docker", action="store_true", help="Gọi psql trên máy thay vì docker exec")
    p.add_argument("--psql")
    p.add_argument("--container", default="dxos-postgres")
    p.add_argument("--user", default="dxos_owner")
    p.add_argument("--database", default="dxos")
    a = p.parse_args(argv)

    if a.no_docker:
        psql = a.psql or shutil.which("psql")
        if not psql:
            raise SystemExit("Không tìm thấy psql.")
        cmd = [psql, "-U", a.user, "-d", a.database]
    else:
        cmd = ["docker", "exec", "-i", a.container, "psql", "-U", a.user, "-d", a.database]

    kq = tinh(chay_sql(a.tenant, cmd))
    if a.json:
        print(json.dumps({"tenant": a.tenant, "ngay_do": date.today().isoformat(), **kq}, ensure_ascii=False, indent=2))
    else:
        in_bang(a.tenant, kq)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

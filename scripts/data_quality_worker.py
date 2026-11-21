#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Chạy rule chất lượng dữ liệu (D-DQ-02) và ghi lần chạy, kết quả, vấn đề.

- Rule đọc từ core.data_quality_rules (khai báo ở core/postgres/22-data-quality.sql).
- Mỗi rule chạy trong giao dịch chỉ đọc riêng có statement_timeout: một rule lỗi (thiếu bảng, quá
  thời gian) chỉ tăng rule_errors, lần chạy vẫn tiếp tục.
- Vấn đề chỉ chứa entity_type, entity_id, field, dossier_id: không lưu giá trị của trường lỗi.
- Lần sau vẫn lỗi thì vấn đề đã đóng (resolved) mở lại; không còn lỗi thì vấn đề đang mở tự đóng.
  Vấn đề bị bỏ qua (ignored) giữ nguyên.
- In số đếm, không in dữ liệu cá nhân.

Chạy:
    docker compose --profile tools run --rm tools scripts/data_quality_worker.py
    python scripts/data_quality_worker.py --dry-run --domain ho_so
    python scripts/data_quality_worker.py --rule DQ-CD-01 --json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
THOI_GIAN_TOI_DA = os.getenv("DQ_RULE_TIMEOUT", "15s")
SO_MAU = 5
logger = logging.getLogger("dxos.dq_worker")


def _env(ten: str, mac_dinh: str = "") -> str:
    gia_tri = os.getenv(ten)
    if gia_tri:
        return gia_tri
    env_file = ROOT / ".env"
    if env_file.exists():
        for dong in env_file.read_text(encoding="utf-8").splitlines():
            if dong.startswith(ten + "="):
                return dong.split("=", 1)[1].strip()
    return mac_dinh


def dsn_mac_dinh() -> str:
    return "postgresql://{u}:{p}@{h}:{port}/{db}".format(
        u=_env("DB_USER", "dxos_svc"), p=_env("DB_PASSWORD"), h=_env("POSTGRES_HOST", "postgres"),
        port=_env("POSTGRES_PORT", "5432"), db=_env("POSTGRES_DB", "dxos"),
    )


def tong_hop(tong: Dict[str, int], loi: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Gộp số kiểm và bản ghi lỗi theo phường → total, failed, score, sample_ids (hàm thuần)."""
    kq: Dict[str, Dict[str, Any]] = {}
    for tenant, n in tong.items():
        kq[tenant] = {"total": int(n), "failed": 0, "sample_ids": []}
    for r in loi:
        d = kq.setdefault(r["tenant"], {"total": 0, "failed": 0, "sample_ids": []})
        d["failed"] += 1
        if len(d["sample_ids"]) < SO_MAU:
            d["sample_ids"].append(r["entity_id"])
    for d in kq.values():
        d["total"] = max(d["total"], d["failed"])
        d["score"] = round(100.0 * (d["total"] - d["failed"]) / d["total"], 2) if d["total"] else 100.0
    return kq


def trang_thai_lan_chay(so_rule: int, so_loi_rule: int) -> str:
    if so_rule and so_loi_rule == so_rule:
        return "failed"
    return "partial" if so_loi_rule else "succeeded"


async def chay_rule(conn, rule) -> Optional[Dict[str, Any]]:
    """Hai câu SELECT của rule trong giao dịch chỉ đọc; lỗi thì None."""
    try:
        async with conn.transaction(readonly=True):
            await conn.execute(f"SET LOCAL statement_timeout = '{THOI_GIAN_TOI_DA}'")
            tong = {r[0]: r[1] for r in await conn.fetch(rule["sql_total"])}
            loi = [{"tenant": r[0], "entity_id": str(r[1]), "field": r[2], "dossier_id": r[3]}
                   for r in await conn.fetch(rule["sql_fail"])]
        return {"tong": tong, "loi": loi}
    except Exception as exc:
        print(f"  [LOI] {rule['code']}: {type(exc).__name__}", file=sys.stderr)
        return None


async def ghi_ket_qua(conn, run_id, rule, kq: Dict[str, Any]) -> Dict[str, int]:
    dem = {"moi": 0, "tu_dong": 0}
    theo_phuong = tong_hop(kq["tong"], kq["loi"])
    async with conn.transaction():
        for tenant, d in theo_phuong.items():
            await conn.execute(
                """
                INSERT INTO core.data_quality_results (run_id, tenant, rule_code, total, failed, score, sample_ids)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                """,
                run_id, tenant, rule["code"], d["total"], d["failed"], d["score"], json.dumps(d["sample_ids"]),
            )
        moi_theo_phuong: Dict[str, int] = {}
        for r in kq["loi"]:
            moi = await conn.fetchval(
                """
                INSERT INTO core.data_quality_issues (tenant, rule_code, entity_type, entity_id, field, dossier_id, severity, last_seen_run)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (tenant, rule_code, entity_id) DO UPDATE
                SET field = EXCLUDED.field, dossier_id = EXCLUDED.dossier_id, severity = EXCLUDED.severity,
                    last_seen_run = EXCLUDED.last_seen_run,
                    status = CASE WHEN core.data_quality_issues.status = 'resolved' THEN 'open' ELSE core.data_quality_issues.status END,
                    resolved_at = CASE WHEN core.data_quality_issues.status = 'resolved' THEN NULL ELSE core.data_quality_issues.resolved_at END
                RETURNING (xmax = 0)
                """,
                r["tenant"], rule["code"], rule["entity_type"], r["entity_id"], r["field"], r["dossier_id"],
                rule["severity"], run_id,
            )
            if moi:
                dem["moi"] += 1
                moi_theo_phuong[r["tenant"]] = moi_theo_phuong.get(r["tenant"], 0) + 1
        dong = await conn.execute(
            """
            UPDATE core.data_quality_issues
            SET status = 'resolved', resolved_at = now(), note = 'Tự đóng: lần chạy sau không còn lỗi'
            WHERE rule_code = $1 AND status IN ('open', 'in_progress') AND last_seen_run IS DISTINCT FROM $2
            """,
            rule["code"], run_id,
        )
        dem["tu_dong"] = int(dong.split()[-1]) if dong else 0
        for tenant, n in moi_theo_phuong.items():
            await conn.execute(
                "INSERT INTO core.outbox (tenant, topic, payload) VALUES ($1, 'dq.issue.created', $2::jsonb)",
                tenant, json.dumps({"rule_code": rule["code"], "so_van_de": n}),
            )
    return dem


async def chay(dsn: str, rule_code: Optional[str], domain: Optional[str], dry_run: bool, tac_gia: str) -> Dict[str, Any]:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        rules = await conn.fetch(
            """
            SELECT code, domain, severity, entity_type, sql_total, sql_fail FROM core.data_quality_rules
            WHERE enabled AND ($1::text IS NULL OR code = $1) AND ($2::text IS NULL OR domain = $2)
            ORDER BY code
            """,
            rule_code, domain,
        )
        run_id = None
        if not dry_run:
            run_id = await conn.fetchval(
                "INSERT INTO core.data_quality_runs (triggered_by) VALUES ($1) RETURNING id", tac_gia,
            )
        bao_cao: Dict[str, Any] = {"run_id": str(run_id) if run_id else None, "rules": [], "rule_errors": 0}
        for rule in rules:
            kq = await chay_rule(conn, rule)
            if kq is None:
                bao_cao["rule_errors"] += 1
                bao_cao["rules"].append({"code": rule["code"], "loi": True})
                continue
            muc = {"code": rule["code"], "total": sum(kq["tong"].values()), "failed": len(kq["loi"])}
            if not dry_run:
                muc |= await ghi_ket_qua(conn, run_id, rule, kq)
            bao_cao["rules"].append(muc)
        bao_cao["status"] = trang_thai_lan_chay(len(rules), bao_cao["rule_errors"])
        if run_id:
            await conn.execute(
                "UPDATE core.data_quality_runs SET finished_at = now(), status = $2, rule_errors = $3 WHERE id = $1",
                run_id, bao_cao["status"], bao_cao["rule_errors"],
            )
            await conn.execute(
                """
                INSERT INTO core.lineage_events (job, run_id, inputs, outputs, facets)
                VALUES ('dq.worker', $1, '[]'::jsonb, '[{"namespace": "core", "name": "data_quality_results"},
                        {"namespace": "core", "name": "data_quality_issues"}]'::jsonb, $2::jsonb)
                """,
                str(run_id), json.dumps({"so_rule": len(rules), "rule_errors": bao_cao["rule_errors"]}),
            )
        return bao_cao
    finally:
        await conn.close()


async def _chay_lap(args) -> int:
    """Chế độ dịch vụ nền (D-DQ-02): mỗi N giây chấm lại, lỗi một lượt chỉ ghi log, không thoát."""
    logger.info("Khởi động worker chất lượng dữ liệu nền (lặp mỗi %d giây)", args.lap_giay)
    while True:
        try:
            kq = await chay(
                args.dsn or dsn_mac_dinh(),
                args.rule,
                args.domain,
                args.dry_run,
                "data_quality_worker_cron",
            )
            logger.info(
                "Đã chấm xong DQ (lần chạy %s, status=%s, %d rule, %d lỗi)",
                kq.get("run_id") or "(thử)",
                kq.get("status"),
                len(kq.get("rules", [])),
                kq.get("rule_errors", 0),
            )
        except asyncio.CancelledError:
            logger.info("Worker chất lượng dữ liệu nhận tín hiệu dừng.")
            break
        except Exception as exc:
            logger.exception("Chạy worker chất lượng dữ liệu thất bại ở lượt này, thử lại ở lượt sau: %s", exc)
        try:
            await asyncio.sleep(args.lap_giay)
        except asyncio.CancelledError:
            logger.info("Worker chất lượng dữ liệu nhận tín hiệu dừng.")
            break
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Chạy rule chất lượng dữ liệu")
    p.add_argument("--rule", help="Chỉ chạy một rule, ví dụ DQ-CD-01")
    p.add_argument("--domain", help="Chỉ chạy rule của một miền, ví dụ ho_so")
    p.add_argument("--dry-run", action="store_true", help="Chỉ đếm, không ghi lần chạy/vấn đề")
    p.add_argument("--json", action="store_true")
    p.add_argument("--dsn", default=None)
    p.add_argument("--lap-giay", type=int, help="Chạy nền, mỗi N giây chấm lại rule DQ")
    a = p.parse_args(argv)
    if a.lap_giay is not None:
        if a.lap_giay < 1:
            p.error("--lap-giay tối thiểu 1")
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        return asyncio.run(_chay_lap(a))
    kq = asyncio.run(chay(a.dsn or dsn_mac_dinh(), a.rule, a.domain, a.dry_run, "data_quality_worker"))
    if a.json:
        print(json.dumps(kq, ensure_ascii=False, indent=2))
    else:
        print(f"Lần chạy {kq['run_id'] or '(thử)'}: {kq['status']}, {len(kq['rules'])} rule, {kq['rule_errors']} rule lỗi")
        for r in kq["rules"]:
            if r.get("loi"):
                print(f"  {r['code']}: lỗi khi chạy")
            else:
                print(f"  {r['code']}: {r['failed']}/{r['total']} lỗi" + (f", {r.get('moi', 0)} vấn đề mới" if "moi" in r else ""))
    return 0 if kq["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Đối soát trạng thái mong muốn (Git) với thực tế đang chạy (`dx gitops`).

Trạng thái mong muốn là những gì nằm trong repo:
1. compose.yaml, profile core: mỗi dịch vụ phải có container, đúng config-hash compose tính,
   đang chạy (dịch vụ restart: "no" thì phải đã chạy xong, mã 0).
2. Tệp cấu hình theo dõi (compose.yaml, apps/*/app.yaml, apps/*/db/migrations, core/) không
   có thay đổi chưa commit so với Git.
3. Chính sách app trong core.app_policies khớp app.yaml (flow_policies, doc_signers, metrics, break_glass).

Mặc định chỉ báo lệch. `--apply` áp lại bằng `docker compose --profile core up -d` (không xóa volume,
không --remove-orphans) và `app_manager.py upgrade`. Thay đổi chưa commit chỉ được báo, không bao giờ bị hoàn tác.

Mỗi lần chạy ghi một dòng JSON vào logs/reconciler.jsonl. Khóa logs/reconciler.lock để hai lần
chạy (timer, tay) không chồng nhau: lần sau thoát ngay với mã 0.

Mã thoát: 0 không lệch (hoặc đang có lần chạy khác); 1 lỗi (không gọi được docker...); 3 có lệch.
"""

import argparse
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, io.UnsupportedOperation):
        pass

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = ROOT / "logs"
PROJECT = "dxos"
WATCHED = ["compose.yaml", "apps", "core"]
POLICY_KEYS = {"flow_policies": "flow_policies", "break_glass": "break_glass"}


def sh(cmd: list[str], timeout: int = 60, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout, cwd=ROOT, **kw)


class Khoa:
    """Khóa tệp không chặn: có lần chạy khác đang giữ thì acquire() trả False."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a+")
        try:
            if os.name == "nt":
                import msvcrt

                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.fh.close()
            self.fh = None
            return False
        return True

    def release(self) -> None:
        if self.fh:
            self.fh.close()
            self.fh = None


def compose_services() -> dict[str, dict]:
    data = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8")) or {}
    return {
        name: {"mot_lan": str(cfg.get("restart", "")) == "no"}
        for name, cfg in (data.get("services") or {}).items()
        if "core" in (cfg.get("profiles") or [])
    }


def lech_compose() -> list[dict]:
    services = compose_services()
    r = sh(["docker", "compose", "--profile", "core", "config", "--hash", "*"])
    if r.returncode != 0:
        raise RuntimeError(f"docker compose config --hash lỗi: {r.stderr.strip()[:200]}")
    mong_muon = dict(line.split() for line in r.stdout.splitlines() if len(line.split()) == 2)
    r = sh([
        "docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={PROJECT}",
        "--format", "{{.Labels}}|{{.State}}",
    ])
    if r.returncode != 0:
        raise RuntimeError(f"docker ps lỗi: {r.stderr.strip()[:200]}")
    thuc_te: dict[str, tuple[str, str]] = {}
    for line in r.stdout.splitlines():
        labels, _, state = line.rpartition("|")
        lab = dict(p.split("=", 1) for p in labels.split(",") if "=" in p)
        svc = lab.get("com.docker.compose.service")
        if svc:
            thuc_te[svc] = (lab.get("com.docker.compose.config-hash", ""), state)
    lech = []
    for svc, meta in services.items():
        if svc not in thuc_te:
            lech.append({"loai": "compose", "dich_vu": svc, "chi_tiet": "thiếu container"})
            continue
        h, state = thuc_te[svc]
        if mong_muon.get(svc) and h != mong_muon[svc]:
            lech.append({"loai": "compose", "dich_vu": svc, "chi_tiet": "cấu hình container khác compose.yaml"})
        if not meta["mot_lan"] and state != "running":
            lech.append({"loai": "compose", "dich_vu": svc, "chi_tiet": f"trạng thái {state}"})
    return lech


def lech_git() -> list[dict]:
    r = sh(["git", "status", "--porcelain", "--", *WATCHED])
    if r.returncode != 0:
        return [{"loai": "git", "chi_tiet": f"không đọc được git status: {r.stderr.strip()[:200]}"}]
    return [{"loai": "git", "tep": line[3:], "chi_tiet": f"thay đổi chưa commit ({line[:2].strip()})"}
            for line in r.stdout.splitlines() if line.strip()]


def psql_json(sql: str) -> list:
    r = sh(["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql])
    if r.returncode != 0:
        raise RuntimeError(f"psql lỗi: {r.stderr.strip()[:200]}")
    return [json.loads(x) for x in r.stdout.splitlines() if x.strip()]


def lech_chinh_sach() -> list[dict]:
    lech = []
    for app_yaml in sorted((ROOT / "apps").glob("*/app.yaml")):
        app = yaml.safe_load(app_yaml.read_text(encoding="utf-8")) or {}
        code = app.get("code") or app_yaml.parent.name
        rows = psql_json(
            "SELECT json_build_object('t', policy_type, 'k', policy_key, 'd', policy_data) "
            f"FROM core.app_policies WHERE app_code = '{code.replace(chr(39), '')}'"
        )
        db = {(x["t"], x["k"]): x["d"] for x in rows}
        mong_muon: dict[tuple[str, str], object] = {}
        if app.get("flow_policies"):
            mong_muon[("flow_policies", "default")] = app["flow_policies"]
        if app.get("break_glass"):
            mong_muon[("break_glass", "config")] = app["break_glass"]
        for doc_type, cfg in (app.get("doc_signers") or {}).items():
            mong_muon[("doc_signers", doc_type)] = cfg
        for m in app.get("metrics") or []:
            mong_muon[("metrics", m["code"])] = None  # chỉ kiểm có mặt; app_manager thêm trường mặc định
        if not db and mong_muon:
            lech.append({"loai": "chinh_sach", "app": code, "chi_tiet": "app chưa được cài (core.app_policies trống)"})
            continue
        for key, want in mong_muon.items():
            if key not in db:
                lech.append({"loai": "chinh_sach", "app": code, "chi_tiet": f"thiếu {key[0]}/{key[1]}"})
            elif want is not None and db[key] != want:
                lech.append({"loai": "chinh_sach", "app": code, "chi_tiet": f"{key[0]}/{key[1]} khác app.yaml"})
    return lech


def ap_lai(lech: list[dict]) -> list[str]:
    da_lam = []
    if any(x["loai"] == "compose" for x in lech):
        r = sh(["docker", "compose", "--profile", "core", "up", "-d"], timeout=600)
        da_lam.append(f"docker compose --profile core up -d -> mã {r.returncode}")
    for app in sorted({x["app"] for x in lech if x["loai"] == "chinh_sach"}):
        r = sh(["docker", "compose", "--profile", "tools", "run", "--rm", "-T", "tools",
                "scripts/app_manager.py", "upgrade", app], timeout=600)
        da_lam.append(f"app_manager upgrade {app} -> mã {r.returncode}")
    return da_lam


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Đối soát trạng thái mong muốn với thực tế (dx gitops)")
    ap.add_argument("--apply", action="store_true", help="Áp lại compose và chính sách app khi lệch")
    ap.add_argument("--bo-chinh-sach", action="store_true", help="Không kiểm core.app_policies")
    args = ap.parse_args(argv)

    khoa = Khoa(LOG_DIR / "reconciler.lock")
    if not khoa.acquire():
        print("[RECONCILER] Đang có lần đối soát khác chạy, bỏ qua lần này.")
        return 0
    try:
        print("=== [GITOPS RECONCILER] Đối soát trạng thái ===")
        try:
            lech = lech_compose() + lech_git()
            if not args.bo_chinh_sach:
                lech += lech_chinh_sach()
        except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            return 1
        for x in lech:
            doi_tuong = x.get("dich_vu") or x.get("tep") or x.get("app") or ""
            print(f"  [LỆCH] {x['loai']}: {doi_tuong} {x['chi_tiet']}".rstrip())
        da_lam = ap_lai(lech) if (args.apply and lech) else []
        for d in da_lam:
            print(f"  [ÁP LẠI] {d}")
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "reconciler.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "lech": lech, "ap_lai": da_lam,
            }, ensure_ascii=False) + "\n")
        if lech:
            print(f"=== {len(lech)} mục lệch{'; đã áp lại, chạy lại để kiểm' if da_lam else ''} ===")
            return 3
        print("=== Không có lệch ===")
        return 0
    finally:
        khoa.release()


if __name__ == "__main__":
    sys.exit(main())

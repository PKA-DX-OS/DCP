#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Chẩn đoán hệ thống `dx doctor`.

Kiểm tra lần lượt và báo đúng mục lỗi:
1. Container profile `core` trong compose.yaml: đang chạy, healthcheck `healthy`;
   container chạy một lần (restart: "no") phải thoát mã 0.
2. Cổng: cổng công bố ra máy (chạy trên máy) hoặc cổng nội bộ theo tên dịch vụ (chạy trong container tools).
3. Chứng thư TLS NATS MQTT (core/nats/certs/server.crt): có và còn hạn.
4. Dung lượng đĩa trống tại thư mục repo.
5. Đầu-cuối: lấy token thật từ Keycloak cho tài khoản demo, gọi PostgREST qua APISIX.

Mã thoát: 0 khi không có mục FAIL; 1 khi có ít nhất một mục FAIL; 2 khi tham số sai.
Không in mật khẩu hay token ra màn hình.
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on all platforms
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception) as _e:
        _ = _e

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
DEMO_ACCOUNTS_FILE = ROOT / "secrets" / "demo-accounts.txt"
NATS_CERT = ROOT / "core" / "nats" / "certs" / "server.crt"
DISK_WARN_BYTES = 2 * 1024**3
DISK_FAIL_BYTES = 512 * 1024**2
CERT_WARN_DAYS = 30


class KetQua:
    def __init__(self) -> None:
        self.loi: list[str] = []
        self.canh_bao: list[str] = []

    def ok(self, msg: str) -> None:
        print(f"  [OK]   {msg}")

    def warn(self, msg: str) -> None:
        self.canh_bao.append(msg)
        print(f"  [WARN] {msg}")

    def fail(self, msg: str) -> None:
        self.loi.append(msg)
        print(f"  [FAIL] {msg}")


def trong_container() -> bool:
    return Path("/.dockerenv").exists() or os.getenv("DX_IN_CONTAINER") == "1"


def dich_vu_core(profile: str = "core") -> list[dict]:
    """Đọc compose.yaml: dịch vụ thuộc profile, tên container, healthcheck, cổng công bố."""
    data = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8")) or {}
    ds = []
    for ten, cfg in (data.get("services") or {}).items():
        if profile not in (cfg.get("profiles") or []):
            continue
        cong = []
        for p in cfg.get("ports") or []:
            phan = str(p).split(":")
            if len(phan) >= 2:
                cong.append((int(phan[-2]), int(phan[-1].split("/")[0])))
        ds.append({
            "ten": ten,
            "container": cfg.get("container_name") or ten,
            "co_health": "healthcheck" in cfg,
            "mot_lan": str(cfg.get("restart", "")) == "no",
            "cong": cong,
        })
    return ds


def kiem_container(ds: list[dict], kq: KetQua) -> None:
    print("--> 1. Container (profile core):")
    try:
        res = subprocess.run(
            ["docker", "inspect", "--format", "{{.Name}}|{{json .State}}", *[d["container"] for d in ds]],
            capture_output=True, text=True, timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        kq.fail(f"Không gọi được docker: {e}")
        return
    if res.returncode != 0 and not res.stdout.strip() and "No such object" not in res.stderr:
        kq.fail(f"docker inspect lỗi: {res.stderr.strip()[:200]}")
        return
    # Mỗi container tồn tại cho một dòng "/tên|{State}"; container không có thì không có dòng
    trang_thai: dict[str, dict] = {}
    for line in res.stdout.splitlines():
        ten, _, st = line.partition("|")
        try:
            trang_thai[ten.lstrip("/")] = json.loads(st)
        except json.JSONDecodeError:
            continue
    for d in ds:
        st = trang_thai.get(d["container"])
        ten = f"{d['ten']} ({d['container']})"
        if st is None:
            kq.fail(f"{ten}: không có container, chưa `dx up`?")
            continue
        status = st.get("Status")
        health = (st.get("Health") or {}).get("Status")
        if d["mot_lan"]:
            if status == "exited" and st.get("ExitCode") == 0:
                kq.ok(f"{ten}: đã chạy xong (mã 0)")
            elif status == "running":
                kq.warn(f"{ten}: vẫn đang chạy")
            else:
                kq.fail(f"{ten}: {status}, mã thoát {st.get('ExitCode')}")
            continue
        if status != "running":
            kq.fail(f"{ten}: {status}")
        elif d["co_health"] and health != "healthy":
            kq.fail(f"{ten}: healthcheck {health or 'chưa có'}")
        else:
            kq.ok(f"{ten}: running{', ' + health if health else ''}")


def kiem_cong(ds: list[dict], kq: KetQua) -> None:
    noi_bo = trong_container()
    print(f"--> 2. Cổng ({'nội bộ theo tên dịch vụ' if noi_bo else 'công bố trên máy'}):")
    for d in ds:
        for cong_may, cong_trong in d["cong"]:
            host, port = (d["ten"], cong_trong) if noi_bo else ("127.0.0.1", cong_may)
            try:
                with socket.create_connection((host, port), timeout=2):
                    kq.ok(f"{d['ten']}: {host}:{port} mở")
            except OSError as e:
                kq.fail(f"{d['ten']}: {host}:{port} không kết nối được ({e.__class__.__name__})")


def kiem_chung_thu(kq: KetQua) -> None:
    print("--> 3. Chứng thư TLS NATS MQTT:")
    if not NATS_CERT.exists():
        kq.fail(f"Thiếu {NATS_CERT.relative_to(ROOT)}; chạy `dx init`")
        return
    try:
        from cryptography import x509

        cert = x509.load_pem_x509_certificate(NATS_CERT.read_bytes())
        het = cert.not_valid_after_utc
    except Exception as e:
        kq.fail(f"Không đọc được {NATS_CERT.name}: {e}")
        return
    con = (het - datetime.now(timezone.utc)).days
    if con < 0:
        kq.fail(f"{NATS_CERT.name} đã hết hạn từ {het:%d/%m/%Y}")
    elif con < CERT_WARN_DAYS:
        kq.warn(f"{NATS_CERT.name} còn {con} ngày (hết hạn {het:%d/%m/%Y})")
    else:
        kq.ok(f"{NATS_CERT.name} còn {con} ngày")


def kiem_dia(kq: KetQua) -> None:
    print("--> 4. Dung lượng đĩa:")
    trong = shutil.disk_usage(ROOT).free
    gb = trong / 1024**3
    if trong < DISK_FAIL_BYTES:
        kq.fail(f"Chỉ còn {gb:.1f} GB trống tại {ROOT}")
    elif trong < DISK_WARN_BYTES:
        kq.warn(f"Còn {gb:.1f} GB trống tại {ROOT}")
    else:
        kq.ok(f"Còn {gb:.1f} GB trống")


def get_gateway_url() -> str:
    url = os.getenv("GATEWAY_INTERNAL_URL")
    if url:
        return url
    for host in ["http://apisix:8080", "http://localhost:8080", "http://127.0.0.1:8080"]:
        try:
            with httpx.Client(timeout=1.0) as client:
                if client.get(f"{host}/api/v1/health").status_code == 200:
                    return host
        except Exception:
            continue
    return "http://localhost:8080"


def get_keycloak_url() -> str:
    url = os.getenv("KEYCLOAK_INTERNAL_URL")
    if url:
        return url
    for host in ["http://keycloak:8080/auth", "http://localhost:8080/auth", "http://localhost:8081/auth"]:
        try:
            with httpx.Client(timeout=1.0) as client:
                if client.get(f"{host}/realms/dxos/.well-known/openid-configuration").status_code == 200:
                    return host
        except Exception:
            continue
    return "http://localhost:8080/auth"


def get_demo_account() -> tuple[str, str] | None:
    if not DEMO_ACCOUNTS_FILE.exists():
        return None
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 2 and parts[0] == "cdt.minh":
            return parts[0], parts[1]
    return None


def kiem_api(kq: KetQua) -> None:
    print("--> 5. Đầu-cuối Keycloak -> APISIX -> PostgREST:")
    acc = get_demo_account()
    if not acc:
        kq.fail(f"Thiếu tài khoản cdt.minh trong {DEMO_ACCOUNTS_FILE.relative_to(ROOT)} (chỉ có khi DEMO_MODE=true)")
        return
    username, password = acc
    gateway, keycloak = get_gateway_url(), get_keycloak_url()
    token = None
    for _ in range(3):
        try:
            resp = httpx.post(
                f"{keycloak}/realms/dxos/protocol/openid-connect/token",
                data={"client_id": "dx-test", "grant_type": "password", "username": username, "password": password},
                timeout=5.0,
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                break
            last = f"HTTP {resp.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(2)
    if not token:
        kq.fail(f"Keycloak ({keycloak}) không cấp token cho {username}: {last}")
        return
    kq.ok(f"Keycloak cấp token cho {username}")
    try:
        resp = httpx.get(f"{gateway}/api/v1/rest/v_ho_so?limit=1", headers={"Authorization": f"Bearer {token}"}, timeout=5.0)
    except Exception as e:
        kq.fail(f"Không gọi được APISIX {gateway}: {e}")
        return
    if resp.status_code == 200:
        kq.ok(f"PostgREST qua APISIX trả 200 ({len(resp.json())} bản ghi)")
    else:
        kq.fail(f"PostgREST qua APISIX trả HTTP {resp.status_code}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Chẩn đoán stack DX-OS (dx doctor)")
    ap.add_argument("--profile", default="core", help="Profile compose cần kiểm (mặc định core)")
    ap.add_argument("--bo-api", action="store_true", help="Bỏ bước gọi Keycloak/PostgREST")
    args = ap.parse_args(argv)

    print("=== [DX-OS DOCTOR] Chẩn đoán hệ thống ===")
    kq = KetQua()
    ds = dich_vu_core(args.profile)
    kiem_container(ds, kq)
    kiem_cong(ds, kq)
    kiem_chung_thu(kq)
    kiem_dia(kq)
    if not args.bo_api:
        kiem_api(kq)

    print("==========================================================")
    if kq.loi:
        print(f"[FAIL] {len(kq.loi)} mục lỗi:", file=sys.stderr)
        for m in kq.loi:
            print(f"  - {m}", file=sys.stderr)
        return 1
    print(f"[PASS] Hệ thống hoạt động bình thường ({len(kq.canh_bao)} cảnh báo).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

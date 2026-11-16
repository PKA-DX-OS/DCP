#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import argparse
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ICT = timezone(timedelta(hours=7))

# Công trường và thiết bị mô phỏng tương ứng
SITES = {
    "CT-01": "DEV-NOISE-01",
    "CT-02": "DEV-NOISE-02",
}


def utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def load_sensor_secret(tenant: str) -> str:
    env_name = f"SENSOR_{tenant.upper().replace('-', '_')}_SECRET"
    secret = os.environ.get(env_name, "").strip()
    if not secret:
        secret_file = Path("secrets") / f"sensor-{tenant}-secret.txt"
        if secret_file.exists():
            secret = secret_file.read_text(encoding="utf-8").strip()
    if not secret:
        raise SystemExit(
            f"Thiếu secret cho tenant {tenant}. Đặt {env_name} trong .env "
            f"hoặc chạy 'make init' để tạo secrets/sensor-{tenant}-secret.txt"
        )
    return secret


def build_metrics(spike: bool, local_hour: int) -> dict:
    if spike:
        laeq = random.uniform(84.0, 86.5)
        pm10 = random.uniform(80.0, 115.0)
        pm25 = random.uniform(40.0, 55.0)
    else:
        laeq = random.uniform(55.0, 64.0)
        pm10 = random.uniform(30.0, 45.0)
        pm25 = random.uniform(15.0, 25.0)
        if local_hour >= 21 or local_hour < 6:
            laeq = min(laeq, 54.9)
    return {
        "laeq_dba": round(laeq, 1),
        "pm10": round(pm10, 1),
        "pm25": round(pm25, 1),
    }


def build_payload(tenant: str, site_id: str, device_id: str, spike: bool) -> dict:
    now_utc = datetime.now(timezone.utc)
    return {
        "tenant": tenant,
        "site_id": site_id,
        "device_id": device_id,
        "source": "sensor",
        "ts": now_utc.isoformat(),
        "metrics": build_metrics(spike, now_utc.astimezone(ICT).hour),
    }


class TokenClient:
    """Lấy token OAuth2 client_credentials, làm mới trước khi hết hạn 30 giây."""

    def __init__(self, token_url: str, client_id: str, client_secret: str):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = ""
        self._expires_at = 0.0

    def get(self, http: httpx.Client) -> str:
        if self._token and time.time() < self._expires_at - 30:
            return self._token
        resp = http.post(self.token_url, data={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }, timeout=10.0)
        if resp.status_code != 200:
            raise RuntimeError(f"lấy token thất bại: HTTP {resp.status_code}")
        body = resp.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + float(body.get("expires_in", 300))
        return self._token

    def invalidate(self) -> None:
        self._token = ""
        self._expires_at = 0.0


def send_reading(http: httpx.Client, tokens: TokenClient, endpoint: str, payload: dict) -> None:
    stamp = datetime.now(ICT).strftime("%H:%M:%S")
    m = payload["metrics"]
    for attempt in (1, 2):
        try:
            headers = {"Authorization": f"Bearer {tokens.get(http)}"}
            resp = http.post(endpoint, json=payload, headers=headers, timeout=5.0)
        except (RuntimeError, httpx.HTTPError) as exc:
            print(f"[{stamp}] Lỗi kết nối hoặc xác thực: {exc}")
            return
        if resp.status_code == 401 and attempt == 1:
            tokens.invalidate()
            continue
        if resp.status_code == 201:
            alerts = resp.json().get("alerts", [])
            flag = f" [CẢNH BÁO: {len(alerts)}]" if alerts else ""
            print(f"[{stamp}] {payload['site_id']} ({payload['device_id']}): "
                  f"ồn={m['laeq_dba']} dBA, PM10={m['pm10']}, PM2.5={m['pm25']}{flag}")
        else:
            print(f"[{stamp}] Lỗi gửi bản tin: HTTP {resp.status_code} {resp.text[:200]}")
        return


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DX-OS: giả lập cảm biến bụi/tiếng ồn công trường")
    p.add_argument("--endpoint", default=os.getenv("DX_INGEST_URL", "http://localhost:8080/api/v1/ingest"))
    p.add_argument("--keycloak", default=os.getenv("KEYCLOAK_URL", "http://localhost:8080/auth"),
                   help="URL Keycloak qua APISIX")
    p.add_argument("--tenant", default=os.getenv("DX_TENANT", "phuong-a"))
    p.add_argument("--site", choices=sorted(SITES), help="Chỉ phát cho một công trường")
    p.add_argument("--spike", action="store_true", help="Phát đột biến 84-86.5 dBA")
    p.add_argument("--duration", type=int, default=120, help="Thời gian chạy (giây); 0 = chạy mãi")
    p.add_argument("--interval", type=int, default=5, help="Chu kỳ giữa các bản tin (giây)")
    p.add_argument("--dry-run", action="store_true", help="Chỉ in payload, không gửi, không cần secret")
    return p.parse_args()


def main() -> int:
    utf8_console()
    args = parse_args()

    client_id = f"dxos-sensor-{args.tenant}"
    token_url = f"{args.keycloak.rstrip('/')}/realms/dxos/protocol/openid-connect/token"
    tokens = None
    if not args.dry_run:
        tokens = TokenClient(token_url, client_id, load_sensor_secret(args.tenant))

    sites = [args.site] if args.site else list(SITES)
    spike_site = args.site or "CT-01"

    print("=" * 58)
    print(" [DX-OS] GIẢ LẬP CẢM BIẾN CÔNG TRƯỜNG")
    print(f" Chế độ: {'ĐỘT BIẾN' if args.spike else 'BÌNH THƯỜNG'} | công trường: {', '.join(sites)}")
    print("=" * 58)

    start = time.time()
    with httpx.Client() as http:
        while True:
            if args.duration and time.time() - start >= args.duration:
                print("[HOÀN TẤT] Đã hết thời gian chạy.")
                break
            for site_id in sites:
                spike = args.spike and site_id == spike_site
                payload = build_payload(args.tenant, site_id, SITES[site_id], spike)
                if args.dry_run:
                    print(payload)
                else:
                    send_reading(http, tokens, args.endpoint, payload)
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
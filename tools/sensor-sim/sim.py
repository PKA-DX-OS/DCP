#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Công cụ giả lập thiết bị cảm biến IoT công trường:
- Xác thực OAuth2 client_credentials (vai dx:device) qua Keycloak trước khi gửi dữ liệu qua Gateway.
- Bình thường: phát số liệu tiếng ồn 55-65 dBA, PM10 30-45 µg/m³, PM2.5 15-25 µg/m³.
- Chế độ spike (--spike): phát tiếng ồn 78 dBA vượt ngưỡng ban ngày (70 dBA) để kích hoạt quy trình hậu kiểm.
"""

import argparse
import os
import random
import time
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
import httpx

logger = logging.getLogger("sensor-sim")

# Ensure UTF-8 output on all platforms
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception) as _e:
        _ = _e


def get_sensor_token(keycloak_url: str, tenant: str = "phuong-a") -> str:
    secret = os.environ.get(f"SENSOR_{tenant.upper().replace('-', '_')}_SECRET")
    if not secret:
        secret_file = Path(f"secrets/sensor-{tenant}-secret.txt")
        if secret_file.exists():
            secret = secret_file.read_text(encoding="utf-8").strip()
    if not secret:
        secret = "dxos_dev_sensor_phuong_a_secret_2026" if tenant == "phuong-a" else "dxos_dev_sensor_phuong_b_secret_2026"

    token_url = f"{keycloak_url.rstrip('/')}/realms/dxos/protocol/openid-connect/token"
    client_id = f"dxos-sensor-{tenant}"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": secret,
                },
            )
            if resp.status_code == 200:
                return resp.json().get("access_token", "")
            else:
                print(f"Lỗi lấy token cho sensor {client_id}: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Không kết nối được Keycloak để lấy token sensor: {e}")
    return ""


def send_reading(endpoint: str, site_id: str, device_id: str, laeq: float, pm10: float, pm25: float, tenant: str = "phuong-a", token: str = ""):
    payload = {
        "tenant": tenant,
        "site_id": site_id,
        "device_id": device_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "laeq_dba": round(laeq, 1),
            "pm10": round(pm10, 1),
            "pm25": round(pm25, 1),
        },
    }
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 201:
                data = resp.json()
                alerts = data.get("alerts", [])
                alert_str = f" [CẢNH BÁO VƯỢT NGƯỠNG: {len(alerts)}]" if alerts else ""
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {site_id} ({device_id}): ồn={laeq}dBA, PM10={pm10}, PM2.5={pm25}{alert_str}")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Lỗi gửi bản tin: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Không kết nối được API Ingest ({e})")


def main():
    parser = argparse.ArgumentParser(description="DX-OS Sensor Simulator")
    parser.add_argument("--endpoint", default="http://localhost:8080/api/v1/ingest", help="Ingest API URL")
    parser.add_argument("--keycloak", default="http://keycloak:8080/auth", help="Keycloak URL")
    parser.add_argument("--spike", action="store_true", help="Gửi tiếng ồn đột biến 78 dBA (vượt ngưỡng ban ngày 70 dBA)")
    parser.add_argument("--duration", type=int, default=120, help="Thời gian chạy đột biến (giây)")
    parser.add_argument("--interval", type=int, default=5, help="Khoảng thời gian giữa các bản tin (giây)")
    parser.add_argument("--tenant", default="phuong-a", help="Tenant đơn vị")
    parser.add_argument("--site", default="", help="Mã công trình cụ thể để phát mô phỏng đột biến")
    parser.add_argument("--laeq", type=float, default=86.5, help="Chỉ số tiếng ồn dBA khi phát đột biến cụ thể")
    args = parser.parse_args()

    # Thử lấy token từ localhost nếu keycloak URL mặc định là docker internal
    kc_url = args.keycloak
    if "keycloak:8080" in kc_url:
        # Nếu chạy ngoài container, đổi sang localhost:8081
        try:
            with httpx.Client(timeout=1.0) as cl:
                r = cl.get("http://localhost:8081/auth/realms/dxos")
                if r.status_code == 200:
                    kc_url = "http://localhost:8081/auth"
        except Exception as probe_err:
            logger.debug(f"Không thể kết nối localhost:8081 Keycloak: {probe_err}")

    token = get_sensor_token(kc_url, args.tenant)
    if not token:
        # Thử lại với localhost nếu chưa thành công
        token = get_sensor_token("http://localhost:8081/auth", args.tenant)

    print("==========================================================")
    print(" [DX-OS] KHỞI ĐỘNG CẢM BIẾN GIẢ LẬP CÔNG TRƯỜNG IOT ")
    if args.spike:
        print(" CHẾ ĐỘ: ĐỘT BIẾN TIẾNG ỒN (VƯỢT NGƯỠNG)")
        print(f" Thời gian phát: {args.duration} giây | Chu kỳ: {args.interval} giây")
    else:
        print(" CHẾ ĐỘ: HOẠT ĐỘNG BÌNH THƯỜNG")
    if token:
        print(f" Xác thực OAuth2: Đã lấy token Bearer thành công cho {args.tenant}.")
    else:
        print(" [CẢNH BÁO] Không lấy được token Keycloak, gửi không xác thực.")
    print("==========================================================")

    if args.site:
        dev_id = f"DEV-NOISE-{args.site}"
        send_reading(args.endpoint, args.site, dev_id, args.laeq, 85.0, 45.0, tenant=args.tenant, token=token)
        print(f"[HOÀN TẤT] Đã phát bản tin mô phỏng cảm biến cho {args.site} với tiếng ồn {args.laeq} dBA.")
        return

    start_time = time.time()
    devices = [("CT-01", "DEV-NOISE-01"), ("CT-02", "DEV-NOISE-02")]

    while True:
        elapsed = time.time() - start_time
        if args.spike and elapsed >= args.duration:
            print(f"\n[HOÀN TẤT] Đã hoàn thành phát chuỗi đột biến {args.duration} giây.")
            break

        for site_id, dev_id in devices:
            if args.spike and site_id == "CT-01":
                # Đột biến vượt ngưỡng 85 dBA
                laeq = random.uniform(84.0, 86.5)
                pm10 = random.uniform(80.0, 115.0)
                pm25 = random.uniform(40.0, 55.0)
            else:
                laeq = random.uniform(55.0, 64.0)
                pm10 = random.uniform(30.0, 45.0)
                pm25 = random.uniform(15.0, 25.0)

            send_reading(args.endpoint, site_id, dev_id, laeq, pm10, pm25, tenant=args.tenant, token=token)

        time.sleep(args.interval)


if __name__ == "__main__":
    main()

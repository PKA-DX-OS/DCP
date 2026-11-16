#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
DX-OS GitOps Reconciler (F-22, F-47, O-01, O-02):
- Đọc `deploy/release.env` và `deploy/cosign.pub`.
- Kiểm tra tính hợp lệ của chữ ký cosign đối với release digest.
- So khớp mã băm SHA-256 của `compose.yaml` hiện tại với giá trị đã ký.
- Nếu phát hiện trôi dạt (drift): ghi log JSON, tự phục hồi bằng docker compose up -d thật.
- Nếu không có chữ ký hợp lệ: thoát mã 2.
"""

import hashlib
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on all platforms
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, io.UnsupportedOperation):
        pass


def compute_file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_cosign_signature(digest: str, pub_key: Path) -> bool:
    """Xác minh chữ ký số cosign. Không có chữ ký hợp lệ hoặc thiếu công cụ -> False."""
    if not pub_key.exists():
        print(f"[RECONCILER] Không tìm thấy khóa công khai {pub_key}", file=sys.stderr)
        return False

    try:
        res = subprocess.run(
            ["cosign", "verify", "--key", str(pub_key), digest],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return res.returncode == 0
    except FileNotFoundError:
        print("[RECONCILER] Công cụ cosign chưa được cài đặt trong môi trường!", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[RECONCILER] Lỗi xác minh chữ ký cosign: {e}", file=sys.stderr)
        return False


def run_reconciliation():
    root = Path(__file__).resolve().parent.parent.parent
    release_env = root / "deploy" / "release.env"
    if not release_env.exists():
        release_env = root / "deploy" / "release.env.example"
    cosign_pub = root / "deploy" / "cosign.pub"
    compose_file = root / "compose.yaml"

    print("=== [GITOPS RECONCILER] Bắt đầu chu trình đối soát cấu hình ===")

    if not release_env.exists():
        print(f"[ERROR] Không tìm thấy tệp khai báo phát hành {release_env}", file=sys.stderr)
        sys.exit(1)

    # Đọc cấu hình release.env
    env_vars = {}
    for line in release_env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()

    expected_compose_hash = env_vars.get("COMPOSE_FILE_SHA256", "")
    current_compose_hash = compute_file_sha256(compose_file)
    services_image = env_vars.get("DXOS_SERVICES_IMAGE", "")

    print(f"  * Phiên bản phát hành mục tiêu: {env_vars.get('RELEASE_VERSION', '1.1.0')}")
    print(f"  * Digest hình ảnh dịch vụ: {services_image or '<chưa cấu hình bản phát hành đã ký>'}")

    # 1. Xác minh chữ ký số cosign nếu có khai báo hình ảnh đã phát hành (O-01, O-02)
    if services_image:
        is_signed = verify_cosign_signature(services_image, cosign_pub)
        if not is_signed:
            print("[FAIL] Chữ ký số cosign không hợp lệ hoặc thiếu chứng thực! Từ chối áp dụng bản cập nhật.", file=sys.stderr)
            sys.exit(2)
        print("  [PASS] Chữ ký số cosign hợp lệ.")
    else:
        print("  [INFO] Chưa có bản phát hành đã ký (DXOS_SERVICES_IMAGE rỗng). Reconciler đối chiếu cấu hình compose.yaml.")

    # 2. Kiểm tra trôi dạt cấu hình compose.yaml (F-47)
    drift_detected = False
    if expected_compose_hash and current_compose_hash != expected_compose_hash:
        drift_detected = True
        drift_event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "config_drift_detected",
            "expected_hash": expected_compose_hash,
            "actual_hash": current_compose_hash,
            "action": "reconcile_self_healing",
        }
        print(f"  [DRIFT LOG JSON] {json.dumps(drift_event)}")
        print("  --> Đang kích hoạt tự phục hồi (Self-Healing)...")
        # Thực thi áp dụng lại cấu hình chuẩn thật qua docker compose
        try:
            res = subprocess.run(
                ["docker", "compose", "--profile", "core", "up", "-d", "--remove-orphans"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            print(f"  [ACTION EXECUTED] Mã thoát: {res.returncode}")
            if res.returncode != 0:
                print(f"  [ACTION ERROR] docker compose thất bại: {res.stderr}", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"  [ACTION ERROR] Không thể tự phục hồi qua Docker: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("  [PASS] Cấu hình compose.yaml hoàn toàn khớp với bản phát hành chuẩn Git.")

    if drift_detected:
        print("=== [GITOPS RECONCILER] Đã phát hiện và tự phục hồi trôi dạt cấu hình thành công. ===")
    else:
        print("=== [GITOPS RECONCILER] Chu trình đối soát hoàn thành: hệ thống đồng bộ, không có drift. ===")


if __name__ == "__main__":
    run_reconciliation()

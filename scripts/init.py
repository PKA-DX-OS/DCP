#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kịch bản khởi tạo môi trường `dx init`:
1. Sinh các chuỗi bí mật ngẫu nhiên an toàn cho `.env`.
2. Tạo chứng chỉ TLS tự ký cho cổng MQTT của NATS (cổng 8883).
3. Kết xuất các tệp cấu hình bảo mật vào thư mục `secrets/` ngoài Git:
   - `secrets/realm-dxos.json`
   - `secrets/seaweedfs-s3.json`
   - `secrets/nats-auth.conf`
4. Khởi tạo tệp JWKS cục bộ `core/postgrest/jwks.json`.
"""

import hashlib
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure UTF-8 output on all platforms
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception) as _e:
        _ = _e

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def generate_self_signed_cert(cert_dir: Path):
    cert_dir.mkdir(parents=True, exist_ok=True)
    key_path = cert_dir / "server.key"
    cert_path = cert_dir / "server.crt"

    if key_path.exists() and cert_path.exists():
        print("  - Chứng chỉ TLS cho NATS MQTT đã tồn tại.")
        return

    print("  - Đang sinh cặp khóa và chứng chỉ TLS cho cổng NATS MQTT :8883...")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "VN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DX-OS Core (mẫu)"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("nats"),
                x509.IPAddress(__import__("ipaddress").ip_address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"  - Đã lưu chứng chỉ TLS vào {cert_dir}")


def render_template(tpl_path: Path, out_path: Path, env_map: dict):
    if not tpl_path.exists():
        return
    text = tpl_path.read_text(encoding="utf-8")
    for k, v in env_map.items():
        text = text.replace(f"${{{k}}}", str(v))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")


def render_realm_dxos(tpl_path: Path, out_path: Path, env_map: dict):
    """Kết xuất cấu hình Keycloak Realm từ template với chính sách bảo mật động (N-08, N-09)."""
    if not tpl_path.exists():
        return
    text = tpl_path.read_text(encoding="utf-8")
    for k, v in env_map.items():
        text = text.replace(f"${{{k}}}", str(v))
    try:
        data = json.loads(text)
    except Exception as e:
        print(f"[WARN] Lỗi phân tích JSON realm template: {e}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        return

    # N-08: Sinh redirectUris và webOrigins từ PUBLIC_BASE_URL (hỗ trợ nhiều URL phân cách dấu phẩy)
    raw_pub = env_map.get("PUBLIC_BASE_URL", "http://localhost:8080")
    pub_urls = [u.strip().rstrip("/") for u in raw_pub.split(",") if u.strip()]
    redirects = ["http://localhost:8080/*", "http://127.0.0.1:8080/*"]
    origins = ["http://localhost:8080", "http://127.0.0.1:8080", "+"]
    for u in pub_urls:
        r = f"{u}/*"
        if r not in redirects:
            redirects.append(r)
        if u not in origins:
            origins.append(u)

    # N-09: dx-test chỉ được tạo khi DEMO_MODE=true
    is_demo = str(env_map.get("DEMO_MODE", "false")).lower() in ("true", "1", "yes")

    filtered_clients = []
    for client in data.get("clients", []):
        cid = client.get("clientId")
        if cid == "dxos-web":
            # N-09: Tắt directAccessGrantsEnabled trên client công khai dxos-web
            client["directAccessGrantsEnabled"] = False
            client["redirectUris"] = redirects
            client["webOrigins"] = origins
            filtered_clients.append(client)
        elif cid == "dx-test":
            if is_demo:
                client["directAccessGrantsEnabled"] = True
                filtered_clients.append(client)
        else:
            filtered_clients.append(client)
    data["clients"] = filtered_clients

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  - Đã kết xuất cấu hình Realm Keycloak vào secrets/realm-dxos.json (N-08, N-09)")


def load_or_create_env(root_dir: Path, force_demo: bool = False) -> dict:
    env_example = root_dir / ".env.example"
    env_target = root_dir / ".env"

    env_map = {}

    # Nếu .env đã có sẵn, đọc cấu hình hiện tại
    if env_target.exists():
        print("  - Tệp .env đã tồn tại, đọc các bí mật hiện có...")
        for line in env_target.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_map[k.strip()] = v.strip()
    else:
        print("  - Đang sinh tệp .env với các bí mật ngẫu nhiên an toàn...")

    if force_demo:
        env_map["DEMO_MODE"] = "true"
        print("  - Kích hoạt DEMO_MODE=true theo yêu cầu (cờ --demo)")

    # Đọc danh sách biến từ .env.example
    example_lines = env_example.read_text(encoding="utf-8").splitlines()
    new_lines = []

    for line in example_lines:
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#") or "=" not in trimmed:
            new_lines.append(line)
            continue

        k, default_val = trimmed.split("=", 1)
        k = k.strip()
        default_val = default_val.strip()

        if k in env_map:
            new_lines.append(f"{k}={env_map[k]}")
            continue

        # Sinh bí mật ngẫu nhiên cho các khóa bảo mật
        if "PASSWORD" in k or "SECRET" in k or k == "OPENBAO_TOKEN":
            val = secrets.token_urlsafe(20)
        elif "ACCESS_KEY" in k:
            val = "s3_" + secrets.token_hex(8)
        else:
            val = default_val

        env_map[k] = val
        new_lines.append(f"{k}={val}")

    # V2-01: Kiểm tra bắt buộc bốn bộ mật khẩu cơ sở dữ liệu riêng biệt
    required_db_pw_keys = [
        "POSTGRES_SUPERUSER_PASSWORD",
        "KEYCLOAK_DB_PASSWORD",
        "FLOWABLE_DB_PASSWORD",
        "DB_PASSWORD",
    ]
    for r_key in required_db_pw_keys:
        if not env_map.get(r_key):
            # Nếu chưa có trong .env cũ, tự sinh ngẫu nhiên
            val = secrets.token_urlsafe(20)
            env_map[r_key] = val
            new_lines.append(f"{r_key}={val}")

    db_passwords = [env_map[k] for k in required_db_pw_keys]
    if len(db_passwords) != len(set(db_passwords)):
        print("[ERROR] Bốn bộ mật khẩu cơ sở dữ liệu (POSTGRES_SUPERUSER_PASSWORD, KEYCLOAK_DB_PASSWORD, FLOWABLE_DB_PASSWORD, DB_PASSWORD) phải hoàn toàn khác nhau!", file=sys.stderr)
        sys.exit(1)

    # Q-01: Sinh mã FLOW_INTERNAL_TOKEN cho kết nối nội bộ Flowable -> Flow
    if not env_map.get("FLOW_INTERNAL_TOKEN"):
        val = secrets.token_urlsafe(32)
        env_map["FLOW_INTERNAL_TOKEN"] = val
        new_lines.append(f"FLOW_INTERNAL_TOKEN={val}")

    env_target.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    if not env_target.exists():
        print("  - Đã tạo tệp .env thành công.")
    else:
        print("  - Đã đồng bộ và cập nhật tệp .env thành công.")

    return env_map


def main():
    root = Path(__file__).resolve().parent.parent
    print("=== [DX-OS] Bắt đầu khởi tạo môi trường (dx init) ===")

    # 1. Tạo thư mục cấu trúc
    (root / "dist").mkdir(parents=True, exist_ok=True)
    (root / "backups").mkdir(parents=True, exist_ok=True)
    (root / "secrets").mkdir(parents=True, exist_ok=True)
    (root / "core" / "postgrest").mkdir(parents=True, exist_ok=True)

    # 2. Sinh TLS cert cho MQTT
    generate_self_signed_cert(root / "core" / "nats" / "certs")

    # 3. Nạp hoặc tạo .env (mặc định DEMO_MODE=false, chỉ true khi có cờ --demo)
    force_demo = "--demo" in sys.argv or "-demo" in sys.argv
    env_map = load_or_create_env(root, force_demo=force_demo)

    # 4. Render các template bảo mật vào thư mục secrets/
    render_realm_dxos(
        root / "core" / "keycloak" / "realm-dxos.template.json",
        root / "secrets" / "realm-dxos.json",
        env_map,
    )

    render_template(
        root / "core" / "seaweedfs" / "s3.template.json",
        root / "secrets" / "seaweedfs-s3.json",
        env_map,
    )
    print("  - Đã kết xuất cấu hình S3 SeaweedFS vào secrets/seaweedfs-s3.json")

    render_template(
        root / "core" / "nats" / "nats-auth.template.conf",
        root / "secrets" / "nats-auth.conf",
        env_map,
    )
    print("  - Đã kết xuất cấu hình xác thực NATS MQTT vào secrets/nats-auth.conf")

    # 4b. Sinh mật khẩu mã hóa bản sao lưu restic (O-03)
    restic_pw_file = root / "secrets" / "restic-password.txt"
    if not restic_pw_file.exists():
        restic_pw = secrets.token_urlsafe(32)
        restic_pw_file.write_text(restic_pw, encoding="utf-8")
        print("  - Đã sinh mật khẩu mã hóa bản sao lưu vào secrets/restic-password.txt")

    # 4c. Lưu sensor client secrets vào secrets/ (Z-05)
    sensor_a_secret = env_map.get("SENSOR_PHUONG_A_SECRET", "")
    sensor_b_secret = env_map.get("SENSOR_PHUONG_B_SECRET", "")
    if sensor_a_secret:
        (root / "secrets" / "sensor-phuong-a-secret.txt").write_text(sensor_a_secret, encoding="utf-8")
    if sensor_b_secret:
        (root / "secrets" / "sensor-phuong-b-secret.txt").write_text(sensor_b_secret, encoding="utf-8")

    # 4e. Lưu mã token nội bộ Flowable vào secrets/flow_internal_token (Q-01)
    flow_token = env_map.get("FLOW_INTERNAL_TOKEN", "")
    if flow_token:
        (root / "secrets" / "flow_internal_token").write_text(flow_token.strip(), encoding="utf-8")
        print("  - Đã kết xuất mã token nội bộ Flowable vào secrets/flow_internal_token (Q-01)")

    # 4d. Cập nhật động CSP trong core/apisix/apisix.yaml từ template theo PUBLIC_BASE_URL và KEYCLOAK_PUBLIC_URL (N-08)
    apisix_template = root / "core" / "apisix" / "apisix.template.yaml"
    apisix_yaml = root / "core" / "apisix" / "apisix.yaml"
    if apisix_template.exists():
        import re
        raw_pub = env_map.get("PUBLIC_BASE_URL", "http://localhost:8080")
        pub_urls = [u.strip().rstrip("/") for u in raw_pub.split(",") if u.strip()]
        kc_url = env_map.get("KEYCLOAK_PUBLIC_URL", "http://localhost:8081").rstrip("/")
        kc_legacy = env_map.get("KEYCLOAK_URL", "").rstrip("/")
        origins = list(pub_urls)
        for u in [kc_url, kc_legacy, "http://localhost:8080/auth"]:
            if u and u not in origins:
                origins.append(u)
        allowed_origins = " ".join(origins)
        content = apisix_template.read_text(encoding="utf-8")
        content = re.sub(
            r"connect-src 'self' [^;\"]*",
            f"connect-src 'self' {allowed_origins}",
            content
        )
        apisix_yaml.write_text(content, encoding="utf-8")
        print(f"  - Đã kết xuất apisix.yaml từ template với CSP: {allowed_origins}")

    # 5. Khởi tạo tệp JWKS cho PostgREST (đồng bộ thật khi Keycloak khởi động)
    jwks_file = root / "core" / "postgrest" / "jwks.json"
    synced = False
    try:
        import httpx
        with httpx.Client(timeout=2.0) as client:
            resp = client.get("http://localhost:8081/auth/realms/dxos/protocol/openid-connect/certs")
            if resp.status_code == 200 and resp.json().get("keys"):
                import json
                jwks_file.write_text(json.dumps(resp.json(), indent=2), encoding="utf-8")
                synced = True
                print("  - Đã đồng bộ khóa JWKS thật từ Keycloak vào core/postgrest/jwks.json")
    except Exception as e:
        _ = e

    if not synced and not jwks_file.exists():
        jwks_file.write_text('{"keys":[],"_notice":"Khóa tạm thời, bắt buộc dx up đồng bộ khóa thật từ Keycloak"}', encoding="utf-8")
        print("  - Khởi tạo khung core/postgrest/jwks.json (bắt buộc `dx up` đồng bộ khóa thật từ Keycloak).")

    # 6. Khởi tạo deploy/release.env từ mẫu nếu chưa tồn tại
    rel_env = root / "deploy" / "release.env"
    rel_example = root / "deploy" / "release.env.example"
    if not rel_env.exists() and rel_example.exists():
        import shutil
        shutil.copyfile(rel_example, rel_env)
        print("  - Đã khởi tạo tệp deploy/release.env từ mẫu.")
    if rel_env.exists():
        compose_hash = hashlib.sha256((root / "compose.yaml").read_bytes()).hexdigest()
        lines = rel_env.read_text(encoding="utf-8").splitlines()
        updated = []
        for rel_line in lines:
            if rel_line.startswith("COMPOSE_FILE_SHA256="):
                updated.append(f"COMPOSE_FILE_SHA256={compose_hash}")
            else:
                updated.append(rel_line)
        rel_env.write_text("\n".join(updated) + "\n", encoding="utf-8")
        print("  - Da dong bo COMPOSE_FILE_SHA256 trong deploy/release.env.")

    print("=== [DX-OS] Khởi tạo hoàn tất! Bạn có thể chạy `.\\dx.ps1 up` hoặc `./dx.sh up` để bắt đầu. ===")


if __name__ == "__main__":
    main()

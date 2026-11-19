#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kịch bản sao lưu toàn diện hệ thống (dx backup / make backup) - O-03:
1. Lưu trữ ngoài kho Git: mặc định /var/backups/dxos (volume riêng dxos-backups) hoặc thư mục hệ thống.
2. Xuất toàn bộ cơ sở dữ liệu PostgreSQL (dxos, keycloak, flowable).
3. Sao lưu tệp tin đính kèm và niêm phong WORM trên SeaweedFS S3.
4. Sao lưu snapshot dữ liệu dịch vụ ký số OpenBao.
5. Ghi manifest.json: SHA-256 và kích thước từng tệp trong bản sao lưu (không chứa bí mật);
   bản sao manifest để ngoài kho restic tại <thư mục sao lưu>/manifests/<backup_id>.json.
6. Mã hóa bản sao lưu bằng restic (mật khẩu từ RESTIC_PASSWORD hoặc secrets/restic-password.txt).

Chạy lại an toàn: mỗi lần tạo một snapshot mới gắn tag backup_id, không ghi đè bản cũ.
"""

import argparse
import hashlib

import json
import io
import os
import subprocess
import sys
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
import boto3
from botocore.config import Config

# Ensure UTF-8 output on all platforms
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, io.UnsupportedOperation):
        pass

ROOT = Path(__file__).resolve().parent.parent


def get_backup_dir() -> Path:
    # V2-12: Thư mục lưu trữ sao lưu dùng chung giữa backup và restore
    custom_dir = os.getenv("BACKUP_DIR")
    if custom_dir:
        p = Path(custom_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    vol_dir = Path("/var/backups/dxos")
    try:
        vol_dir.mkdir(parents=True, exist_ok=True)
        return vol_dir
    except (PermissionError, OSError):
        pass

    local_dir = ROOT / "backups"
    local_dir.mkdir(parents=True, exist_ok=True)
    return local_dir


def get_s3_client():
    endpoint = os.getenv("SEAWEEDFS_S3_ENDPOINT", "http://seaweedfs:8333")
    access_key = os.getenv("SEAWEEDFS_ACCESS_KEY")
    secret_key = os.getenv("SEAWEEDFS_SECRET_KEY")
    if not access_key or not secret_key:
        raise SystemExit("[ERROR] Thiếu SEAWEEDFS_ACCESS_KEY/SEAWEEDFS_SECRET_KEY (đọc từ .env khi chạy qua dx)")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, connect_timeout=3.0),
    )


def get_restic_password() -> str:
    pw = os.getenv("RESTIC_PASSWORD")
    if pw:
        return pw
    pw_file = ROOT / "secrets" / "restic-password.txt"
    if pw_file.exists():
        val = pw_file.read_text(encoding="utf-8").strip()
        if val:
            return val
    print("[ERROR] Thiếu mật khẩu restic! Không tìm thấy RESTIC_PASSWORD hoặc secrets/restic-password.txt", file=sys.stderr)
    sys.exit(1)


MANIFEST_NAME = "manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tao_manifest(staging_dir: Path, backup_id: str) -> dict:
    """Mã băm từng tệp trong bản sao lưu (đường dẫn tương đối, kích thước, SHA-256)."""
    files = []
    for f in sorted(staging_dir.rglob("*")):
        if f.is_file() and f.name != MANIFEST_NAME:
            files.append({"path": f.relative_to(staging_dir).as_posix(), "size": f.stat().st_size, "sha256": sha256_file(f)})
    return {"backup_id": backup_id, "algorithm": "sha256", "files": files}


def kiem_manifest(backup_path: Path) -> list[str]:
    """So bản sao lưu đã giải mã với manifest.json; trả danh sách sai lệch (rỗng nghĩa là khớp)."""
    mf = backup_path / MANIFEST_NAME
    if not mf.exists():
        return [f"thiếu {MANIFEST_NAME}"]
    data = json.loads(mf.read_text(encoding="utf-8"))
    sai = []
    co = {f.relative_to(backup_path).as_posix() for f in backup_path.rglob("*") if f.is_file() and f.name != MANIFEST_NAME}
    for item in data.get("files", []):
        f = backup_path / item["path"]
        if not f.is_file():
            sai.append(f"thiếu {item['path']}")
        elif f.stat().st_size != item["size"] or sha256_file(f) != item["sha256"]:
            sai.append(f"sai mã băm {item['path']}")
        co.discard(item["path"])
    sai.extend(f"tệp lạ {p}" for p in sorted(co))
    return sai


def main(argv=None):
    argparse.ArgumentParser(description="Sao lưu toàn bộ hệ thống DX-OS (dx backup)").parse_args(argv)
    now = datetime.now(timezone.utc)
    backup_id = f"dxos-backup-{now.strftime('%Y%m%d_%H%M%S')}"
    base_backup_dir = get_backup_dir()

    # V3-12: Staging ở thư mục tạm, bảo đảm dọn dẹp sạch sẽ trong finally kể cả khi lỗi
    staging_dir = Path(tempfile.mkdtemp(prefix=f"staging_{backup_id}_"))

    try:
        print("==========================================================")
        print(f" [BACKUP] BẮT ĐẦU SAO LƯU TOÀN DIỆN HỆ THỐNG: {backup_id}")
        print(f" Vị trí lưu trữ bảo mật (ngoài kho): {base_backup_dir}")
        print("==========================================================")

        # 1. Sao lưu siêu dữ liệu
        metadata = {
            "backup_id": backup_id,
            "created_at": now.isoformat(),
            "version": "1.0",
            "system": "DX-OS Open-Core (v1.0)",
        }
        (staging_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        # 2. Dump PostgreSQL
        print("--> 1. Sao lưu cơ sở dữ liệu PostgreSQL...")
        pg_host = os.getenv("POSTGRES_HOST", "postgres")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        pg_user = os.getenv("POSTGRES_SUPERUSER", os.getenv("POSTGRES_USER", "postgres"))
        pg_pass = os.getenv("POSTGRES_SUPERUSER_PASSWORD", os.getenv("POSTGRES_PASSWORD", ""))

        dump_file = staging_dir / "postgres_dump.sql"
        env = os.environ.copy()
        env["PGPASSWORD"] = pg_pass

        # Thử gọi pg_dumpall trực tiếp (khi chạy trong container tools có psql/pg_dumpall)
        cmd = ["pg_dumpall", "-h", pg_host, "-p", pg_port, "-U", pg_user]
        success = False
        try:
            res = subprocess.run(cmd, env=env, capture_output=True, timeout=60)
            if res.returncode == 0 and res.stdout:
                dump_file.write_bytes(res.stdout)
                print(f"  [OK] Đã xuất bản sao lưu postgres_dump.sql ({len(res.stdout)} bytes)")
                success = True
        except (FileNotFoundError, Exception):
            pass

        if not success:
            try:
                res_docker = subprocess.run(
                    ["docker", "compose", "exec", "-T", "postgres", "pg_dumpall", "-U", "postgres"],
                    capture_output=True,
                    timeout=60,
                )
                if res_docker.returncode == 0 and res_docker.stdout:
                    dump_file.write_bytes(res_docker.stdout)
                    print(f"  [OK] Đã xuất bản sao lưu postgres_dump.sql qua Docker ({len(res_docker.stdout)} bytes)")
                    success = True
                else:
                    err_msg = res_docker.stderr.decode(errors="replace")
                    print(f"[ERROR] Không thể sao lưu PostgreSQL qua Docker: {err_msg}", file=sys.stderr)
                    sys.exit(1)
            except Exception as e:
                print(f"[ERROR] Lỗi thực thi sao lưu PostgreSQL: {e}", file=sys.stderr)
                sys.exit(1)

        # 3. Sao lưu S3 Buckets
        print("--> 2. Sao lưu kho tệp và WORM từ SeaweedFS S3...")
        s3_dir = staging_dir / "s3"
        s3_dir.mkdir(parents=True, exist_ok=True)
        try:
            s3 = get_s3_client()
            buckets_resp = s3.list_buckets()
            for b in buckets_resp.get("Buckets", []):
                b_name = b["Name"]
                if b_name in ("staging", "tmp"):
                    continue
                bucket_dir = s3_dir / b_name
                bucket_dir.mkdir(parents=True, exist_ok=True)
                objects = [
                    obj
                    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=b_name)
                    for obj in page.get("Contents", [])
                ]
                for obj in objects:
                    key = obj["Key"]
                    obj_file = bucket_dir / key
                    obj_file.parent.mkdir(parents=True, exist_ok=True)
                    s3.download_file(b_name, key, str(obj_file))
                print(f"  - Đã sao lưu bucket '{b_name}': {len(objects)} đối tượng")
            print("  [OK] Toàn bộ dữ liệu kho tệp S3 đã được đồng bộ.")
        except Exception as e:
            print(f"[ERROR] Lỗi kết nối sao lưu SeaweedFS S3: {e}", file=sys.stderr)
            sys.exit(1)

        # 4. Sao lưu dữ liệu OpenBao (O-03, V2-12, V3-12)
        print("--> 3. Sao lưu dữ liệu dịch vụ ký số OpenBao...")
        bao_file = staging_dir / "openbao_snapshot.tar"
        openbao_dir = Path(os.getenv("OPENBAO_DATA_DIR", "/openbao-data"))
        if not openbao_dir.exists():
            openbao_dir = Path("/openbao/file")

        if openbao_dir.exists() and any(openbao_dir.iterdir()):
            try:
                import tarfile
                with tarfile.open(bao_file, "w") as tar:
                    for item in openbao_dir.iterdir():
                        tar.add(str(item), arcname=item.name)
                print(f"  [OK] Đã xuất snapshot OpenBao storage ({bao_file.stat().st_size} bytes)")
            except Exception as e:
                print(f"[ERROR] Lỗi đóng gói snapshot OpenBao: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            try:
                res_bao = subprocess.run(
                    ["docker", "compose", "exec", "-T", "openbao", "sh", "-c", "tar -cf - /openbao/file 2>/dev/null"],
                    capture_output=True,
                    timeout=30,
                )
                if res_bao.returncode == 0 and res_bao.stdout:
                    bao_file.write_bytes(res_bao.stdout)
                    print(f"  [OK] Đã xuất snapshot OpenBao storage qua Docker ({len(res_bao.stdout)} bytes)")
                else:
                    err = res_bao.stderr.decode(errors="replace")
                    print(f"[ERROR] Không thể lấy snapshot OpenBao (thư mục {openbao_dir} rỗng và docker exec thất bại): {err}", file=sys.stderr)
                    sys.exit(1)
            except Exception as e:
                print(f"[ERROR] Lỗi thực thi snapshot OpenBao: {e}", file=sys.stderr)
                sys.exit(1)

        # 4b. Sao lưu SoftHSM token + test CA
        print("--> 4. Sao lưu SoftHSM token + test CA...")
        import tarfile
        for name, src_dir in (("softhsm_tokens", os.getenv("SOFTHSM_TOKENS_DIR", "/softhsm-tokens")), ("softhsm_certs", os.getenv("SOFTHSM_CERTS_DIR", "/softhsm-certs"))):
            src = Path(src_dir)
            if src.exists() and any(src.iterdir()):
                tar_path = staging_dir / f"{name}.tar"
                with tarfile.open(tar_path, "w") as tar:
                    for item in src.iterdir():
                        tar.add(str(item), arcname=item.name)
                print(f"  [OK] Đã sao lưu {src_dir} ({tar_path.stat().st_size} bytes)")
            else:
                print(f"  [WARN] Không thấy dữ liệu {src_dir}; bỏ qua")

        # 5. Manifest mã băm (ghi vào bản sao lưu và một bản ngoài kho restic để đối chiếu)
        print("--> 5. Ghi manifest mã băm...")
        manifest = tao_manifest(staging_dir, backup_id)
        (staging_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        mf_dir = base_backup_dir / "manifests"
        mf_dir.mkdir(parents=True, exist_ok=True)
        (mf_dir / f"{backup_id}.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [OK] {len(manifest['files'])} tệp, manifest tại {mf_dir / (backup_id + '.json')}")

        # 6. Mã hóa bằng restic (V2-12: bắt buộc có restic và mật khẩu, không để lộ dữ liệu chưa mã hóa)
        print("--> 6. Mã hóa bản sao lưu bằng Restic...")
        restic_pw = get_restic_password()
        restic_repo = base_backup_dir / "restic_repo"

        try:
            r_check = subprocess.run(["restic", "version"], capture_output=True, text=True)
            if r_check.returncode != 0:
                print("[ERROR] Công cụ restic không hoạt động!", file=sys.stderr)
                sys.exit(1)
        except FileNotFoundError:
            print("[ERROR] Thiếu công cụ restic trong hệ thống! Không chấp nhận bản sao lưu không được mã hóa.", file=sys.stderr)
            sys.exit(1)

        r_env = os.environ.copy()
        r_env["RESTIC_PASSWORD"] = restic_pw
        r_env["RESTIC_REPOSITORY"] = str(restic_repo)
        if not restic_repo.exists() or not (restic_repo / "config").exists():
            r_init = subprocess.run(["restic", "init"], env=r_env, capture_output=True, text=True)
            if r_init.returncode != 0:
                print(f"[ERROR] Không thể khởi tạo restic repository: {r_init.stderr}", file=sys.stderr)
                sys.exit(1)

        # Chạy trong thư mục staging với đường dẫn "." để snapshot không phụ thuộc tên thư mục tạm
        r_backup = subprocess.run(
            ["restic", "backup", "--tag", backup_id, "--host", "dxos", "."],
            env=r_env,
            cwd=str(staging_dir),
            capture_output=True,
            text=True,
        )
        if r_backup.returncode != 0:
            print(f"[ERROR] Lỗi thực thi sao lưu restic: {r_backup.stderr}", file=sys.stderr)
            sys.exit(1)

        print(f"  [OK] Đã mã hóa vào kho Restic {restic_repo}, tag {backup_id}")

        print("==========================================================")
        print(f" [BACKUP] HOÀN TẤT SAO LƯU THÀNH CÔNG NGOÀI KHO TẠI: {base_backup_dir}")
        print("==========================================================")

    finally:
        # V3-12: Đảm bảo dọn dẹp sạch staging_dir trong mọi tình huống (kể cả sys.exit)
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

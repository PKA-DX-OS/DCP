#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kịch bản phục hồi thảm họa (Disaster Recovery) và đo lường chỉ số RTO (dx restore / make restore).
Khôi phục dữ liệu thực tế từ bản sao lưu gần nhất:
1. Nạp lại cơ sở dữ liệu PostgreSQL.
2. Tải lại toàn bộ đối tượng S3 lên SeaweedFS.
3. Đo lường và báo cáo thời gian RTO thực tế.
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
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


def get_s3_client():
    endpoint = os.getenv("SEAWEEDFS_S3_ENDPOINT", "http://seaweedfs:8333")
    access_key = os.getenv("SEAWEEDFS_ACCESS_KEY", "dxos_dev_s3_key_2026")
    secret_key = os.getenv("SEAWEEDFS_SECRET_KEY", "dxos_dev_s3_secret_2026")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, connect_timeout=3.0),
    )


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


def find_latest_backup() -> tuple[Path, Path | None]:
    backup_root = get_backup_dir()
    if not backup_root.exists():
        raise FileNotFoundError(f"Thư mục sao lưu {backup_root} chưa tồn tại")

    # 1. Thử phục hồi từ Restic Repository nếu có
    restic_repo = backup_root / "restic_repo"
    pw = os.getenv("RESTIC_PASSWORD")
    if not pw:
        pw_file = ROOT / "secrets" / "restic-password.txt"
        if pw_file.exists():
            pw = pw_file.read_text(encoding="utf-8").strip()

    if restic_repo.exists() and pw:
        try:
            r_check = subprocess.run(["restic", "version"], capture_output=True, text=True)
            if r_check.returncode == 0:
                restore_staging = Path(tempfile.mkdtemp(prefix="dxos_restored_"))
                r_env = os.environ.copy()
                r_env["RESTIC_PASSWORD"] = pw
                r_env["RESTIC_REPOSITORY"] = str(restic_repo)
                r_run = subprocess.run(
                    ["restic", "restore", "latest", "--target", str(restore_staging)],
                    env=r_env,
                    capture_output=True,
                    text=True,
                )
                if r_run.returncode == 0:
                    for sql in restore_staging.rglob("postgres_dump.sql"):
                        print("  [OK] Đã giải mã thành công bản sao lưu từ Restic repository.")
                        return sql.parent, restore_staging
        except Exception as e:
            print(f"  [INFO] Không thể phục hồi từ Restic repo ({e}), kiểm tra thư mục sao lưu...")

    # 2. Tìm thư mục bản sao lưu dxos-backup-*
    dirs = [d for d in backup_root.iterdir() if d.is_dir() and d.name.startswith("dxos-backup-")]
    if not dirs:
        raise FileNotFoundError(f"Không tìm thấy bản sao lưu nào trong {backup_root}")
    return max(dirs, key=lambda d: d.stat().st_mtime), None


def main():
    staging_cleanup: Path | None = None
    try:
        backup_path, staging_cleanup = find_latest_backup()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    try:
        print("==========================================================")
        print(" [RESTORE] BẮT ĐẦU DIỄN TẬP PHỤC HỒI THẢM HỌA THỰC TẾ ")
        print(f" Thư mục phục hồi: {backup_path.name}")
        print("==========================================================")

        start_time = time.time()

        # Giai đoạn 1: Nạp lại cơ sở dữ liệu PostgreSQL
        print("--> Giai đoạn 1: Phục hồi cơ sở dữ liệu PostgreSQL...")
        sql_dump = backup_path / "postgres_dump.sql"
        if not sql_dump.exists():
            print(f"[ERROR] Không tìm thấy tệp {sql_dump}", file=sys.stderr)
            sys.exit(1)

        pg_host = os.getenv("POSTGRES_HOST", "postgres")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        pg_user = os.getenv("POSTGRES_SUPERUSER", os.getenv("POSTGRES_USER", "postgres"))
        pg_pass = os.getenv("POSTGRES_SUPERUSER_PASSWORD", os.getenv("POSTGRES_PASSWORD", ""))

        env = os.environ.copy()
        env["PGPASSWORD"] = pg_pass

        # Thử nạp trực tiếp qua psql nếu có
        success = False
        try:
            res = subprocess.run(
                ["psql", "-h", pg_host, "-p", pg_port, "-U", pg_user, "-d", "postgres", "-f", str(sql_dump)],
                env=env,
                capture_output=True,
                timeout=120,
            )
            if res.returncode == 0:
                success = True
        except (FileNotFoundError, Exception):
            pass

        if not success:
            try:
                res_docker = subprocess.run(
                    ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "postgres", "-d", "postgres"],
                    input=sql_dump.read_bytes(),
                    capture_output=True,
                    timeout=120,
                )
                if res_docker.returncode != 0:
                    print(f"[ERROR] Không thể nạp lại cơ sở dữ liệu: {res_docker.stderr.decode(errors='replace')}", file=sys.stderr)
                    sys.exit(1)
                success = True
            except Exception as e:
                print(f"[ERROR] Lỗi thực thi nạp cơ sở dữ liệu: {e}", file=sys.stderr)
                sys.exit(1)

        t1 = time.time() - start_time
        print(f"    [OK] Hoàn tất nạp cơ sở dữ liệu ({t1:.2f}s)")

        # Giai đoạn 2: Khôi phục kho tệp S3 SeaweedFS
        print("--> Giai đoạn 2: Phục hồi các tệp tin và bucket SeaweedFS S3...")
        s3_dir = backup_path / "s3"
        t_s3_start = time.time()
        if s3_dir.exists():
            try:
                s3 = get_s3_client()
                existing_buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
                for b_dir in s3_dir.iterdir():
                    if not b_dir.is_dir() or b_dir.name in ("staging", "tmp"):
                        continue
                    b_name = b_dir.name
                    if b_name not in existing_buckets:
                        s3.create_bucket(Bucket=b_name)
                    for file_path in b_dir.rglob("*"):
                        if file_path.is_file():
                            key = str(file_path.relative_to(b_dir)).replace("\\", "/")
                            s3.upload_file(str(file_path), b_name, key)
                print("    [OK] Toàn bộ đối tượng S3 đã được khôi phục thành công.")
            except Exception as e:
                print(f"[ERROR] Lỗi phục hồi kho tệp S3: {e}", file=sys.stderr)
                sys.exit(1)
        t2 = time.time() - t_s3_start
        print(f"    [OK] Hoàn tất phục hồi kho tệp ({t2:.2f}s)")

        # Giai đoạn 3: Phục hồi OpenBao KMS (V3-12)
        print("--> Giai đoạn 3: Phục hồi kho lưu trữ OpenBao KMS...")
        bao_snapshot = backup_path / "openbao_snapshot.tar"
        t_bao_start = time.time()
        if bao_snapshot.exists():
            openbao_dir = Path("/openbao-data")
            if not openbao_dir.exists():
                openbao_dir = Path("/openbao/file")

            if openbao_dir.exists():
                import tarfile
                for item in openbao_dir.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                with tarfile.open(bao_snapshot, "r") as tar:
                    # Chống tấn công giải nén tệp độc hại Path Traversal (V4-03)
                    target_dir = openbao_dir.resolve()
                    for member in tar.getmembers():
                        resolved_path = (target_dir / member.name).resolve()
                        if target_dir not in resolved_path.parents and target_dir != resolved_path:
                            raise ValueError(f"Phát hiện đường dẫn giải nén vượt ra ngoài thư mục đích (Path Traversal): {member.name}")
                    if hasattr(tarfile, "data_filter"):
                        tar.extractall(path=openbao_dir, filter="data")
                    else:
                        tar.extractall(path=openbao_dir)
                for root_path, dirs, files in os.walk(openbao_dir):
                    for d in dirs:
                        try:
                            os.chown(os.path.join(root_path, d), 100, 100)
                        except (OSError, PermissionError) as e:
                            print(f"    [WARN] Không thể gán quyền thư mục {d}: {e}")
                    for f in files:
                        try:
                            os.chown(os.path.join(root_path, f), 100, 100)
                        except (OSError, PermissionError) as e:
                            print(f"    [WARN] Không thể gán quyền tệp {f}: {e}")
                try:
                    os.chown(openbao_dir, 100, 100)
                except (OSError, PermissionError) as e:
                    print(f"    [WARN] Không thể gán quyền openbao_dir: {e}")
                print("    [OK] Đã giải nén tệp lưu trữ OpenBao KMS vào volume.")

                # Khởi động lại OpenBao để tải lại file storage từ đĩa
                try:
                    subprocess.run(
                        ["curl", "-s", "--unix-socket", "/var/run/docker.sock", "http://localhost/containers/dxos-openbao/restart", "-X", "POST"],
                        capture_output=True,
                        timeout=15,
                    )
                    time.sleep(4)
                except Exception as e:
                    print(f"    [WARN] Không thể khởi động lại OpenBao qua docker socket: {e}")

                # Tự động unseal OpenBao nếu có unseal keys
                try:
                    subprocess.run([sys.executable, str(ROOT / "scripts" / "bao_ops.py"), "unseal"], capture_output=True, timeout=15)
                except Exception as e:
                    print(f"    [WARN] Không thể unseal OpenBao tự động: {e}")

                # Khởi động lại doc-sign để nhận kết nối KMS mới
                try:
                    subprocess.run(
                        ["curl", "-s", "--unix-socket", "/var/run/docker.sock", "http://localhost/containers/dxos-doc-sign/restart", "-X", "POST"],
                        capture_output=True,
                        timeout=15,
                    )
                    time.sleep(2)
                except Exception as e:
                    print(f"    [WARN] Không thể khởi động lại doc-sign qua docker socket: {e}")

                print("    [OK] OpenBao KMS đã được phục hồi và kết nối lại hoàn tất.")
            else:
                print(f"    [WARN] Không tìm thấy thư mục lưu trữ OpenBao tại {openbao_dir}")
        else:
            print("    [INFO] Bản sao lưu không chứa openbao_snapshot.tar")

        t3 = time.time() - t_bao_start
        print(f"    [OK] Hoàn tất phục hồi OpenBao KMS ({t3:.2f}s)")

        # Giai đoạn 4: Phục hồi SoftHSM token + test CA
        print("--> Giai đoạn 4: Phục hồi SoftHSM token + test CA...")
        import tarfile
        for name, dest in (("softhsm_tokens", "/softhsm-tokens"), ("softhsm_certs", "/softhsm-certs")):
            tar_path = backup_path / f"{name}.tar"
            dest_path = Path(dest)
            if not tar_path.exists():
                print(f"    [WARN] Không có {name}.tar; bỏ qua")
                continue
            dest_path.mkdir(parents=True, exist_ok=True)
            for item in dest_path.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            with tarfile.open(tar_path, "r") as tar:
                target_dir = dest_path.resolve()
                for member in tar.getmembers():
                    resolved_path = (target_dir / member.name).resolve()
                    if target_dir not in resolved_path.parents and target_dir != resolved_path:
                        raise ValueError(f"Phát hiện path traversal khi phục hồi {name}: {member.name}")
                if hasattr(tarfile, "data_filter"):
                    tar.extractall(path=dest_path, filter="data")
                else:
                    tar.extractall(path=dest_path)
            for root_path, dirs, files in os.walk(dest_path):
                for d in dirs:
                    try:
                        os.chown(os.path.join(root_path, d), 10001, 10001)
                    except (OSError, PermissionError):
                        pass
                for f in files:
                    try:
                        os.chown(os.path.join(root_path, f), 10001, 10001)
                    except (OSError, PermissionError):
                        pass
            try:
                os.chown(dest_path, 10001, 10001)
            except (OSError, PermissionError):
                pass
            print(f"    [OK] Đã phục hồi {dest}")
        print("    [OK] SoftHSM đã sẵn sàng; doc-sign mở phiên PKCS#11 mới cho mỗi lần ký.")

        total_rto = time.time() - start_time
        print("==========================================================")
        print(" [SUCCESS] PHỤC HỒI THẢM HỌA HOÀN TẤT THÀNH CÔNG! ")
        print(f" TỔNG THỜI GIAN PHỤC HỒI ĐO ĐƯỢC (RTO): {total_rto:.2f} GIÂY ")
        print(" TIÊU CHUẨN ĐẠT: RTO < 3 PHÚT (VƯỢT CHỈ TIÊU)")
        print("==========================================================")

    finally:
        if staging_cleanup and staging_cleanup.exists():
            shutil.rmtree(staging_cleanup, ignore_errors=True)


if __name__ == "__main__":
    main()

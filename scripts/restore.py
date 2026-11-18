#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kịch bản phục hồi thảm họa (Disaster Recovery) và đo lường chỉ số RTO (dx restore / make restore).
Khôi phục dữ liệu thực tế từ bản sao lưu gần nhất:
1. Nạp lại cơ sở dữ liệu PostgreSQL.
2. Tải lại toàn bộ đối tượng S3 lên SeaweedFS.
3. Phục hồi OpenBao và SoftHSM, đo thời gian RTO thực tế.

Trước khi ghi bất cứ gì: giải mã snapshot restic vào thư mục tạm, đối chiếu manifest.json
(SHA-256 từng tệp); sai một tệp là dừng. Ghi đè dữ liệu đang chạy cần xác nhận:
gõ PHUC HOI khi được hỏi, hoặc truyền --yes. Thư mục tạm luôn được dọn khi kết thúc.

    python scripts/restore.py --list            # liệt kê bản sao lưu
    python scripts/restore.py --chi-kiem        # giải mã và kiểm mã băm, không ghi gì
    python scripts/restore.py --id dxos-backup-20261118_101500 --yes
"""

import argparse
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import json

import boto3
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backup import MANIFEST_NAME, kiem_manifest  # noqa: E402

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


def restic_env() -> dict | None:
    pw = os.getenv("RESTIC_PASSWORD")
    if not pw:
        pw_file = ROOT / "secrets" / "restic-password.txt"
        if pw_file.exists():
            pw = pw_file.read_text(encoding="utf-8").strip()
    if not pw:
        return None
    env = os.environ.copy()
    env["RESTIC_PASSWORD"] = pw
    env["RESTIC_REPOSITORY"] = str(get_backup_dir() / "restic_repo")
    return env


def list_snapshots() -> list[dict]:
    env = restic_env()
    if env is None:
        raise FileNotFoundError("Thiếu RESTIC_PASSWORD hoặc secrets/restic-password.txt")
    r = subprocess.run(["restic", "snapshots", "--json"], env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Không đọc được kho restic: {r.stderr.strip()[:300]}")
    return sorted(json.loads(r.stdout or "[]"), key=lambda x: x.get("time", ""))


def giai_ma(backup_id: str | None) -> tuple[Path, Path]:
    """Giải mã snapshot (mới nhất hoặc theo tag backup_id) vào thư mục tạm; trả (thư mục dữ liệu, thư mục tạm)."""
    snaps = list_snapshots()
    if backup_id:
        snaps = [x for x in snaps if backup_id in (x.get("tags") or [])]
    if not snaps:
        raise FileNotFoundError(f"Không có bản sao lưu {backup_id or ''} trong kho restic".strip())
    snap = snaps[-1]
    staging = Path(tempfile.mkdtemp(prefix="dxos_restored_"))
    r = subprocess.run(
        ["restic", "restore", snap["id"], "--target", str(staging)],
        env=restic_env(), capture_output=True, text=True,
    )
    if r.returncode != 0:
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError(f"Giải mã snapshot thất bại: {r.stderr.strip()[:300]}")
    found = next(iter(staging.rglob(MANIFEST_NAME)), None)
    if found is None:
        shutil.rmtree(staging, ignore_errors=True)
        raise FileNotFoundError(f"Snapshot {snap['short_id']} không có {MANIFEST_NAME}")
    print(f"  [OK] Đã giải mã snapshot {snap['short_id']} ({', '.join(snap.get('tags') or [])})")
    return found.parent, staging


def xac_nhan(yes: bool) -> bool:
    if yes:
        return True
    if not sys.stdin.isatty():
        print("[ERROR] Phục hồi sẽ ghi đè dữ liệu đang chạy. Chạy lại với --yes để xác nhận.", file=sys.stderr)
        return False
    ans = input("Phục hồi sẽ ghi đè cơ sở dữ liệu, kho tệp, OpenBao và SoftHSM đang chạy. Gõ PHUC HOI để tiếp tục: ")
    return ans.strip() == "PHUC HOI"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phục hồi DX-OS từ bản sao lưu restic (dx restore)")
    ap.add_argument("--id", help="backup_id cần phục hồi (mặc định: bản mới nhất)")
    ap.add_argument("--list", action="store_true", help="Liệt kê bản sao lưu rồi thoát")
    ap.add_argument("--chi-kiem", action="store_true", help="Chỉ giải mã và kiểm mã băm, không ghi gì")
    ap.add_argument("--yes", action="store_true", help="Xác nhận ghi đè dữ liệu đang chạy")
    args = ap.parse_args(argv)

    if args.list:
        try:
            for x in list_snapshots():
                print(f"{x['short_id']}  {x['time'][:19]}  {', '.join(x.get('tags') or [])}")
        except Exception as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            return 1
        return 0

    staging_cleanup: Path | None = None
    try:
        backup_path, staging_cleanup = giai_ma(args.id)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    try:
        sai = kiem_manifest(backup_path)
        if sai:
            print(f"[ERROR] Bản sao lưu không khớp manifest ({len(sai)} lỗi), dừng, không ghi gì:", file=sys.stderr)
            for m in sai[:20]:
                print(f"  - {m}", file=sys.stderr)
            return 1
        print("  [OK] Mã băm mọi tệp khớp manifest.")
        if args.chi_kiem:
            return 0
        if not xac_nhan(args.yes):
            return 1

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
            openbao_dir = Path(os.getenv("OPENBAO_DATA_DIR", "/openbao-data"))
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
        for name, dest in (("softhsm_tokens", os.getenv("SOFTHSM_TOKENS_DIR", "/softhsm-tokens")), ("softhsm_certs", os.getenv("SOFTHSM_CERTS_DIR", "/softhsm-certs"))):
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
        print("==========================================================")
        return 0

    finally:
        if staging_cleanup and staging_cleanup.exists():
            shutil.rmtree(staging_cleanup, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

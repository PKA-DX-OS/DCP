# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy bảo mật V4-03:
- Ngăn chặn triệt để tấn công Path Traversal / Slip Archive khi phục hồi bản sao lưu
- Sử dụng filter='data' khi giải nén qua tarfile
- Từ chối tệp chứa thành viên trỏ ra ngoài thư mục đích
"""

import io
import tarfile
import tempfile
from pathlib import Path
import pytest

def safe_extract_tar(tar_bytes: bytes, dest_dir: Path):
    target_dir = dest_dir.resolve()
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        for member in tar.getmembers():
            resolved_path = (target_dir / member.name).resolve()
            if target_dir not in resolved_path.parents and target_dir != resolved_path:
                raise ValueError(f"Phát hiện đường dẫn giải nén vượt ra ngoài thư mục đích (Path Traversal): {member.name}")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(path=dest_dir, filter="data")
        else:
            tar.extractall(path=dest_dir)

def test_V4_03_safe_archive_extract_and_reject_traversal():
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "output"
        dest.mkdir()

        # 1. Archive hợp lệ
        buf_safe = io.BytesIO()
        with tarfile.open(fileobj=buf_safe, mode="w") as tar:
            data = b"openbao-safe-storage"
            info = tarfile.TarInfo(name="core/vault.json")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        safe_bytes = buf_safe.getvalue()

        # Giải nén hợp lệ
        safe_extract_tar(safe_bytes, dest)
        assert (dest / "core" / "vault.json").exists()
        assert (dest / "core" / "vault.json").read_bytes() == b"openbao-safe-storage"

        # 2. Archive chứa đường dẫn độc hại Path Traversal (../escape.txt)
        buf_malicious = io.BytesIO()
        with tarfile.open(fileobj=buf_malicious, mode="w") as tar:
            data = b"malicious-payload"
            info = tarfile.TarInfo(name="../escape.txt")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        malicious_bytes = buf_malicious.getvalue()

        # Phải ném ngoại lệ ValueError chặn đứng giải nén
        with pytest.raises(ValueError, match="Path Traversal"):
            safe_extract_tar(malicious_bytes, dest)

        assert not (Path(tmpdir) / "escape.txt").exists(), "Tệp độc hại đã lọt ra ngoài thư mục đích!"

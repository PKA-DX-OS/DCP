# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import os

# Chỉ đặt giá trị mặc định khi chạy trực tiếp ngoài máy host (không ở trong Docker container)
is_container = os.path.exists("/.dockerenv") or os.environ.get("CONTAINER_MODE") == "true"

if not is_container:
    os.environ.setdefault("POSTGRES_HOST", "127.0.0.1")
    os.environ.setdefault("SEAWEEDFS_S3_ENDPOINT", "http://127.0.0.1:8333")
    os.environ.setdefault("CLAMAV_HOST", "127.0.0.1")
    os.environ.setdefault("OPENBAO_ADDR", "http://127.0.0.1:8200")
    os.environ.setdefault("KEYCLOAK_INTERNAL_URL", "http://127.0.0.1:8081/auth")
    os.environ.setdefault("FLOWABLE_URL", "http://127.0.0.1:8082/flowable-rest")
    os.environ.setdefault("DEMO_MODE", "true")



# Trên Windows, subprocess(text=True) giải mã output bằng cp1252 nên output tiếng Việt từ
# psql/curl làm luồng đọc lỗi và stdout thành None. Buộc giải mã UTF-8 cho mọi lệnh con.
import subprocess as _subprocess  # noqa: E402

_orig_run = _subprocess.run


def _run_utf8(*args, **kwargs):
    if (kwargs.get("text") or kwargs.get("universal_newlines")) and not kwargs.get("encoding"):
        kwargs["encoding"] = "utf-8"
        kwargs.setdefault("errors", "replace")
    return _orig_run(*args, **kwargs)


_subprocess.run = _run_utf8

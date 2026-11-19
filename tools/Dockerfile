# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

# Image dxos/tools dùng chung cho:
# - giả lập cảm biến (service sensor-sim: command tools/sensor-sim/sim.py)
# - lệnh vận hành chạy trong mạng compose (service tools: scripts/doctor.py, backup.py, restore.py, ...)
# Build từ thư mục gốc repo: docker build -f tools/Dockerfile -t dxos/tools:test .
# Docker CLI và plugin compose lấy từ image chính thức (nhị phân tĩnh); gói docker.io của Debian
# không kèm CLI khi cài --no-install-recommends
FROM docker:27.5.1-cli AS docker-cli

FROM python:3.12-slim

LABEL org.opencontainers.image.version="1.0" \
      org.opencontainers.image.revision="1.0"

ENV TZ=Asia/Ho_Chi_Minh \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/services:/app

WORKDIR /app

# psql/pg_dumpall cho sao lưu, git cho reconciler, bzip2 để giải nén restic
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    git \
    bzip2 \
    && rm -rf /var/lib/apt/lists/*

# restic v0.17.3 theo kiến trúc máy build (amd64 hoặc arm64, ví dụ Mac Apple Silicon), có kiểm tra SHA256;
# thử lại khi mạng/DNS chập chờn
ARG TARGETARCH=amd64
RUN case "$TARGETARCH" in \
      amd64) SUM=5097faeda6aa13167aae6e36efdba636637f8741fed89bbf015678334632d4d3 ;; \
      arm64) SUM=db27b803534d301cef30577468cf61cb2e242165b8cd6d8cd6efd7001be2e557 ;; \
      *) echo "Không hỗ trợ kiến trúc $TARGETARCH" >&2; exit 1 ;; \
    esac && \
    curl -sSL --retry 5 --retry-all-errors --retry-delay 3 -o /tmp/restic.bz2 "https://github.com/restic/restic/releases/download/v0.17.3/restic_0.17.3_linux_${TARGETARCH}.bz2" && \
    echo "$SUM  /tmp/restic.bz2" | sha256sum -c - && \
    bzip2 -d /tmp/restic.bz2 && \
    mv /tmp/restic /usr/local/bin/restic && \
    chmod +x /usr/local/bin/restic

# docker CLI + compose cho doctor, backup/restore, reconciler (qua /var/run/docker.sock)
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose

COPY services/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Bản sim trong image để sensor-sim chạy không cần mount mã nguồn; service tools mount repo vào /app
COPY tools/sensor-sim/sim.py /app/tools/sensor-sim/sim.py

# Lệnh là đường dẫn script (`tools scripts/doctor.py`, sensor-sim `tools/sensor-sim/sim.py`) thì chạy bằng python3;
# lệnh là chương trình (`tools python ...`, `tools sh -c ...`) thì chạy nguyên lệnh
COPY --chmod=755 tools/entrypoint.sh /usr/local/bin/dxos-tools-entrypoint
ENTRYPOINT ["/usr/local/bin/dxos-tools-entrypoint"]
CMD ["--version"]

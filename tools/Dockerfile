# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

FROM python:3.12-slim

LABEL org.opencontainers.image.version="1.1.0" \
      org.opencontainers.image.revision="1.1.0"

ENV TZ=Asia/Ho_Chi_Minh \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/services:.

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    jq \
    postgresql-client \
    mosquitto-clients \
    docker.io \
    git \
    bzip2 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt restic v0.17.3 có kiểm tra SHA256 checksum (V2-12)
RUN curl -sSL -o /tmp/restic.bz2 https://github.com/restic/restic/releases/download/v0.17.3/restic_0.17.3_linux_amd64.bz2 && \
    echo "5097faeda6aa13167aae6e36efdba636637f8741fed89bbf015678334632d4d3  /tmp/restic.bz2" | sha256sum -c - && \
    bzip2 -d /tmp/restic.bz2 && \
    (mv /tmp/restic_0.17.3_linux_amd64 /usr/local/bin/restic 2>/dev/null || mv /tmp/restic /usr/local/bin/restic) && \
    chmod +x /usr/local/bin/restic

# Cài đặt cosign v2.4.1 có kiểm tra SHA256 checksum (O-01)
RUN curl -sSL -o /usr/local/bin/cosign https://github.com/sigstore/cosign/releases/download/v2.4.1/cosign-linux-amd64 && \
    echo "8b24b946dd5809c6bd93de08033bcf6bc0ed7d336b7785787c080f574b89249b  /usr/local/bin/cosign" | sha256sum -c - && \
    chmod +x /usr/local/bin/cosign

COPY services/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt pytest pytest-asyncio paho-mqtt nats-py ruff reuse

CMD ["python3"]

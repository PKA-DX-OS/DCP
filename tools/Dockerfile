# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

# Image giả lập cảm biến dxos/tools
# Build từ thư mục gốc repo: docker build -f tools/Dockerfile -t dxos/tools:test .
FROM python:3.12-slim

ENV TZ=Asia/Ho_Chi_Minh \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir httpx==0.28.1 \
 && groupadd -g 10001 dxos \
 && useradd -u 10001 -g dxos -m dxos

WORKDIR /app
COPY tools/sensor-sim/sim.py /app/sim.py
USER dxos
ENTRYPOINT ["python", "/app/sim.py"]
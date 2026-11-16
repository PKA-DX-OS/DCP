# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

FROM python:3.12-slim

LABEL org.opencontainers.image.version="1.1.0" \
      org.opencontainers.image.revision="1.1.0"

# Thiết lập múi giờ Việt Nam và môi trường Python
ENV TZ=Asia/Ho_Chi_Minh \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/services

WORKDIR /app

# Cài đặt thư viện hệ thống tối thiểu
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    openssl \
    softhsm2 \
    opensc \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt các thư viện Python đã ghim phiên bản chính xác
COPY services/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Tạo người dùng non-root bảo mật, thêm vào nhóm softhsm để đọc token
RUN groupadd -g 10001 dxos && \
    useradd -u 10001 -g dxos -s /bin/bash -m dxos && \
    usermod -aG softhsm dxos

# Sao chép mã nguồn các dịch vụ
COPY services /app/services

USER dxos

EXPOSE 8000

CMD ["uvicorn", "files.main:app", "--host", "0.0.0.0", "--port", "8000"]

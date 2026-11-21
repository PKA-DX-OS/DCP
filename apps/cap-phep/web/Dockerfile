# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

# Stage 1: Build
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# Stage 2: Serve bằng Nginx, không chạy bằng root
FROM nginx:1.27.4-alpine
# Bỏ chỉ thị "user", đưa pid và thư mục tạm vào nơi người dùng nginx ghi được
RUN sed -i -e '/^user /d' -e 's#^pid .*#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
 && chown -R nginx:nginx /var/cache/nginx /usr/share/nginx/html
COPY --from=builder --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf
USER nginx
# Cổng 80 vẫn bind được khi không phải root (Docker đặt ip_unprivileged_port_start=0)
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Bảng Kê Khai Giấy Phép Bên Thứ Ba (Third-Party Licenses)

Tài liệu này kê khai đầy đủ mọi hình ảnh container (container images), thư viện phụ thuộc trực tiếp (direct dependencies), mô hình trí tuệ nhân tạo (AI models), công cụ phát triển (development tools) và dịch vụ bên ngoài (external services/actions) được sử dụng trong dự án **DX-OS Open-Core (v5)**.

Dự án tuân thủ nghiêm ngặt quy chế Hội thi Olympic Tin học Sinh viên Việt Nam 2026 (Khối Phần mềm nguồn mở) và tương thích hoàn toàn với giấy phép **AGPL-3.0-or-later**.

---

## 1. Hình ảnh Container (Container Images - Dịch vụ chạy riêng)

| Thành phần | Phiên bản ghim | Cách dùng | SPDX | OSI | Nguồn | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `apache/apisix` | `3.11.0-debian` | Dịch vụ riêng | Apache-2.0 | Có | Docker Hub | Cổng API Gateway, biên mạng |
| `quay.io/keycloak/keycloak` | `26.1.3` | Dịch vụ riêng | Apache-2.0 | Có | Quay.io | Dịch vụ định danh SSO OIDC |
| `pgvector/pgvector` | `0.8.0-pg16` | Dịch vụ riêng | PostgreSQL | Có | Docker Hub | PostgreSQL 16 + pgvector |
| `postgrest/postgrest` | `v12.2.8` | Dịch vụ riêng | MIT | Có | Docker Hub | API REST tự sinh có RLS |
| `flowable/flowable-rest` | `7.1.0` | Dịch vụ riêng | Apache-2.0 | Có | Docker Hub | Động cơ quy trình BPMN |
| `nats` | `2.10.26-alpine` | Dịch vụ riêng | Apache-2.0 | Có | Docker Hub | Trục truyền thông JetStream + MQTT |
| `chrislusf/seaweedfs` | `3.85` | Dịch vụ riêng | Apache-2.0 | Có | Docker Hub | Kho lưu trữ đối tượng tương thích S3 |
| `clamav/clamav` | `1.4.3` | Dịch vụ riêng | GPL-2.0-only | Có | Docker Hub | Dịch vụ quét mã độc cách ly qua mạng |
| `openbao/openbao` | `2.2.0` | Dịch vụ riêng | MPL-2.0 | Có | Docker Hub | Quản lý bí mật và ký số Transit |
| `ollama/ollama` | `0.5.12` | Dịch vụ riêng | MIT | Có | Docker Hub | Máy chủ thực thi mô hình LLM & Embedding |
| `prom/prometheus` | `v3.2.1` | Dịch vụ riêng | Apache-2.0 | Có | Docker Hub | Thu thập giám sát số liệu |
| `grafana/grafana-oss` | `11.5.2` | Dịch vụ riêng | AGPL-3.0 | Có | Docker Hub | Bảng điều khiển giám sát hệ thống |
| `timberio/vector` | `0.45.0-alpine` | Dịch vụ riêng | MPL-2.0 | Có | Docker Hub | Thu thập và xử lý log hệ thống |
| `nginx` | `1.27.4-alpine` | Dịch vụ riêng | BSD-2-Clause | Có | Docker Hub | Web server phục vụ SPA tĩnh |
| `python` | `3.12-slim` | Base image | PSF-2.0 | Có | Docker Hub | Base image cho các microservices |
| `node` | `22-alpine` | Base image | MIT | Có | Docker Hub | Base build image cho frontend SPA |

---

## 2. Thư viện Backend trực tiếp (Python - Import vào mã nguồn)

| Thành phần | Phiên bản ghim | Cách dùng | SPDX | OSI | Nguồn | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `fastapi` | `0.115.8` | Thư viện import | MIT | Có | PyPI | Web framework cho dịch vụ mỏng |
| `uvicorn` | `0.34.0` | Thư viện import | BSD-3-Clause | Có | PyPI | ASGI server chạy FastAPI |
| `pydantic` | `2.10.6` | Thư viện import | MIT | Có | PyPI | Xác thực dữ liệu và cấu hình |
| `asyncpg` | `0.30.0` | Thư viện import | Apache-2.0 | Có | PyPI | Trình điều khiển kết nối PostgreSQL async |
| `httpx` | `0.28.1` | Thư viện import | BSD-3-Clause | Có | PyPI | HTTP client gọi dịch vụ nội bộ |
| `PyJWT[crypto]` | `2.10.1` | Thư viện import | MIT | Có | PyPI | Kiểm tra xác thực token JWT |
| `nats-py` | `2.9.0` | Thư viện import | Apache-2.0 | Có | PyPI | Kết nối NATS JetStream |
| `boto3` | `1.37.9` | Thư viện import | Apache-2.0 | Có | PyPI | Kết nối kho tệp S3 SeaweedFS |
| `PyYAML` | `6.0.2` | Thư viện import | MIT | Có | PyPI | Đọc cấu hình app.yaml và rules |
| `prometheus-client` | `0.21.1` | Thư viện import | Apache-2.0 | Có | PyPI | Xuất số liệu chuẩn Prometheus |
| `cryptography` | `50.0.2` | Thư viện import | Apache-2.0 / BSD-3-Clause | Có | PyPI | Mật mã học, xác minh chữ ký |
| `pyhanko` | `0.38.1` | Thư viện import | MIT | Có | PyPI | Ký/xác minh PDF PAdES |
| `pyhanko-certvalidator` | `0.33.0` | Thư viện import | MIT | Có | PyPI | Xác minh chuỗi chứng thư PAdES |
| `python-pkcs11` | `0.10.1` | Thư viện import | MIT | Có | PyPI | Truy cập token SoftHSM/HSM |
| `asn1crypto` | `1.5.1` | Thư viện import | MIT | Có | PyPI | Phân tích ASN.1/X.509 |
| `qrcode` | `8.0` | Thư viện import | BSD-3-Clause | Có | PyPI | Tạo mã QR nhúng vào PDF giấy phép |
| `reportlab` | `4.4.1` | Thư viện import | BSD-3-Clause | Có | PyPI | Sinh văn bản PDF giấy phép |
| `duckdb` | `1.2.0` | Thư viện import | MIT | Có | PyPI | Phân tích dữ liệu Parquet cục bộ |
| `pyarrow` | `19.0.1` | Thư viện import | Apache-2.0 | Có | PyPI | Xử lý dữ liệu định dạng Parquet |
| `pytest` | `8.3.4` | Công cụ phát triển | MIT | Có | PyPI | Khung kiểm thử tự động |
| `pytest-asyncio` | `0.25.3` | Công cụ phát triển | Apache-2.0 | Có | PyPI | Hỗ trợ async cho pytest |
| `ruff` | `0.9.9` | Công cụ phát triển | MIT | Có | PyPI | Linter và formatter mã Python |

### 2.1. Gói hệ thống trong image dịch vụ (apt)

| Thành phần | Phiên bản ghim | Cách dùng | SPDX | OSI | Nguồn | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `softhsm2` | `2.6.1-3` | Dịch vụ riêng | BSD-2-Clause | Có | Debian | Token PKCS#11 phần mềm |
| `opensc` | `0.26.1-2` | Công cụ | LGPL-2.1-or-later | Có | Debian | `pkcs11-tool` nạp/xuất cert |
| `openssl` | `3.5.7` | Công cụ | Apache-2.0 | Có | Debian | Sinh test CA, CSR, PKCS#8 |

---

## 3. Thư viện Frontend trực tiếp (Vue 3 / TypeScript - Build vào SPA)

| Thành phần | Phiên bản ghim | Cách dùng | SPDX | OSI | Nguồn | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `vue` | `3.5.13` | Thư viện import | MIT | Có | npm | Framework giao diện người dùng |
| `vue-router` | `4.5.0` | Thư viện import | MIT | Có | npm | Điều hướng trang SPA |
| `pinia` | `3.0.1` | Thư viện import | MIT | Có | npm | Quản lý trạng thái ứng dụng |
| `oidc-client-ts` | `3.1.0` | Thư viện import | Apache-2.0 | Có | npm | Đăng nhập SSO OIDC PKCE |
| `@fontsource/inter` | `5.2.5` | Phông chữ nhúng | OFL-1.1 | Có | npm | Phông Inter (có bộ ký tự tiếng Việt), đóng gói vào SPA để chạy không cần Internet |
| `echarts` | `5.6.0` | Thư viện import | Apache-2.0 | Có | npm | Biểu đồ bảng điều hành |
| `tailwindcss` | `3.4.17` | Thư viện import | MIT | Có | npm | Tiện ích CSS tạo kiểu giao diện |
| `vite` | `6.2.0` | Công cụ phát triển | MIT | Có | npm | Công cụ đóng gói ứng dụng |
| `typescript` | `5.7.3` | Công cụ phát triển | Apache-2.0 | Có | npm | Trình biên dịch TypeScript |
| `vitest` | `3.0.7` | Công cụ phát triển | MIT | Có | npm | Kiểm thử đơn vị frontend (cả hai ứng dụng web) |
| `@vue/test-utils` | `2.6.0` | Công cụ phát triển | MIT | Có | npm | Gắn component Vue khi kiểm thử |
| `happy-dom` | `20.14.6` | Công cụ phát triển | MIT | Có | npm | DOM giả lập cho test component |
| `@playwright/test` | `1.50.1` | Công cụ phát triển | Apache-2.0 | Có | npm | Khung kiểm thử E2E trình duyệt |

---

## 4. Mô hình Trí tuệ Nhân tạo (AI Models - Trọng số tải riêng lúc chạy)

| Thành phần | Phiên bản ghim | Cách dùng | SPDX | OSI | Nguồn | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `qwen2.5:0.5b` | `latest-pinned` | Mô hình | Apache-2.0 | Có | HuggingFace / Ollama | Mô hình sinh ngôn ngữ nhẹ CPU |
| `bge-m3` | `latest-pinned` | Mô hình | MIT | Có | HuggingFace / Ollama | Mô hình sinh vector nhúng đa ngữ |

*(Lưu ý: Không lưu trữ trọng số mô hình trong kho mã nguồn).*

---

## 5. Môi trường Thực thi và Công cụ Phát triển (Development Tools)

| Thành phần | Phiên bản ghim | Cách dùng | SPDX | OSI | Nguồn | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Node.js` | `22.x LTS` | Công cụ phát triển | MIT | Có | Node.js Foundation | Môi trường thực thi JavaScript |
| `npm CLI` | `10.x / 11.x` | Công cụ phát triển | Artistic-2.0 | Có | npm, Inc. | Trình quản lý gói npm |
| `Docker Engine` | `26.x+` | Công cụ phát triển | Apache-2.0 | Có | Moby Project | Nền tảng container hóa |
| `Docker Compose` | `v2.29+` | Công cụ phát triển | Apache-2.0 | Có | Docker, Inc. | Điều phối container cục bộ |
| `cosign` | `2.4.1` | Công cụ phát triển | Apache-2.0 | Có | Sigstore | Ký và xác minh chữ ký container |
| `restic` | `0.17.3` | Công cụ phát triển / Vận hành | BSD-2-Clause | Có | Restic contributors | Mã hóa sao lưu và phục hồi thảm họa |
| `syft` | `1.19.0` | Công cụ phát triển | Apache-2.0 | Có | Anchore | Sinh tài liệu định danh SBOM |
| `trivy` | `0.59.1` | Công cụ phát triển | Apache-2.0 | Có | Aqua Security | Quét lỗ hổng và kiểm tra giấy phép |
| `reuse` | `5.0.2` | Công cụ phát triển | GPL-3.0-or-later | Có | FSFE | Kiểm tra chuẩn bản quyền REUSE |

---

## 6. Dịch vụ Ngoài và GitHub Actions (External Services)

| Thành phần | Phiên bản ghim | Cách dùng | SPDX | OSI | Nguồn | Ghi chú |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GitHub` | Dịch vụ ngoài | Dịch vụ ngoài | Thương mại / SaaS | Không | GitHub Inc. | Nền tảng lưu trữ mã và CI/CD |
| `actions/checkout` | `v4.2.2` | GitHub Action | MIT | Có | GitHub Actions | Tải mã nguồn repository |
| `actions/setup-python` | `v5.4.0` | GitHub Action | MIT | Có | GitHub Actions | Cài đặt môi trường Python trong CI |
| `actions/setup-node` | `v4.2.0` | GitHub Action | MIT | Có | GitHub Actions | Cài đặt môi trường Node.js trong CI |
| `sigstore/cosign-installer` | `v3.8.1` | GitHub Action | Apache-2.0 | Có | GitHub Actions | Cài đặt công cụ cosign |
| `aquasecurity/trivy-action`| `0.29.0` | GitHub Action | Apache-2.0 | Có | GitHub Actions | Chạy quét bảo mật Trivy |
| `gitleaks/gitleaks-action` | `v2.3.8` | GitHub Action | MIT | Có | GitHub Actions | Kiểm tra rò rỉ bí mật trong commit |

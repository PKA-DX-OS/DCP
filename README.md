<!--
SPDX-FileCopyrightText: 2026 DCP contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# DCP — DX-OS Open-Core

> **Nền tảng dịch vụ lõi headless cho bài toán Một cửa Cấp phép Xây dựng và Hậu kiểm Công trường.**
>
> Dự án phục vụ cuộc thi Olympic Tin học Sinh viên Việt Nam 2026 — Khối Phần mềm Nguồn mở (OLP PMNM 2026).

[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)](LICENSE)
[![Release: v1.1](https://img.shields.io/badge/release-v1.1-green.svg)](https://github.com/PKA-DX-OS/DCP/releases/tag/v1.1)

---

## 1. Giới thiệu

DCP là một **nền tảng dịch vụ lõi (Tầng 1)** chạy headless, không có giao diện người dùng cuối, cung cấp các dịch vụ dùng chung cho nhiều ứng dụng nghiệp vụ:

- Định danh, SSO, MFA, vai trò, đa thuê ước.
- API Gateway, JWT, rate-limit, security headers.
- Dữ liệu cấu trúc (PostgreSQL/PostgREST/RLS) và phi cấu trúc (S3, ClamAV).
- Quy trình nghiệp vụ BPMN (Flowable), tác vụ, SLA, phân tách nhiệm vụ.
- Audit hash chain, sự kiện outbox, metrics, lineage.
- Ký số PDF/PAdES, QR xác minh, trợ lý RAG.

**Ứng dụng minh họa (Tầng 2):** Một cửa cấp phép xây dựng nhà ở riêng lẻ + hậu kiểm công trường bằng dữ liệu bụi/tiếng ồn, bao gồm:

- Cổng công dân: nộp hồ sơ, checklist giấy tờ, theo dõi tiến độ, tải giấy phép.
- Workspace cán bộ: tiếp nhận, phân công, thẩm định, duyệt, ký, hậu kiểm.
- Dashboard lãnh đạo: 11 chỉ số, truy vết nguồn dữ liệu, xuất Excel/PDF.
- Trợ lý AI: hỏi đáp quy định có trích dẫn.

---

## 2. Trạng thái

> **Phiên bản hiện tại: [v1.1](https://github.com/PKA-DX-OS/DCP/releases/tag/v1.1)** (2026-11-20). Danh sách thay đổi xem [CHANGELOG.md](CHANGELOG.md).

- [x] LICENSE AGPL-3.0-or-later
- [x] README, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY
- [x] REUSE.toml, LICENSES/
- [x] Tầng 1 — dịch vụ lõi
- [x] Tầng 2 — ứng dụng C3 (`cap-phep`, `bang-dieu-hanh`)
- [x] Bộ test, demo, SBOM ([QA_RESULTS_2026-11-20.md](docs/QA_RESULTS_2026-11-20.md), [demo-guide.md](docs/demo-guide.md), `sbom/`)

---

## 3. Kiến trúc

```
Tầng 3: Nền tảng kinh doanh số (ngoài phạm vi)
────────────────────────────────────────────────
Tầng 2: Không gian năng lực H-P-D-I
  [H] Cổng công dân       [P] Workspace cán bộ
  [D] Dashboard/BI        [I] Trợ lý RAG
────────────────────────────────────────────────
Tầng 1: Nền tảng dịch vụ lõi (headless)
  Keycloak · APISIX · PostgreSQL/PostgREST · SeaweedFS/ClamAV
  Flowable · NATS · OpenBao · SoftHSM · audit · metrics · assistant
```

**Bốn nguyên lý thiết kế:**

1. Phân tách dữ liệu theo vòng đời và tốc độ (nóng → ấm → lạnh).
2. Hội tụ IT/OT: dữ liệu nghiệp vụ + dữ liệu cảm biến hiện trường.
3. Quản trị dữ liệu: phả hệ, chất lượng, kiểm toán.
4. Zero-Trust + GitOps: xác thực nhiều lớp, cấu hình bằng mã, tự phục hồi.

---

## 4. Cấu trúc repo

```
core/           # cấu hình Tầng 1: PostgreSQL, Keycloak, APISIX, NATS, OpenBao...
services/       # dịch vụ mỏng: files, doc-sign, flow, ingest, metrics, assistant...
apps/           # ứng dụng Tầng 2: cap-phep, bang-dieu-hanh
tools/          # giả lập cảm biến, tiện ích
scripts/        # init, backup, restore, doctor, SBOM...
docs/           # kiến trúc, vận hành, bảo mật, demo
tests/          # unit, integration, e2e, e2e-ui
contracts/      # hợp đồng API (OpenAPI) của các phân hệ
sbom/           # SBOM CycloneDX theo phiên bản
```

---

## 5. Cài đặt nhanh

Yêu cầu Docker Engine 26+ và Docker Compose v2.29+, máy từ 12 GB RAM và còn trống 20 GB đĩa.

```bash
git clone https://github.com/PKA-DX-OS/DCP.git
cd DCP
./dx.sh init --demo      # Windows: .\dx.ps1 init --demo
./dx.sh up               # Windows: .\dx.ps1 up
```

| Địa chỉ | Nội dung |
| :--- | :--- |
| `http://localhost:8080/` | cổng chủ đầu tư và bàn làm việc cán bộ |
| `http://localhost:8080/dieu-hanh/` | bảng điều hành |
| `http://localhost:8080/kiem-tra/<mã>` | tra cứu văn bản đã ký |

Tài khoản demo và mật khẩu được sinh ngẫu nhiên vào `secrets/demo-accounts.txt`. Hướng dẫn đầy đủ (nâng cấp, LAN, gỡ cài đặt, kiểm thử) xem [docs/install.md](docs/install.md); vận hành xem [docs/ops.md](docs/ops.md).

---

## 6. Đóng góp

Xem [CONTRIBUTING.md](CONTRIBUTING.md) để biết quy ước nhánh, commit, PR và SPDX.

- Nhánh `main`: luôn releasable, chỉ nhận PR.
- Nhánh `develop`: tích hợp.
- Nhánh cá nhân: `feat/<tên>`.
- Commit theo Conventional Commits.
- Mỗi file nguồn có SPDX header; chạy `reuse lint` trước khi PR.

---

## 7. Giấy phép

Mã nguồn phát hành theo **GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)**. Xem [LICENSE](LICENSE) và [LICENSES/](LICENSES/).

Tài liệu phát hành theo **CC-BY-4.0**; cấu hình/khai báo có thể dùng **CC0-1.0**.

---

## 8. Tuyên bố giới hạn

Hệ thống là **bản mô phỏng phục vụ cuộc thi**:

- Dữ liệu là dữ liệu tổng hợp, không phải dữ liệu thật của công dân/doanh nghiệp.
- Chữ ký số dùng SoftHSM/test CA, không phải chứng thư số quốc gia/HSM.
- Giấy phép PDF không có giá trị pháp lý.
- Không tuyên bố tuân thủ ISO 27001/SOC.

---

## 9. Liên hệ

- Repo: <https://github.com/PKA-DX-OS/DCP>
- Báo lỗi bảo mật: xem [SECURITY.md](SECURITY.md)

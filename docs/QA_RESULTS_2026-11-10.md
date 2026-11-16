<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Kết quả kiểm thử & cải thiện — 10/11/2026

## 1. Phạm vi cải thiện

- Ký PDF **PAdES/SoftHSM2/PKCS#11** (mặc định demo), giữ OpenBao Transit legacy.
- Dashboard **[D]** gọi `metrics-api` thật, có OIDC PKCE và phả hệ OpenLineage.
- Trợ lý **[I]** gọi `assistant` RAG thật, có citation.
- Trang `/kiem-tra` bỏ CDN, dùng CSS nội bộ, thêm form đối soát PDF.
- Sửa `metrics-api` đọc `jsonb` từ asyncpg.
- Thêm SBOM CycloneDX, CLI `e2e`, `e2e-ui`, `test-qa`, `check-no-fakes`, `sbom`.
- Sửa one-command, sensor endpoint, GitOps reconciler, backup/restore SoftHSM.
- Thống nhất UI: banner, header indigo, font, card, footer, link chéo C3 ↔ Bảng điều hành.
- **P1 Manifest giấy tờ:** `document_manifest` + checklist động; server kiểm tra 7 lớp, trả 422 có cấu trúc; chặn thiếu/hết hạn/lệch số liệu/trùng SHA-256.
- **Review từng tệp:** `trang_thai_kiem_tra`, `ly_do`, `version`, `tep_goc_id`; nút Đạt/Không đạt trên Bàn làm việc; công dân thấy trạng thái từng giấy.
- **Đủ 8 chỉ số dashboard:** thêm đang xử lý, thời gian TB, phiếu kiểm tra, vi phạm; dashboard render động.

## 2. Kết quả chạy

| Hạng mục | Kết quả |
|---|---|
| Unit tests | **18 passed** |
| E2E API qua APISIX | **13/13 passed** |
| E2E UI 11 bước (Playwright) | **1 passed** |
| Integration/security trên host | **117 passed, 1 skipped** (thêm 5 test P1 manifest) |
| Scan exposure/RLS | **100% tuân thủ, 0 vi phạm** |
| Audit hash chain | **PASS** |
| REUSE lint | **Compliant (0 missing license/copyright)** |
| SBOM | `sbom/dxos-1.1.0.cdx.json` — **30 thành phần** |
| GitOps reconciler | **PASS, không drift** |
| Backup/restore | **PASS — RTO 12.94s**, có SoftHSM |
| PAdES sau restore | **PASS** |
| One-shot `run.ps1`/`run.cmd` | **PASS** — từ stack đã stop, exit 0, 6 dịch vụ healthy, gateway HTTP OK |
| P1 nộp thiếu giấy | **422** + 6 lỗi đúng `loai_giay` |
| P1 giấy hết hạn | **422** "Giấy tờ đã hết hạn" |
| P1 lệch diện tích L5 | **422** "Diện tích trên giấy đất khác hồ sơ" |
| P1 trùng SHA-256 | **422** "Tệp đã tồn tại trong hồ sơ" |
| P1 nộp đủ 6 giấy | **200**, tạo hồ sơ + 6 `ho_so_tep` version 1 |
| Review tệp đạt/không đạt | **PASS** — cập nhật trạng thái + lý do + audit |
| Dashboard 8 chỉ số | **PASS** — đủ 8 nhãn, không lỗi tải dữ liệu |

## 3. Backup cuối

- Restic repository: volume `dxos-c3_dxos-backups`
- Backup gần nhất: `dxos-backup-20261110_095317`
- Bao gồm: PostgreSQL, SeaweedFS S3, OpenBao, SoftHSM token + test CA.

## 4. Lưu ý

- Test CA/SoftHSM chỉ phục vụ demo, **không có giá trị pháp lý**.
- `e2e-ui` và `test-qa` cần Python + Playwright trên host; các test còn lại chạy qua tools container.
- Docker Desktop đôi khi tạo APISIX nhưng chưa start; `dx.ps1 up`/`dx.sh up` có fallback `docker start dxos-apisix`.

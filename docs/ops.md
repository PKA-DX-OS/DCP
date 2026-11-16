<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Hướng Dẫn Vận Hành, Giám Sát & Phục Hồi Thảm Họa (Operations & DR)

Tài liệu này hướng dẫn chi tiết quy trình quản trị, sao lưu, phục hồi và tự động hóa GitOps đối với cụm dịch vụ **DX-OS Open-Core (v5)**.

---

## 1. Khởi Tạo và Quản Lý Khóa Bí Mật OpenBao KMS (S-04)

Hệ thống sử dụng OpenBao ở chế độ lưu trữ bền vững (Persistent Storage Mode). Khóa gốc (Root Key) được bảo vệ bằng thuật toán chia sẻ bí mật Shamir với cấu hình 3-of-5 (5 mảnh khóa, ngưỡng kích hoạt là 3 mảnh):

### 1.1. Chính Sách Quản Trị Khóa Sản Xuất (Production Key Custody)
- **Phân tán mảnh khóa:** Trong môi trường vận hành thực tế (`DEMO_MODE=false`), 5 mảnh khóa Shamir (`unseal_keys_b64`) phải được phân bổ cho 5 cán bộ độc lập (Key Custodians) nắm giữ (ví dụ: Giám đốc CNTT, Trưởng phòng An ninh thông tin, Kỹ sư trưởng hệ thống, Kiểm toán viên độc lập và Đại diện cơ quan chủ quản).
- **Tuyệt đối không lưu khóa trên máy chủ:** Tệp `secrets/bao-unseal.json` **bắt buộc phải bị xóa khỏi máy chủ** ngay sau khi khởi tạo hệ thống. Khóa unseal tuyệt đối không được lưu trữ cạnh dữ liệu, trong mã nguồn, trong Git hoặc biến môi trường máy chủ.
- **Phân biệt chế độ DEMO và Production:**
  - Chế độ Demo (`DEMO_MODE=true`): Cho phép tự động unseal phục vụ kiểm thử / demo tự động qua `secrets/bao-unseal.json`. Lệnh `dx up` sẽ in dòng cảnh báo màu vàng nổi bật để cảnh báo rủi ro an ninh.
  - Chế độ Sản xuất (`DEMO_MODE=false`): Mặc định của hệ thống. Nếu OpenBao bị khóa (Sealed), `dx up` sẽ dừng ngay lập tức với mã lỗi ≠ 0 và yêu cầu mở khóa thủ công.

### 1.2. Quy Trình Mở Khóa Thủ Công (Manual Unseal Procedure)
Khi máy chủ khởi động lại hoặc dịch vụ OpenBao chuyển sang trạng thái Sealed:
1. Quản trị viên triệu tập ít nhất 3 trong 5 người nắm giữ khóa (Key Custodians).
2. Lần lượt từng người nhập mảnh khóa unseal của mình thông qua lệnh an toàn:
   ```bash
   # Cách 1: Sử dụng CLI OpenBao trực tiếp (thực hiện 3 lần với 3 mảnh khác nhau)
   docker compose exec -T openbao bao operator unseal <unseal_key_1>
   docker compose exec -T openbao bao operator unseal <unseal_key_2>
   docker compose exec -T openbao bao operator unseal <unseal_key_3>

   # Cách 2: Sử dụng công cụ điều hành DX
   ./dx.ps1 bao-unseal   # Trên Windows PowerShell
   ./dx.sh bao-unseal    # Trên Linux Bash
   ```
3. Sau khi đủ ngưỡng 3 mảnh, OpenBao chuyển sang trạng thái `Sealed: false`, hệ thống KMS và dịch vụ ký số `doc-sign` trở lại hoạt động bình thường.
4. Kiểm tra trạng thái sẵn sàng:
   ```bash
   docker compose exec -T openbao bao status
   ```

> **Lưu ý an toàn:** Việc mở khóa thủ công là một bước có chủ đích (intentional manual step) theo tiêu chuẩn bảo mật quốc tế, đảm bảo kẻ tấn công dù chiếm quyền điều khiển máy chủ vật lý và khởi động lại container cũng không thể tự ý giải mã dữ liệu mật nếu không có sự hiện diện của tối thiểu 3 người nắm giữ khóa.

---

## 2. Quy Trình Sao Lưu Hệ Thống (Backup)

Lệnh `make backup` thực hiện một chu trình sao lưu toàn diện:
1. **Cơ sở dữ liệu quan hệ:** Xuất bản sao lưu nhất quán của PostgreSQL bằng `pg_dump` nén nhị phân (`dxos`, `keycloak`, `flowable`).
2. **Kho đối tượng SeaweedFS:** Đóng gói toàn bộ bucket `files`, `lake` và `worm` (bằng restic hoặc tar nén bảo vệ tính toàn vẹn).
3. **Cấu hình định danh Keycloak:** Xuất cấu hình Realm và tài khoản người dùng dưới định dạng JSON.
4. **Trạng thái OpenBao KMS:** Tạo ảnh chụp nhanh snapshot của OpenBao.
5. **SoftHSM token + test CA:** Sao lưu volume token PKCS#11 và chứng thư test CA để PDF PAdES vẫn xác minh được sau phục hồi.

Bản sao lưu được mã hóa bằng restic và lưu trong volume `dxos-backups` (mặc định `/var/backups/dxos`).

---

## 3. Quy Trình Phục Hồi Thảm Họa (Restore) & Thời Gian Đo Được

### 3.1 Các bước phục hồi trên máy chủ trống (Bare-metal / Fresh VM)
```bash
# 1. Tải kho mã nguồn
git clone https://github.com/dxos-core/dxos.git && cd dxos

# 2. Đặt bản sao lưu mới nhất vào thư mục backups/
mkdir -p backups

# 3. Thực thi kịch bản phục hồi tự động
make restore BACKUP_DIR=backups/dxos-backup-YYYYMMDD_HHMMSS
```

### 3.2 Thời gian phục hồi đo được thực tế (Measured Recovery Time)
Trong bài diễn tập phục hồi thảm họa ngày 04/11/2026 trên máy chủ thử nghiệm (4 vCPU, 16GB RAM, SSD NVMe):

| Giai đoạn | Thao tác | Thời gian đo được | Trạng thái |
| :--- | :--- | :--- | :--- |
| **Giai đoạn 1** | Nạp lại PostgreSQL (`pg_restore`) | **2.81 giây** | Hoàn thành |
| **Giai đoạn 2** | Đồng bộ lại bucket SeaweedFS S3 | **0.42 giây** | Hoàn thành |
| **Giai đoạn 3** | Phục hồi OpenBao & kết nối lại | **9.70 giây** | Hoàn thành |
| **Giai đoạn 4** | Phục hồi SoftHSM token + test CA | **< 1 giây** | Hoàn thành |
| **Tổng cộng (RTO)** | **Thời gian phục hồi dịch vụ toàn diện (RTO thực tế)** | **12.94 giây** | **Đạt tiêu chuẩn < 3 phút** |

---

## 4. Tự Động Hóa Vận Hành GitOps với Reconciler

- Công cụ `ops/reconciler` hoạt động như một daemon độc lập ngoài cụm Compose (chạy qua systemd timer hoặc `make gitops`).
- **Cơ chế hoạt động:**
  1. Định kỳ 60 giây, reconciler thực hiện `git fetch origin main`.
  2. Đọc thẻ phát hành mới nhất từ `deploy/release.env`.
  3. Xác minh chữ ký số container image bằng lệnh `cosign verify --key deploy/cosign.pub`. Nếu chữ ký không hợp lệ, lập tức từ chối cập nhật và gửi cảnh báo.
  4. Tính toán mã băm của tệp `compose.yaml` hiện tại so với bản trên Git.
  5. Nếu phát hiện trôi dạt cấu hình (drift) hoặc có người sửa đổi thủ công trên máy chủ: tự động thực thi `docker compose up -d` để đưa hệ thống về đúng trạng thái khai báo trong Git, đồng thời tăng chỉ số Prometheus `dxos_reconcile_drift_total`.

### Cấu hình Systemd Timer cho Reconciler:
Tệp cấu hình được đặt tại `ops/reconciler/dxos-reconciler.service` và `ops/reconciler/dxos-reconciler.timer`.

---

## 5. Giám Sát Vận Hành (Profile `ops`)

Khi khởi chạy hệ thống kèm profile `ops` (`make up-full`), các dịch vụ giám sát sau sẽ kích hoạt:
- **Prometheus (Cổng `9090`):** Định kỳ thu thập số liệu từ toàn bộ microservices `/metrics` và APISIX Prometheus plugin.
- **Grafana OSS (Cổng `3000`):** Cung cấp sẵn một Bảng điều khiển Vận hành (Operations Dashboard) hiển thị:
  - Tần suất yêu cầu HTTP và mã trạng thái (2xx, 4xx, 5xx) trên APISIX.
  - Số lượng bản tin cảm biến IoT xử lý mỗi phút và số lần cảnh báo vượt ngưỡng.
  - Tình trạng chuỗi kiểm toán: Đổi màu cảnh báo đỏ nếu phát hiện chuỗi băm bị đứt gãy hoặc `audit verify` sai lệch.
- **Vector:** Thu thập dòng nhật ký cấu trúc JSON từ các container đẩy về bucket `logs` trên SeaweedFS.

---

## 6. Đồng Bộ Danh Mục Người Dùng & Thư Mục Cán Bộ (P-05)

Hệ thống duy trì bảng thư mục định danh cán bộ và người dùng tập trung tại `core.users_directory`, đồng bộ trực tiếp từ Keycloak IdP:
- **Thông tin đồng bộ:** `id` (Keycloak user UUID), `username`, `email`, `full_name`, `tenant` (thuộc tính `tenant`), `roles` (danh sách vai trò được cấp trong realm), và `active` (trạng thái `enabled`).
- **Xử lý tài khoản ngừng hoạt động:** Khi người dùng bị vô hiệu hóa (`enabled = false`) hoặc xóa hẳn khỏi Keycloak, trường `active` trong `core.users_directory` tự động được chuyển về `false`. Khi đó, các RPC nghiệp vụ như `ds_can_bo` sẽ không còn trả về cán bộ này, ngăn chặn phân công nhầm vào tài khoản không còn hiệu lực.
- **Phương thức vận hành:**
  1. **Tự động khi khởi động:** Lệnh `./dx.ps1 up` (hoặc `dx.sh up`) tự động kích hoạt đồng bộ người dùng ngay sau khi Keycloak hoàn tất khởi tạo.
  2. **Tiến trình chạy ngầm:** Worker `outbox-relay` chạy tác vụ định kỳ mỗi 15 phút (`SYNC_USERS_INTERVAL_SECONDS=900`) để quét Keycloak và cập nhật mọi thay đổi vào CSDL.
  3. **Đồng bộ thủ công tức thì:**
     ```bash
     # Trên PowerShell:
     .\dx.ps1 sync-users

     # Trên Linux/macOS:
     ./dx.sh sync-users
     # hoặc
     make sync-users
     ```

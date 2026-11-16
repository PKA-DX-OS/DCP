<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Hướng Dẫn Cài Đặt Hệ Thống (Installation Guide)

Tài liệu này hướng dẫn chi tiết quy trình dựng hoàn chỉnh hệ thống **DX-OS Open-Core (v5)** từ thư mục mã nguồn sạch.

---

## 1. Yêu Cầu Môi Trường & Phần Cứng

- **Hệ điều hành:** Linux x86_64 (Ubuntu 22.04 / 24.04 LTS khuyến nghị), macOS Apple Silicon (ARM64) hoặc Windows 11 với Docker Desktop / WSL2.
- **Phần mềm cần thiết:**
  - Docker Engine phiên bản tối thiểu `26.0+`
  - Docker Compose v2 phiên bản tối thiểu `v2.29+`
  - GNU Make (`make`)
- **Tài nguyên phần cứng:**
  - Chạy cấu hình Lõi (`profile: core`): Tối thiểu 8 GB RAM, 4 vCPU, 20 GB dung lượng đĩa trống.
  - Chạy đầy đủ (`core + ai + ops + sim`): Tối thiểu 16 GB RAM, 8 vCPU, 40 GB dung lượng đĩa trống.

---

## 2. Các Bước Cài Đặt Chi Tiết

### Bước 1: Tải mã nguồn từ kho Git
```bash
git clone https://github.com/dxos-core/dxos.git
cd dxos
```

### Bước 2: Khởi tạo biến môi trường & sinh bí mật an toàn
```bash
make init
```
Lệnh này sẽ tạo tệp `.env` từ `.env.example`, đồng thời tự động sinh các chuỗi bí mật ngẫu nhiên bảo mật cao (PostgreSQL password, JWT secret, Keycloak admin credentials, OpenBao tokens).

### Bước 3: Khởi động các dịch vụ Lõi Tầng 1
```bash
make up
```
Docker Compose sẽ tải các image chuẩn đã ghim phiên bản và khởi chạy các container. Hệ thống áp dụng cấu hình `healthcheck` cho mọi dịch vụ và chỉ đánh dấu sẵn sàng khi tất cả dịch vụ phụ thuộc đều đạt trạng thái `healthy`.

### Bước 4: Cài đặt Gói Ứng dụng Cấp phép Xây dựng
```bash
make app-install APP=cap-phep
```
Lệnh này sẽ:
- Thực thi các migration tạo schema `app_cap_phep` và các bảng dữ liệu.
- Đồng bộ danh sách các vai trò nghiệp vụ vào Keycloak Realm `dxos`.
- Deploy các tệp quy trình `cap-phep.bpmn20.xml` và `hau-kiem.bpmn20.xml` vào Flowable Engine.
- Đăng ký mẫu phôi giấy phép và bộ quy tắc cảm biến môi trường.

### Bước 5: Nạp dữ liệu mẫu ban đầu
```bash
make seed
```
Tạo sẵn 10 tài khoản demo, 8 hồ sơ ở các trạng thái khác nhau (6 hồ sơ tại Phường A và 2 hồ sơ tại Phường B để kiểm tra đa thuê ước), 2 công trình đang thi công và tài liệu tri thức ban đầu.

---

## 3. Giải Thích Các Biến Cấu Hình Môi Trường Chính (`.env`)

| Biến Môi Trường | Giá Trị Mặc Định | Giải Thích |
| :--- | :--- | :--- |
| `PUBLIC_BASE_URL` | `http://localhost:8080` | URL công khai duy nhất để truy cập toàn bộ hệ thống qua APISIX |
| `SOURCE_URL` | `https://github.com/dxos-core/dxos` | Đường dẫn liên kết mã nguồn hiển thị tại chân trang theo Mục 13 AGPL |
| `POSTGRES_DB` | `dxos` | Tên cơ sở dữ liệu chính của hệ thống |
| `POSTGRES_USER` | `postgres` | Tài khoản quản trị cơ sở dữ liệu |
| `POSTGRES_SUPERUSER_PASSWORD` | Tự sinh ngẫu nhiên | Mật khẩu tài khoản superuser postgres |
| `KEYCLOAK_DB_PASSWORD` | Tự sinh ngẫu nhiên | Mật khẩu cơ sở dữ liệu riêng của Keycloak |
| `FLOWABLE_DB_PASSWORD` | Tự sinh ngẫu nhiên | Mật khẩu cơ sở dữ liệu riêng của Flowable |
| `DB_PASSWORD` | Tự sinh ngẫu nhiên | Mật khẩu cơ sở dữ liệu cho dịch vụ nền (dxos_svc) |
| `KEYCLOAK_ADMIN_PASSWORD` | Tự sinh ngẫu nhiên | Mật khẩu quản trị Keycloak Admin Console |
| `BAO_DEV_ROOT_TOKEN_ID` | Tự sinh ngẫu nhiên | Token quản trị OpenBao (secrets/Transit legacy) |
| `DEMO_MFA` | `false` | Bật/Tắt yêu cầu bắt buộc cài đặt OTP khi Lãnh đạo phê duyệt |
| `DEMO_TIME_SCALE` | `1` | Hệ số rút ngắn thời gian làm việc (phục vụ diễn tập trình diễn nhanh) |
| `BREAK_GLASS_TTL` | `PT2H` | Thời hạn hiệu lực của quyền truy cập khẩn cấp (ISO 8601 Duration) |
| `COMPOSE_PROFILES` | `core` | Danh sách profile dịch vụ kích hoạt mặc định (`core`, `ai`, `ops`, `sim`) |

---

### 3.1 Hướng Dẫn Cấu Hình Demo Qua Mạng LAN hoặc IP Tĩnh (N-08)

Khi triển khai demo hoặc kiểm thử từ các thiết bị khác trong mạng nội bộ (máy tính bảng cán bộ, điện thoại di động, máy trạm):

1. **Xác định địa chỉ IP máy chủ trong mạng LAN** (ví dụ `192.168.1.50` trên Windows bằng `ipconfig` hoặc Linux/macOS bằng `ip a`).
2. **Cấu hình `PUBLIC_BASE_URL` trong tệp `.env`**:
   ```bash
   PUBLIC_BASE_URL=http://localhost:8080,http://192.168.1.50:8080
   ```
   *Lưu ý:* Hệ thống hỗ trợ khai báo nhiều URL phân cách bằng dấu phẩy. Điều này cho phép bạn vừa truy cập từ máy chủ qua `localhost:8080`, vừa truy cập từ máy trạm LAN qua `http://<IP-LAN>:8080`.
3. **Thực thi lệnh khởi tạo**:
   ```powershell
   .\dx.ps1 init
   ```
   Lệnh này tự động:
   - Cập nhật chính sách CSP (`connect-src`) trong `core/apisix/apisix.yaml` cho phép trình duyệt kết nối tới các IP đã khai báo mà không làm bẩn Git working tree (nhờ cơ chế template).
   - Tự động bổ sung các URL mạng LAN vào danh sách `redirectUris` và `webOrigins` của Keycloak client `dxos-web`.
4. **Khởi động và truy cập**:
   ```powershell
   .\dx.ps1 up
   ```
   Từ bất kỳ thiết bị nào cùng mạng LAN, mở trình duyệt truy cập `http://<IP-LAN>:8080` để trải nghiệm đầy đủ các tính năng.


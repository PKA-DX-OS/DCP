<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Cài đặt và nâng cấp

Hướng dẫn dựng DX-OS Open-Core từ mã nguồn bằng lệnh `dx` (`./dx.sh` trên Linux/macOS,
`.\dx.ps1` trên Windows PowerShell). Vận hành hằng ngày, sao lưu và xử lý sự cố xem
[ops.md](ops.md).

## 1. Yêu cầu

- Docker Engine và Docker Compose v2 có hỗ trợ `docker compose up --wait` (khuyến nghị Docker
  Engine 26+, Compose v2.29+).
- Git; bash (Linux/macOS) hoặc PowerShell 5.1+ (Windows).
- Python 3 là tùy chọn: `dx init` dùng Python trên máy nếu đã có `cryptography`, `pyyaml`, `httpx`,
  nếu không sẽ build image `tools` và chạy trong đó. Mọi lệnh khác chạy trong container.
- Bộ nhớ: tổng `mem_limit` của profile `core` khoảng 9,3 GB, profile `ai` thêm khoảng 2,5 GB.
  Nên dùng máy từ 12 GB RAM (16 GB nếu bật `ai`) và còn trống ít nhất 20 GB đĩa.
- Cổng `8080` (gateway) và `8883` trống trên máy chủ; các cổng quản trị chỉ bind `127.0.0.1`
  (xem [architecture.md](architecture.md#4-cổng-mở-ra-máy-chủ)).

## 2. Cài mới

```bash
git clone https://github.com/PKA-DX-OS/DCP.git
cd DCP
./dx.sh init --demo      # Windows: .\dx.ps1 init --demo
./dx.sh up               # Windows: .\dx.ps1 up
```

Trên Windows có thể chạy `run.cmd` (gọi lần lượt `init --demo`, `up`, `doctor`). Trên Linux, WSL và
macOS có thể dùng `make init-demo` rồi `make up`; các mục vận hành của `Makefile` đều gọi `./dx.sh`.

Lưu ý theo hệ điều hành:

- **WSL:** clone repo vào hệ tệp của WSL (ví dụ `~/DCP`), không đặt ở `/mnt/c/...`: bind mount từ ổ
  Windows chậm và mất quyền thực thi. Cần Docker Desktop bật tích hợp WSL cho bản phân phối đang dùng,
  hoặc Docker Engine cài trong WSL.
- **macOS:** `dx.sh` chạy được với bash 3.2 có sẵn. Image `tools` tải restic đúng kiến trúc (amd64 hoặc
  arm64); image bên thứ ba không có bản arm64 được Docker Desktop chạy qua giả lập.
- **Linux:** `dx init` chạy trong container dùng uid/gid của người dùng hiện tại, nên `.env` và
  `secrets/` không thuộc root.

### 2.1 `dx init`

Chạy `scripts/init.py`; chạy lại nhiều lần không ghi đè bí mật đã có.

- Tạo `.env` từ `.env.example`, sinh ngẫu nhiên mọi mật khẩu và bí mật dịch vụ.
  `DEMO_MODE` mặc định `false`; cờ `--demo` đặt `DEMO_MODE=true`.
- Sinh chứng thư TLS cho NATS ở `core/nats/certs/`.
- Sinh vào `secrets/`: realm Keycloak `realm-dxos.json` (redirect URI và web origin lấy từ
  `PUBLIC_BASE_URL`), cấu hình S3 của SeaweedFS, cấu hình xác thực NATS, mật khẩu restic, bí mật
  client cảm biến từng phường, token nội bộ của `flow`.
- Kết xuất `core/apisix/apisix.yaml` từ template và tạo `core/postgrest/jwks.json` tạm.
- Tạo `deploy/release.env` từ `deploy/release.env.example` nếu chưa có, ghi mã băm của
  `compose.yaml` vào `COMPOSE_FILE_SHA256`.

`.env`, `secrets/`, chứng thư, `deploy/release.env` và hai tệp kết xuất trên đều nằm trong
`.gitignore`.

Client `dx-test` (đăng nhập bằng mật khẩu, dùng cho test) chỉ được tạo khi `DEMO_MODE=true`.

### 2.2 `dx up`

1. Build image (`core`, `tools`) và chạy profile `core` với `up -d --wait`.
2. Lấy JWKS của Keycloak cho PostgREST, khởi động lại `postgrest`.
3. Kiểm OpenBao. `DEMO_MODE=true`: tự khởi tạo (Shamir 5/3, lưu mảnh khóa ở
   `secrets/bao-unseal.json`) và tự mở khóa. Ngoài demo: OpenBao chưa khởi tạo hoặc đang khóa thì
   dừng với mã lỗi và nhắc chạy `dx bao-init` hoặc `dx bao-unseal`.
4. Cài hoặc nâng cấp app `cap-phep` (`scripts/app_manager.py install cap-phep`): migration schema
   `app_cap_phep`, triển khai `cap-phep.bpmn20.xml` và `hau-kiem.bpmn20.xml` lên Flowable, nạp chính
   sách vào `core.app_policies`, nạp danh mục giấy tờ và tri thức.
5. `DEMO_MODE=true` và chưa có `secrets/demo-accounts.txt`: chạy seed.
6. Đồng bộ người dùng Keycloak sang `core.users_directory`.
7. Chạy `dx doctor`.

### 2.3 Dữ liệu mẫu

Seed (`apps/cap-phep/seed/seed.py`, hoặc `dx seed`) tạo 12 tài khoản demo với mật khẩu ngẫu nhiên
ghi ở `secrets/demo-accounts.txt`:

| Tài khoản | Vai | Phường |
| :--- | :--- | :--- |
| `cdt.minh`, `cdt.lan` | chủ đầu tư | phuong-a |
| `mc.thu` | một cửa | phuong-a |
| `td.binh`, `td.cuong` | thẩm định | phuong-a |
| `ld.hoa` | lãnh đạo | phuong-a |
| `tt.khanh` | trật tự xây dựng | phuong-a |
| `kt.an` | kiểm toán (`dx:auditor`) | phuong-a |
| `mc.phuongb`, `ld.phuongb`, `td.phuongb` | một cửa, lãnh đạo, thẩm định | phuong-b |
| `admin` | quản trị nền tảng | global |

cùng 6 hồ sơ ở phường A (`CP-2026-000101` đến `000106`, mỗi hồ sơ ở một bước), 2 hồ sơ ở phường B
và công trình `CT-01`. Chạy lại seed chỉ xóa và nạp lại đúng các mã này.

### 2.4 Truy cập

| Địa chỉ | Nội dung |
| :--- | :--- |
| `http://localhost:8080/` | cổng chủ đầu tư và bàn làm việc cán bộ (cap-phep-web) |
| `http://localhost:8080/dieu-hanh/` | bảng điều hành |
| `http://localhost:8080/kiem-tra/<mã>` | tra cứu văn bản đã ký, không cần đăng nhập |
| `http://127.0.0.1:8081/auth/` | quản trị Keycloak (tài khoản trong `.env`) |

## 3. Truy cập qua mạng LAN

1. Thêm địa chỉ LAN vào `PUBLIC_BASE_URL` trong `.env`, phân cách bằng dấu phẩy:
   `PUBLIC_BASE_URL=http://localhost:8080,http://192.168.1.50:8080`.
2. Chạy `dx init`: cập nhật `connect-src` của CSP trong `core/apisix/apisix.yaml` và redirect URI,
   web origin của client `dxos-web` trong `secrets/realm-dxos.json`.
3. `dx restart apisix`.
4. Keycloak chỉ nhập `realm-dxos.json` khi realm `dxos` chưa tồn tại. Với stack đã chạy, thêm
   redirect URI và web origin mới cho client `dxos-web` trong trang quản trị Keycloak, hoặc dựng lại
   bằng `dx reset` (xóa dữ liệu).

## 4. Nâng cấp

```bash
./dx.sh backup           # sao lưu trước (xem ops.md)
git pull
./dx.sh init             # bổ sung biến mới vào .env, kết xuất lại apisix.yaml; không đổi bí mật cũ
./dx.sh up               # build lại, áp compose, nâng cấp app (idempotent), doctor
./dx.sh gitops           # kiểm còn lệch giữa Git và stack đang chạy không
```

- `app_manager` chạy lại được nhiều lần: BPMN không đổi thì bỏ qua, chính sách được ghi đè theo
  `app.yaml` (kiểm bởi `test_V3_01`).
- `dx up` không xóa volume. Chỉ `dx reset` (cần gõ `XOA` hoặc `--yes`) mới xóa container, volume và
  `secrets/demo-accounts.txt` rồi chạy lại `init`.

## 5. Gỡ cài đặt

```bash
./dx.sh app-uninstall cap-phep --yes   # gỡ app: xóa schema của app và chính sách của app
./dx.sh down                           # dừng, giữ dữ liệu
./dx.sh reset --yes                    # dừng và xóa toàn bộ dữ liệu
```

## 6. Kiểm thử sau cài đặt

```bash
python -m pip install -r services/requirements.txt pytest pytest-asyncio
python -m pytest tests/unit -q
python -m pytest tests/integration tests/e2e -q          # cần stack đang chạy, DEMO_MODE=true
python -m pip install playwright && python -m playwright install chromium
python -m pytest tests/e2e-ui -q                          # hành trình trên giao diện thật
```

Test tích hợp và e2e đọc mật khẩu demo từ `secrets/demo-accounts.txt` và mật khẩu Flowable từ
`.env`; Windows cần biến `PYTHONUTF8=1` nếu console không phải UTF-8. Kết quả lần chạy gần nhất
ghi ở [QA_RESULTS_2026-11-10.md](QA_RESULTS_2026-11-10.md).

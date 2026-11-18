<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Vận hành, sao lưu và xử lý sự cố

Các lệnh dưới đây viết dạng `./dx.sh <lệnh>`; trên Windows dùng `.\dx.ps1 <lệnh>` với cùng tham
số. `./dx.sh <lệnh> --help` in hướng dẫn riêng của từng lệnh. Cài đặt và nâng cấp xem
[install.md](install.md).

## 1. Lệnh hằng ngày

| Lệnh | Việc làm |
| :--- | :--- |
| `ps` | trạng thái và healthcheck các container |
| `logs [dịch vụ...]` | xem log trực tiếp |
| `restart [dịch vụ...]` | khởi động lại toàn bộ hoặc vài dịch vụ |
| `doctor [--bo-api]` | chẩn đoán (mục 2) |
| `sync-users` | đồng bộ người dùng Keycloak sang `core.users_directory` |
| `app-install [app]` | cài hoặc nâng cấp gói ứng dụng (mặc định `cap-phep`) |
| `postgrest-jwks` | lấy lại JWKS của Keycloak cho PostgREST rồi khởi động lại PostgREST |
| `backup`, `restore` | sao lưu, phục hồi (mục 4, 5) |
| `gitops [--apply]` | đối soát Git với stack đang chạy (mục 6) |
| `release [phiên bản]` | đóng gói `dist/dxos-<v>.tar.gz`, `SHA256SUMS` và tệp metadata |
| `down` | dừng container, giữ volume |
| `reset [--yes]` | xóa container và mọi volume, sinh lại cấu hình (cần gõ `XOA`) |

Lệnh không hợp lệ trả mã thoát 2; lệnh con lỗi trả mã khác 0.

## 2. Chẩn đoán: `dx doctor`

`scripts/doctor.py` kiểm lần lượt và in từng mục `OK`, `WARN` hoặc `FAIL`:

1. Mọi dịch vụ profile `core` trong `compose.yaml` có container đang chạy và healthcheck
   `healthy`; container chạy một lần (`softhsm-init`) phải thoát mã 0.
2. Cổng của từng dịch vụ mở được (trên máy chủ: cổng công bố ra `127.0.0.1`; trong container
   `tools`: `tên-dịch-vụ:cổng`).
3. Chứng thư `core/nats/certs/server.crt`: thiếu hoặc hết hạn là `FAIL`, còn dưới 30 ngày là `WARN`.
4. Đĩa trống ở thư mục repo: dưới 512 MiB là `FAIL`, dưới 2 GiB là `WARN`.
5. Đầu-cuối: lấy token Keycloak cho `cdt.minh` (mật khẩu từ `secrets/demo-accounts.txt`) và gọi
   `v_ho_so` qua APISIX. `--bo-api` bỏ bước này (ví dụ ngoài chế độ demo).

Mã thoát 0 khi không có `FAIL`, 1 khi có, kèm danh sách mục lỗi. Không in mật khẩu hay token.

## 3. OpenBao

- `dx bao-init` khởi tạo OpenBao (Shamir 5 mảnh, ngưỡng 3) và tạo khóa ký `doc-sign`; mảnh khóa
  ghi vào `secrets/bao-unseal.json`.
- `dx bao-unseal` mở khóa sau khi khởi động lại.
- `DEMO_MODE=true`: `dx up` tự khởi tạo, tự mở khóa và in cảnh báo.
- Ngoài demo: `dx up` dừng nếu OpenBao chưa khởi tạo hoặc đang khóa. Khuyến nghị chia 5 mảnh khóa
  cho 5 người giữ khác nhau, chuyển `secrets/bao-unseal.json` ra khỏi máy chủ sau khi khởi tạo, và
  mở khóa thủ công bằng ít nhất 3 mảnh:

  ```bash
  docker compose exec -T openbao bao operator unseal   # lặp lại với 3 mảnh khác nhau
  docker compose exec -T openbao bao status
  ```

Với `SIGNING_MODE=pkcs11` (mặc định), ký giấy phép dùng SoftHSM nên không phụ thuộc OpenBao;
OpenBao vẫn cần cho văn bản đã ký bằng Transit trước đó.

## 4. Sao lưu: `dx backup`

`scripts/backup.py` chạy trong container `tools`:

1. `pg_dumpall` toàn bộ cụm PostgreSQL (CSDL `dxos`, `keycloak`, `flowable`).
2. Chép mọi bucket SeaweedFS (`staging`, `files`, `lake`, `worm`, `logs`).
3. Đóng gói dữ liệu OpenBao và hai volume SoftHSM (token, chứng thư CA thử nghiệm).
4. Ghi `manifest.json`: SHA-256 và kích thước từng tệp; bản sao ở
   `/var/backups/dxos/manifests/<backup_id>.json`.
5. Mã hóa vào kho restic `/var/backups/dxos/restic_repo` (volume `dxos_dxos-backups`), gắn tag
   `<backup_id>`. Mật khẩu: `RESTIC_PASSWORD` hoặc `secrets/restic-password.txt`.
6. Xóa thư mục tạm; log và manifest không chứa bí mật.

Bản sao lưu không nằm trong thư mục mã nguồn. Cần chép định kỳ kho restic ra nơi khác và cất
`secrets/restic-password.txt` ngoài máy chủ: mất mật khẩu thì không giải mã được.

Ví dụ lịch hằng ngày lúc 2 giờ sáng (cron của người dùng vận hành):

```cron
0 2 * * * cd /opt/dxos && ./dx.sh backup >> logs/backup.log 2>&1
```

## 5. Phục hồi: `dx restore`

```bash
./dx.sh restore --list               # liệt kê bản sao lưu trong kho restic
./dx.sh restore --chi-kiem           # giải mã bản mới nhất và kiểm manifest, không ghi gì
./dx.sh restore --id <backup_id>     # phục hồi một bản, hỏi xác nhận (gõ PHUC HOI)
./dx.sh restore --yes                # phục hồi bản mới nhất, không hỏi
```

`scripts/restore.py` giải mã bản sao lưu vào thư mục tạm, kiểm từng tệp với manifest (thiếu tệp,
sai mã băm hay có tệp lạ đều dừng, không ghi gì), rồi mới nạp lại PostgreSQL, các bucket S3,
OpenBao (khởi động lại, mở khóa khi có mảnh khóa, khởi động lại `doc-sign`) và SoftHSM. In thời
gian từng giai đoạn và tổng thời gian; luôn xóa thư mục tạm.

Phục hồi lên máy mới:

1. `git clone`, đặt lại `.env` và `secrets/` từ bản cất giữ ngoài máy (cùng mật khẩu restic).
2. `./dx.sh up` để dựng stack rỗng.
3. Chép kho restic vào volume:
   `docker run --rm -v dxos_dxos-backups:/var/backups/dxos -v "$PWD/restic_repo:/src:ro" alpine cp -a /src /var/backups/dxos/restic_repo`.
4. `./dx.sh restore --chi-kiem`, rồi `./dx.sh restore --yes`.
5. `./dx.sh doctor`.

## 6. GitOps: `dx gitops`

`ops/reconciler/reconciler.py` so trạng thái mong muốn (Git) với thực tế:

- **Compose:** `docker compose --profile core config --hash "*"` so với nhãn
  `com.docker.compose.config-hash` của từng container; báo container thiếu, không chạy, lệch cấu hình.
- **Git:** thay đổi chưa commit ở `compose.yaml`, `apps/`, `core/`.
- **Chính sách app:** `core.app_policies` so với `app.yaml` (`flow_policies`, `break_glass`,
  `doc_signers`, `metrics`). `--bo-chinh-sach` bỏ bước này.

Mặc định chỉ báo. `--apply` chạy `docker compose --profile core up -d` (không xóa volume, không
xóa container lạ) và `app_manager upgrade`. Mã thoát: 0 không lệch, 3 có lệch, 1 lỗi. Log JSON từng
lần chạy ghi vào `logs/reconciler.jsonl`; khóa `logs/reconciler.lock` chặn hai lần chạy chồng nhau.

Chạy định kỳ bằng systemd (máy chủ Linux, repo đặt ở `/opt/dxos`, người dùng `dxos` thuộc nhóm
`docker`):

```bash
sudo cp ops/reconciler/dxos-reconciler.service ops/reconciler/dxos-reconciler.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dxos-reconciler.timer
journalctl -u dxos-reconciler.service
```

Timer chạy 2 phút sau khi khởi động máy, sau đó 5 phút một lần kể từ lần chạy trước. Muốn tự áp lại
thì thêm `--apply` vào `ExecStart`. Reconciler không tự `git pull`.

## 7. Người dùng và vai trò

- Người dùng và vai quản lý trong Keycloak realm `dxos`; tenant lấy từ thuộc tính `tenant`.
- `core.users_directory` (dùng cho danh sách cán bộ, tên người xin truy cập khẩn...) được đồng bộ
  khi `dx up`, khi chạy `dx sync-users`, và định kỳ trong `outbox-relay`
  (`SYNC_USERS_INTERVAL_SECONDS`, mặc định 900 giây). Người dùng bị tắt hoặc xóa trong Keycloak có
  `active = false`.

## 8. Kiểm toán

- `GET /api/v1/audit/verify` (vai `dx:auditor` hoặc quản trị nền tảng) kiểm lại chuỗi băm
  `core.audit_log`.
- `POST /api/v1/audit/seal` (cùng vai) niêm phong đầu chuỗi vào `core.audit_seal` và bucket `worm`.
- Kiểm chuỗi từ dòng lệnh, chỉ đích danh bản ghi bị sửa:
  `docker compose --profile tools run --rm -T tools scripts/verify_audit.py`.

## 9. Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
| :--- | :--- | :--- |
| `dx up` báo thiếu `.env` | chưa khởi tạo | `dx init` (thêm `--demo` cho môi trường thử) |
| `dx up` dừng ở bước OpenBao | OpenBao chưa khởi tạo hoặc đang khóa, `DEMO_MODE=false` | `dx bao-init` lần đầu, `dx bao-unseal` các lần sau |
| PostgREST trả 401 với token hợp lệ | JWKS của PostgREST cũ (Keycloak đổi khóa, dựng lại realm) | `dx postgrest-jwks` |
| Tải tệp trả 503 `Retry-After` | ClamAV chưa sẵn sàng (lần đầu phải tải cơ sở dữ liệu virus) | chờ `clamav` healthy (`dx ps`), thử lại |
| Ký giấy phép lỗi, `doc-sign` báo PKCS#11 | `softhsm-init` chưa chạy xong hoặc lỗi | `dx logs softhsm-init`; `dx doctor` báo mã thoát của container này |
| Đăng nhập báo `Invalid redirect uri` | truy cập bằng địa chỉ chưa khai báo | xem [install.md](install.md#3-truy-cập-qua-mạng-lan) |
| Trang `/kiem-tra` không gửi được tệp đối soát | `apisix.yaml` kết xuất từ template cũ (`form-action 'none'`) | `dx init`, rồi `dx restart apisix` |
| Chuông thông báo đứng ở "Mất kết nối" | `flow` khởi động lại hoặc vé SSE hết hạn | giao diện tự thử lại (1, 2, 4... tối đa 30 giây); nếu kéo dài xem `dx logs flow` |
| `dx doctor` `FAIL` chứng thư NATS | `core/nats/certs/server.crt` hết hạn | xóa thư mục `core/nats/certs/`, chạy `dx init`, `dx restart nats` |
| `dx gitops` mã thoát 3 | có người sửa tay container hoặc chính sách | xem `logs/reconciler.jsonl`, chạy `dx gitops --apply` nếu thay đổi không chủ đích |

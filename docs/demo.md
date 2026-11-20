# Hướng Dẫn Trình Diễn DX-OS Open-Core C3

Tài liệu này mô tả cách dựng stack và chạy kịch bản trình diễn 6 chặng của miền cấp phép xây dựng.

## 1. Môi trường

Yêu cầu: Docker Desktop, Python 3.12, Node 22 (chỉ cần khi build giao diện).

```bash
cp .env.example .env
python scripts/init.py
docker compose --profile core up -d
python scripts/doctor.py
```

Cài gói ứng dụng và dữ liệu mẫu:

```bash
python scripts/app_manager.py install --app cap-phep
python apps/cap-phep/seed/seed.py
python scripts/seed_hero.py
python scripts/seed_demo_history.py
```

`seed_demo_history.py` tạo 72 hồ sơ demo trải 12 tháng (`CP-DEMO-HIST-*`) để dashboard có dữ liệu chart; chạy lại an toàn.

Tài khoản demo do `seed.py` sinh và ghi vào `secrets/demo-accounts.txt`:

| Tài khoản | Vai trò |
|---|---|
| `cdt.minh`, `cdt.lan` | Chủ đầu tư |
| `mc.thu` | Cán bộ một cửa |
| `td.binh`, `td.cuong` | Thẩm định viên |
| `ld.hoa` | Lãnh đạo phường |
| `tt.khanh` | Cán bộ trật tự xây dựng |

Mật khẩu lấy trong `secrets/demo-accounts.txt`, dòng `username:password:...`.

## 2. Sáu chặng trình diễn

### Chặng 1 — Công dân nộp hồ sơ

1. Mở `http://localhost:8080/`, đăng nhập `cdt.minh`.
2. Vào **Hồ sơ của tôi** → **Nộp hồ sơ mới**.
3. Điền họ tên, CCCD, điện thoại, địa chỉ, thửa đất, số tầng, diện tích.
4. Mở **Giấy tờ kèm theo**: checklist hiển thị các giấy bắt buộc.
5. Bấm **Kiểm tra và nộp hồ sơ** khi chưa đủ giấy — hệ thống báo đúng tên giấy còn thiếu.
6. Tải đủ giấy, bấm nộp; hồ sơ xuất hiện với trạng thái đã nộp.

### Chặng 2 — Một cửa tiếp nhận

1. Đăng xuất, đăng nhập `mc.thu`.
2. Vào **Bàn làm việc**; thấy việc **Kiểm tra Hồ sơ Hợp lệ**.
3. Mở hồ sơ, kiểm tra giấy tờ, hoàn thành việc.
4. Hồ sơ chuyển sang bước phân công.

### Chặng 3 — Thẩm định và SoD

1. Đăng nhập `td.binh`; mở việc **Thẩm định Hồ sơ Kỹ thuật**.
2. Kết luận đạt và gửi lãnh đạo.
3. Đăng nhập `td.cuong` (không được phân công), thử mở hồ sơ — nhận 403.
4. `td.cuong` yêu cầu **Truy cập khẩn**; `ld.hoa` vào tab **Truy cập khẩn** phê duyệt.
5. Quay lại `td.cuong`, mở được hồ sơ; mọi lần truy cập được ghi audit.

### Chặng 4 — Phê duyệt và ký PAdES

1. Đăng nhập `ld.hoa`; mở việc **Phê duyệt Cấp phép**.
2. Phê duyệt; `doc-sign` sinh PDF giấy phép, ký PAdES qua SoftHSM.
3. Hồ sơ chuyển `DA_CAP`; mở chi tiết thấy mã công khai và nút **Mở trang tra cứu**.

### Chặng 5 — Kiểm tra công khai

1. Mở `http://localhost:8080/kiem-tra/{public_code}` ở cửa sổ ẩn danh.
2. Hệ thống hiển thị trạng thái hợp lệ, ngày cấp, đơn vị cấp.
3. Tải một PDF đã bị sửa nội dung để kiểm tra — hệ thống báo chữ ký không khớp.

### Chặng 6 — Hậu kiểm và cảm biến

1. Chạy cảm biến giả lập:

```bash
python tools/sensor-sim/sim.py --tenant phuong-a --spike --duration 30
```

2. Đăng nhập `tt.khanh`; vào **Công trình**, mở `CT-01`.
3. Cảnh báo vượt ngưỡng 70 dBA được đẩy qua NATS; `outbox-relay` tạo phiếu kiểm tra và mở quy trình hậu kiểm.
4. Phiếu mới xuất hiện trong **Công trình**; bấm **Xem phiếu** để kiểm tra.

## 3. Lệnh hữu ích

```bash
python scripts/doctor.py          # kiểm tra stack và PostgREST
python scripts/verify_audit.py    # xác minh chuỗi băm audit
python -m pytest tests/unit -q    # unit test
docker compose down               # dừng stack
```

## 4. Lưu ý

- Stack dùng cổng 8080 (APISIX) và 8883 (MQTT); phải dừng stack khác đang chiếm hai cổng này.
- `scripts/init.py` sinh `secrets/`, chứng thư NATS, `apisix.yaml` và JWKS; không commit các tệp này.
- Nếu đổi tên miền/cổng công khai, cập nhật `PUBLIC_BASE_URL` trong `.env` rồi chạy lại `python scripts/init.py`.

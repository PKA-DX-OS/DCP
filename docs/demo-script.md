# Kịch Bản Trình Diễn 6 Chặng

**Thời lượng:** 15 phút.

**Điều kiện:** stack đã chạy, đã cài `cap-phep`, đã seed dữ liệu, tài khoản lấy từ `secrets/demo-accounts.txt`.

## Chuẩn bị

```bash
python scripts/doctor.py
```

Kết quả mong đợi: `[PASS] [DX DOCTOR OK] PostgREST trả về HTTP 200`.

## Chặng 1 — Nộp hồ sơ (3 phút)

| Bước | Thao tác | Kết quả |
|---|---|---|
| 1 | Đăng nhập `cdt.minh` | Vào **Hồ sơ của tôi** |
| 2 | Bấm **Nộp hồ sơ mới** | Mở modal nộp hồ sơ |
| 3 | Điền thông tin, chưa tải giấy tờ | — |
| 4 | Bấm **Kiểm tra và nộp hồ sơ** | Báo “Hồ sơ chưa đủ điều kiện nộp” kèm tên từng giấy thiếu |
| 5 | Tải đủ giấy, bấm nộp | Hồ sơ mới xuất hiện, trạng thái đã nộp |

**Câu chốt:** Hệ thống chặn hồ sơ thiếu giấy ngay trên giao diện, không đợi cán bộ kiểm tra.

## Chặng 2 — Một cửa tiếp nhận (2 phút)

| Bước | Thao tác | Kết quả |
|---|---|---|
| 1 | Đăng nhập `mc.thu` | **Bàn làm việc** có việc kiểm tra hồ sơ |
| 2 | Mở hồ sơ vừa nộp | Xem được giấy tờ, checklist |
| 3 | Hoàn thành việc | Hồ sơ chuyển bước phân công |

**Câu chốt:** Mỗi vai chỉ thấy việc được giao; danh sách việc lấy từ quy trình, không phải dữ liệu cứng.

## Chặng 3 — Thẩm định, 403 và truy cập khẩn (3 phút)

| Bước | Thao tác | Kết quả |
|---|---|---|
| 1 | Đăng nhập `td.binh`, mở việc thẩm định | Kết luận đạt, gửi lãnh đạo |
| 2 | Đăng nhập `td.cuong`, mở hồ sơ không được phân công | Nhận 403 |
| 3 | `td.cuong` gửi yêu cầu truy cập khẩn | Yêu cầu xuất hiện ở tab **Truy cập khẩn** |
| 4 | `ld.hoa` phê duyệt | `td.cuong` mở được hồ sơ |
| 5 | Kiểm tra audit | Có bản ghi `access.denied` và lần truy cập khẩn |

**Câu chốt:** Truy cập khẩn có phạm vi, thời hạn và dấu vết audit; không phải cửa sau.

## Chặng 4 — Phê duyệt và ký PAdES (3 phút)

| Bước | Thao tác | Kết quả |
|---|---|---|
| 1 | Đăng nhập `ld.hoa` | Thấy việc phê duyệt |
| 2 | Phê duyệt cấp phép | `doc-sign` sinh PDF và ký PAdES |
| 3 | Mở chi tiết hồ sơ | Trạng thái `DA_CAP`, có mã công khai |
| 4 | Bấm **Mở trang tra cứu** | Mở trang `/kiem-tra/{public_code}` |

**Câu chốt:** Giấy phép được ký số bằng SoftHSM; mã công khai cho phép kiểm tra mà không lộ dữ liệu khác.

## Chặng 5 — Kiểm tra công khai (2 phút)

| Bước | Thao tác | Kết quả |
|---|---|---|
| 1 | Mở `/kiem-tra/{public_code}` ẩn danh | Hiển thị trạng thái hợp lệ, ngày cấp, đơn vị cấp |
| 2 | Tải PDF đã sửa nội dung | Báo chữ ký không khớp |

**Câu chốt:** Người dân kiểm tra được giấy phép mà không cần tài khoản; sửa một byte là mất hiệu lực.

## Chặng 6 — Hậu kiểm và cảm biến (2 phút)

| Bước | Thao tác | Kết quả |
|---|---|---|
| 1 | Chạy `python tools/sensor-sim/sim.py --tenant phuong-a --spike --duration 30` | Cảm biến gửi dữ liệu vượt 70 dBA |
| 2 | Đăng nhập `tt.khanh`, mở **Công trình** | Thấy `CT-01` |
| 3 | Chờ vài giây, xem phiếu kiểm tra | Phiếu mới do cảnh báo tạo, có mã quy trình |
| 4 | Bấm **Xem phiếu** | Kiểm tra được danh sách phiếu hậu kiểm |

**Câu chốt:** Dữ liệu cảm biến đi qua NATS, outbox và quy trình hậu kiểm; không có thao tác thủ công nào ở giữa.

## Phương án khi lỗi

- Không đăng nhập được: chạy `python scripts/doctor.py`, kiểm tra Keycloak và `PUBLIC_BASE_URL`.
- Không thấy việc: kiểm tra đã chạy `seed.py` và đúng tài khoản/vai.
- Cảnh báo không tạo phiếu: kiểm tra `outbox-relay` healthy và `app.yaml` có `alert_hooks`.
- Cổng 8080 bận: dừng stack khác trước khi `docker compose up`.

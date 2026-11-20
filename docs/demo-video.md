# Video demo DX-OS C3

Video 8–10 phút quay theo [demo-script.md](demo-script.md), dùng làm phương án dự phòng khi demo trực tiếp (xem [demo-guide.md](demo-guide.md#du-phong)) và để gửi ban giám khảo. Tệp video **không commit vào repo**; trong repo chỉ có phụ đề `demo-video.srt` và liên kết dưới đây.

## Liên kết

| Bản | Liên kết | Ngày quay | Commit đã quay | Người quay |
|---|---|---|---|---|
| Chính (1080p) | *(điền sau khi tải lên)* | | | |
| Dự phòng (USB, máy dự phòng) | `D:\v1PMNM\_DXOS_TaiLieu\07_BanPhatHanh\video\` | | | |

Chỉ điền liên kết đã kiểm tra mở được ở chế độ không đăng nhập (hoặc ghi rõ ai có quyền xem).

## Quay

Phần này **do người thật làm**. Commit chỉ chứa phụ đề và liên kết.

1. **Chuẩn bị:** làm đủ checklist "Một ngày trước" và "Ba mươi phút trước" trong `demo-guide.md`; diễn tập một lần cho trơn.
2. **Màn hình:** 1920×1080 (hoặc 2560×1440), thu phóng trình duyệt 110–125 %, ẩn thanh dấu trang, ẩn biểu tượng màn hình nền.
3. **Phần mềm:** OBS Studio, 30 fps, MP4 (H.264, CRF 20), âm thanh 48 kHz. Chế độ *Display Capture* cho cả màn hình.
4. **Thứ tự:** quay từng cảnh thành một đoạn riêng để quay lại dễ; ghép theo thứ tự 1 → 9.
5. **Lời:** đọc đúng phần **Lời thoại** của từng cảnh trong `demo-script.md`. Đổi lời thì sửa `demo-script.md` trước, rồi sinh lại phụ đề.
6. **Logo:** chèn logo DX-OS (mái nhà và dấu kiểm, `apps/cap-phep/web/public/favicon.svg`) ở góc trên phải, độ mờ 80 %, trong suốt cả video.
7. **Không lộ bí mật:** không quay tệp `secrets\demo-accounts.txt`, ô mật khẩu khi đang gõ, hay thanh địa chỉ có token.
8. **Xuất:** bản chính 1080p; nếu quay 1440p thì xuất thêm một bản 1440p.

## Phụ đề

`demo-video.srt` (UTF-8, tối đa 2 dòng, 46 ký tự mỗi dòng) có đúng lời thoại của 9 cảnh trong `demo-script.md`, theo khung giờ của storyboard (cảnh 1 từ 0:00, cảnh 9 kết thúc 10:00).

Thời điểm trong tệp hiện là **thời điểm dự kiến**. Sau khi quay, chỉnh lại cho khớp tiếng nói thật bằng Subtitle Edit hoặc Aegisub: *Synchronization → Adjust all times*, rồi chỉnh từng câu lệch. Không sửa câu chữ trong `.srt` mà không sửa `demo-script.md`.

Kiểm tra trước khi nộp:
- [ ] Mở video kèm phụ đề trong VLC, xem hết: không có câu hiện sớm hay muộn quá 0,5 giây.
- [ ] Video khớp kịch bản: đủ 9 cảnh, đúng thứ tự, tổng 8–10 phút.
- [ ] Không có màn hình lỗi đỏ, không lộ mật khẩu.
- [ ] Ghi liên kết, ngày quay và commit đã quay vào bảng ở đầu tệp này.

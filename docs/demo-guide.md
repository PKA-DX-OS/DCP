<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Hướng dẫn demo và phương án dự phòng

Dành cho người đứng máy khi demo. Kịch bản lời thoại xem [demo-script.md](demo-script.md), khung cảnh và dữ liệu xem [demo-storyboard.md](demo-storyboard.md). Lệnh viết cho PowerShell trên Windows ở thư mục repo; trên Linux/macOS thay `.\dx.ps1` bằng `make` hoặc `./dx`.

## 1. Một ngày trước

| # | Việc | Lệnh / cách làm | Đạt khi |
|---|---|---|---|
| 1 | Cập nhật mã và dựng stack | `git pull`; `.\dx.ps1 up` (có `DEMO_MODE=true` trong `.env`) | `dx up` kết thúc không lỗi |
| 2 | Chẩn đoán | `.\dx.ps1 doctor` | Dòng `DX DOCTOR OK` |
| 3 | Nạp hồ sơ hero | `python scripts/seed_hero.py` | `[PASS] Đã nạp hồ sơ hero` |
| 4 | Chuẩn bị giấy tờ nộp | Đoạn lệnh ở mục 1.1 | Thư mục `demo-giay-to/` có 6 tệp PDF |
| 5 | Tải mô hình trợ lý (nếu dùng Ollama) | `docker compose --profile ai up -d ollama`, rồi kéo mô hình theo `docs/install.md` | Tab **Trợ lý** trả lời có trích dẫn |
| 6 | Diễn tập đủ 9 cảnh | Theo `demo-script.md` | Đi hết không phải dừng |
| 7 | Chụp ảnh và quay video dự phòng | Mục 4 | Có ảnh từng cảnh và video 8–10 phút |
| 8 | Sao lưu trạng thái tốt | `.\dx.ps1 backup` | Ghi lại mã bản sao lưu |
| 9 | Số liệu tác động | `python scripts/impact_metrics.py`, dán vào slide 9 | Slide có ngày đo |

Yêu cầu chấp nhận của hướng dẫn này: **diễn tập 3 lần liên tiếp không lỗi**. Ghi kết quả vào bảng ở mục 5.

### 1.1. Tạo 6 tệp giấy tờ mẫu

Mỗi tệp phải là PDF hợp lệ và khác nhau. Đoạn lệnh lấy tệp mẫu trong repo rồi thêm một dòng chú thích khác nhau vào mỗi bản:

```powershell
New-Item -ItemType Directory -Force demo-giay-to | Out-Null
$mau = [IO.File]::ReadAllBytes("tests\e2e-ui\fixtures\ban_ve_thiet_ke_mau.pdf")
foreach ($loai in "don","giay_to_dat","ban_ve_mat_bang","ban_ve_tang","ban_ve_mong","cam_ket_an_toan") {
  $them = [Text.Encoding]::ASCII.GetBytes("`n% demo-$loai`n")
  [IO.File]::WriteAllBytes("demo-giay-to\$loai.pdf", $mau + $them)
}
```

Thư mục `demo-giay-to/` chỉ dùng trên máy demo, không commit.

### 1.2. Bản PDF đã sửa cho cảnh 8

Sau buổi diễn tập, khi đã có giấy phép:
1. Đăng nhập `cdt.minh`, mở hồ sơ đã cấp phép, bấm **Tải giấy phép (PDF)**.
2. Lưu tệp vào `demo-giay-to\giay-phep.pdf`.
3. Tạo bản đã sửa một byte:

```powershell
$b = [IO.File]::ReadAllBytes("demo-giay-to\giay-phep.pdf")
$b[[int]($b.Length / 2)] = $b[[int]($b.Length / 2)] -bxor 1
[IO.File]::WriteAllBytes("demo-giay-to\giay-phep-da-sua.pdf", $b)
```

Tải bản gốc lên trang tra cứu thì báo **khớp**, tải bản đã sửa thì báo **không khớp**.

## 2. Ba mươi phút trước

- [ ] Máy cắm sạc, tắt thông báo hệ điều hành, tắt cập nhật tự động, độ phân giải chiếu 1920×1080, thu phóng trình duyệt 110–125 %.
- [ ] `.\dx.ps1 ps`: mọi container `healthy`. `.\dx.ps1 doctor` đạt.
- [ ] Mở 4 cửa sổ trình duyệt, mỗi cửa sổ một hồ sơ trình duyệt riêng (Chrome: *Thêm người dùng*):

| Cửa sổ | Địa chỉ | Tài khoản | Dùng ở cảnh |
|---|---|---|---|
| A | `http://<máy>:8080/` | `cdt.minh` | 3, 5, 8 |
| B | `http://<máy>:8080/` | `mc.thu`, rồi `td.binh`, rồi `tt.khanh` | 4, 6, 7 |
| C | `http://<máy>:8080/` | `ld.hoa` | 4, 6, 7, 9 (`/dieu-hanh/`) |
| D | cửa sổ ẩn danh | không đăng nhập; `kt.an` ở `/dieu-hanh/` | 8 |

- [ ] Đăng nhập sẵn cửa sổ A và C. Mật khẩu lấy từ `secrets\demo-accounts.txt`. Không chiếu tệp này lên màn hình.
- [ ] Mở sẵn thư mục `demo-giay-to` trong Explorer để kéo thả tệp.
- [ ] Slide mở sẵn ở slide 1, video dự phòng mở sẵn ở trình phát và tạm dừng ở 0:00.
- [ ] Giấy ghi: mã hồ sơ nộp ở cảnh 3 và mã công khai của giấy phép ở cảnh 6.

## 3. Khi có sự cố

Quy tắc chung: **không sửa lỗi trước khán giả quá 30 giây**. Nói một câu, chuyển sang ảnh hoặc video của cảnh đó, rồi đi tiếp cảnh sau.

| Sự cố | Dấu hiệu | Xử lý ngay (≤ 30 giây) | Nếu vẫn lỗi |
|---|---|---|---|
| Không đăng nhập được | Keycloak báo lỗi hoặc quay vòng | Đóng cửa sổ, mở lại, đăng nhập lại; kiểm tra đúng cửa sổ của vai | Chiếu ảnh cảnh đó; sau demo chạy `.\dx.ps1 doctor` |
| API lỗi (hộp lỗi đỏ **Thử lại**) | Màn hình báo không tải được dữ liệu | Bấm **Thử lại** một lần | Chiếu ảnh; nói "dịch vụ đang khởi động lại", đi cảnh sau |
| Không thấy việc ở **Bàn làm việc** | Danh sách trống | Bấm **Làm mới**; kiểm tra đúng tài khoản và đúng phường | Mở hồ sơ dựng sẵn của cảnh đó hoặc chiếu ảnh |
| Kiểm tra quy hoạch không ra kết quả | Nút quay mãi | Đợi 5 giây, bấm lại **Kiểm tra quy hoạch** | Chiếu ảnh kết quả không đạt/đạt |
| Ký số lỗi ở **Phê duyệt và ký** | Báo lỗi khi xác nhận | Bấm lại một lần | Chiếu ảnh giấy phép và mã công khai từ buổi diễn tập; cảnh 8 dùng `giay-phep.pdf` đã tải ở mục 1.2 |
| Trợ lý không trả lời | Chờ quá 20 giây | Hỏi câu ngắn hơn | Nói "trợ lý chạy tại chỗ, khi không có mô hình sẽ trả nguyên văn đoạn văn bản kèm trích dẫn"; chiếu ảnh |
| Stack chậm | Mỗi thao tác > 5 giây | Bỏ bước tùy chọn (cảnh 4 bước 7, cảnh 7 bước 3–4) | Chuyển sang video từ cảnh đang dở |
| Mất mạng phòng hội trường | Không ra ngoài được Internet | Không ảnh hưởng: stack chạy hoàn toàn trên máy, bản đồ mặc định nền trơn không tải tile | — |
| Mất kết nối tới máy chủ demo | Trình duyệt không mở được `:8080` | Kiểm tra cáp hoặc Wi-Fi nội bộ | Chuyển sang video |
| Máy demo treo | Không thao tác được | Chuyển sang máy dự phòng có video và slide | — |

Khôi phục trạng thái sạch giữa hai buổi diễn tập: `.\dx.ps1 restore --id <mã bản sao lưu> --yes`, rồi `python scripts/seed_hero.py`.

## 4. Dự phòng

<a id="du-phong"></a>

1. **Ảnh chụp từng cảnh.** Chạy bộ test giao diện để tự chụp:

   ```powershell
   $env:E2E_OUT_DIR = "logs\demo-anh"
   python -m pytest tests/e2e-ui/test_demo_flow.py tests/e2e-ui/test_B_design_review_ui.py tests/e2e-ui/test_A_planning_ui.py -q
   ```

   Ảnh nằm trong `logs\demo-anh\`. Chép các ảnh ứng với cảnh 3–9 vào thư mục `slide-du-phong` và đánh số theo cảnh.
2. **Video 8–10 phút** quay đúng theo `demo-script.md` (OBS, 1920×1080, 30 fps, có tiếng). Lưu một bản trên máy demo và một bản trên USB.
3. **Stack offline.** Stack không cần Internet khi chạy. Nếu phải dựng lại trên máy khác, dùng bản phát hành `dist/dxos-<phiên bản>.tar.gz` (`.\dx.ps1 release`) và bản sao lưu ở bước 8.
4. **Máy dự phòng** có slide, video và ảnh, không cần stack.

## 5. Nhật ký diễn tập

| Lần | Ngày giờ | Người chạy | Cảnh lỗi | Thời lượng | Ghi chú |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

Chỉ coi là sẵn sàng khi ba lần liên tiếp không có cảnh lỗi.

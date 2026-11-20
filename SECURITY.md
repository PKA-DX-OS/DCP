<!--
SPDX-FileCopyrightText: 2026 DCP contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Chính Sách An Toàn Thông Tin (Security Policy)

Dự án **DCP** áp dụng mô hình bảo mật nhiều lớp (defense-in-depth) và Zero-Trust nhằm đảm bảo an toàn cho hạ tầng chuyển đổi số công vụ.

---

## Các Phiên Bản Được Hỗ Trợ

| Phiên bản | Được hỗ trợ cập nhật bảo mật |
| :--- | :--- |
| `1.1.x` | :white_check_mark: |
| `1.0.x` | :x: |
| `< 1.0.0` | :x: |

---

## Báo Cáo Lỗ Hổng Bảo Mật

Nếu bạn phát hiện bất kỳ vấn đề hoặc lỗ hổng bảo mật nào trong mã nguồn hoặc kiến trúc của DCP, vui lòng **không công khai** trên các kênh mở hoặc Issue tracker của GitHub.

Quy trình báo cáo có trách nhiệm:
1. Gửi email thông báo chi tiết.
2. Nội dung bao gồm:
   - Mô tả chi tiết lỗ hổng và phạm vi ảnh hưởng.
   - Các bước tái hiện (proof-of-concept).
   - Tác động tiềm ẩn đối với hệ thống.
3. Nhóm bảo mật DCP sẽ phản hồi trong vòng **48 giờ** làm việc và cập nhật tiến độ khắc phục.
4. Sau khi bản vá được phát hành chính thức trong phiên bản mới, thông tin lỗ hổng và người báo cáo (nếu được đồng ý) sẽ được ghi nhận trong phần ghi chú phát hành (Security Advisory).

---

## Các Nguyên Tắc Bảo Mật Cốt Lõi Được Áp Dụng Trong DCP

1. **Không có bí mật trong Git:** Không lưu khóa mã hóa, mật khẩu, JWT secret trong kho mã nguồn. Mọi cấu hình nhạy cảm được sinh ngẫu nhiên khi khởi tạo (`make init`) hoặc mã hóa qua SOPS.
2. **Kiểm soát truy cập đa lớp:** APISIX kiểm tra JWT; PostgREST và các microservices xác thực lại token; PostgreSQL thực thi Row-Level Security (RLS) ở tầng nhân DB.
3. **Kiểm dịch tệp tại cửa ngõ:** Mọi tệp tải lên đều được chuyển vào vùng cách ly `staging` và quét qua ClamAV INSTREAM trước khi lưu vào kho tệp chính.
4. **Phân tách nhiệm vụ (SoD):** Ngăn ngừa người thẩm định tự phê duyệt hồ sơ (`dx:sodExclude`).
5. **Toàn vẹn dữ liệu:** Chuỗi băm kiểm toán `audit_log` chống chỉnh sửa và cơ chế niêm phong WORM định kỳ.
6. **Giới hạn phạm vi của `DEMO_MODE`:** Biến môi trường `DEMO_MODE` chỉ được phép kích hoạt 3 chức năng: bật client `dx-test` và `dx-seed`, cho phép `DEMO_TIME_SCALE`, và hiển thị thông báo mô phỏng trên giao diện. `DEMO_MODE` tuyệt đối KHÔNG được nới lỏng hoặc bỏ qua bất kỳ kiểm soát xác thực, phân quyền, quét tệp mã độc, ký số hay kiểm toán nào.

---

## Thông Báo Thu Hồi Khóa Lộ Lọt (Security Advisory - Key Revocation)

- **Cảnh báo:** Khóa riêng tư `core/nats/certs/server.key` từng vô tình được commit trong phiên bản `v0.8.0` đã chính thức bị **thu hồi và coi là mất an toàn**.
- **Biện pháp xử lý:** Từ phiên bản `v0.9.0`, toàn bộ chứng chỉ và khóa riêng tư TLS được sinh ngẫu nhiên tự động trong bước `.\dx.ps1 init` (hoặc `./dx.sh init`), lưu cục bộ ngoài kho Git và được thêm vào `.gitignore`. Mọi hệ thống vận hành bắt buộc phải sinh cặp khóa mới khi khởi tạo.

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Mốc đo D & H trên v1.1

Đo bằng `python scripts/dh_baseline.py --tenant phuong-a` ngày 2026-11-21, trên dữ liệu demo tổng hợp (không phải số của một phường thật). Kế hoạch: [ke-hoach-dh.md](ke-hoach-dh.md), mục 10.

## H — thao tác của người

| Chỉ số | Mốc |
| :--- | ---: |
| Hồ sơ trong phường | 80 |
| Thao tác thủ công / hồ sơ (TB) | 8.14 |
| Thao tác thủ công / hồ sơ (trung vị) | 7.0 |
| Lần chuyển tay / hồ sơ (TB) | 0.17 |
| Hồ sơ phải bổ sung | 11.2% |
| Vòng bổ sung / hồ sơ phải bổ sung | 1.0 |
| Thao tác do chủ đầu tư tự làm | 29.6% |
| Task Flowable hoàn thành (chưa gắn hồ sơ) | 192 |
| Trích xuất tự động (OCR) | 0 |
| Thời gian nộp → ký (TB) | 0.0 ngày làm việc |
| Ký đúng hạn | 100.0% |

## D — chất lượng dữ liệu hồ sơ

| Chỉ số | Mốc |
| :--- | ---: |
| CCCD sai dạng 12 số | 0.0% |
| Điện thoại sai dạng | 1.2% |
| Thiếu mã định danh địa điểm | 97.5% |
| Thiếu thửa đất | 0.0% |
| CCCD gắn với nhiều họ tên | 7 |
| Hồ sơ trùng CCCD + thửa đất | 42 |
| Tỷ lệ trùng | 52.5% |
| Job có sự kiện lineage | 2 |
| Bản ghi MDM | 0 |

## Đọc số này thế nào

Stack đo là máy phát triển: ngoài seed demo còn hồ sơ do các lần chạy `tests/e2e-ui` và `tests/e2e`
tạo ra, nên vài số phản ánh dữ liệu test chứ không phản ánh quy trình.

- **Trùng CCCD + thửa đất 52,5 %, 7 CCCD gắn nhiều họ tên:** test nộp hồ sơ lặp lại cùng CCCD và thửa
  đất mẫu. Đây chính là loại lỗi mà MDM (D-MDM-02) và rule duy nhất của DQ phải bắt; mốc cho thấy v1.1
  chưa có lớp nào chặn hay gom chúng.
- **Thiếu mã định danh địa điểm 97,5 %:** chỉ hồ sơ hero được gắn mã; luồng nộp hồ sơ không bắt buộc
  trường này. Đây là mục tiêu đầu tiên cho rule DQ đầy đủ (D-DQ-01).
- **Thời gian nộp → ký 0,0 ngày, ký đúng hạn 100 %:** hồ sơ test được nộp và ký trong cùng ngày, không
  dùng để so sánh thời gian xử lý thật.
- **Thao tác thủ công 8,14 / hồ sơ, chuyển tay 0,17, tự phục vụ 29,6 %:** dùng làm mốc so cho H; chưa
  tính 192 lần hoàn thành task Flowable vì chưa gắn được với hồ sơ.

Khi so sánh sau mỗi cổng, đo lại trên cùng loại dữ liệu (seed demo + `scripts/seed_hero.py`, chưa chạy
test e2e) để hai lần đo cùng điều kiện.

## Giới hạn

- Thao tác trên task Flowable chưa gắn được với hồ sơ (audit chỉ có `task_id`); D-MET-00 bổ sung `ho_so_id` rồi đo lại.
- Chuyển tay đếm theo người sửa liên tiếp trong `ho_so_lich_su`; cập nhật do dịch vụ (không có `sub`) không tính.

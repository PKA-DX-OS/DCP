<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Mốc đo D & H trên v1.1

Đo bằng `python scripts/dh_baseline.py --tenant phuong-a` ngày 2026-11-22, trên dữ liệu demo tổng hợp (không phải số của một phường thật). Kế hoạch: [ke-hoach-dh.md](ke-hoach-dh.md), mục 10.

## H — thao tác của người

| Chỉ số | Mốc |
| :--- | ---: |
| Hồ sơ trong phường | 487 |
| Thao tác thủ công / hồ sơ (TB) | 8.28 |
| Thao tác thủ công / hồ sơ (trung vị) | 5.0 |
| Lần chuyển tay / hồ sơ (TB) | 0.13 |
| Hồ sơ phải bổ sung | 3.3% |
| Vòng bổ sung / hồ sơ phải bổ sung | 1.0 |
| Thao tác do chủ đầu tư tự làm | 29.1% |
| Task Flowable hoàn thành (chưa gắn hồ sơ) | 870 |
| Trích xuất tự động (OCR) | 0 |
| Thời gian nộp → ký (TB) | 0.0 ngày làm việc |
| Ký đúng hạn | 100.0% |

## D — chất lượng dữ liệu hồ sơ

| Chỉ số | Mốc |
| :--- | ---: |
| CCCD sai dạng 12 số | 0.0% |
| Điện thoại sai dạng | 0.0% |
| Thiếu mã định danh địa điểm | 99.6% |
| Thiếu thửa đất | 0.0% |
| CCCD gắn với nhiều họ tên | 10 |
| Hồ sơ trùng CCCD + thửa đất | 266 |
| Tỷ lệ trùng | 54.6% |
| Job có sự kiện lineage | 7 |
| Bản ghi MDM | 91 |

## Đọc số này thế nào

Stack đo là máy phát triển: ngoài seed demo còn hồ sơ do các lần chạy `tests/e2e-ui` và `tests/e2e`
tạo ra, nên vài số phản ánh dữ liệu test chứ không phản ánh quy trình.

- **Trùng CCCD + thửa đất 54,6 %, 10 CCCD gắn nhiều họ tên:** test nộp hồ sơ lặp lại cùng CCCD và thửa
  đất mẫu. Đây là loại lỗi MDM (D-MDM-02) và rule duy nhất của DQ phải bắt; mốc cho thấy dữ liệu v1.1
  chưa được gom sạch.
- **Thiếu mã định danh địa điểm 99,6 %:** chỉ hồ sơ hero được gắn mã; luồng nộp hồ sơ không bắt buộc
  trường này. Đây là mục tiêu đầu tiên cho rule DQ đầy đủ (D-DQ-01).
- **Thời gian nộp → ký 0,0 ngày, ký đúng hạn 100 %:** hồ sơ test được nộp và ký trong cùng ngày, không
  dùng để so sánh thời gian xử lý thật.
- **870 task Flowable hoàn thành chưa gắn hồ sơ:** phần lớn là audit cũ trước D-MET-00; chỉ số này sẽ
  giảm khi đo lại trên dữ liệu mới, không dùng để kết luận quy trình hiện tại.
- **Thao tác thủ công 8,28 / hồ sơ, chuyển tay 0,13, tự phục vụ 29,1 %:** dùng làm mốc so cho H.
- **MDM 91 bản ghi, lineage 7 job:** MDM/lineage đã có dữ liệu thật; tiếp tục backfill construction và
  kiểm tra chất lượng liên kết trước khi công bố.

Khi so sánh sau mỗi cổng, đo lại trên cùng loại dữ liệu (seed demo + `scripts/seed_hero.py`, chưa chạy
test e2e) để hai lần đo cùng điều kiện.

## Giới hạn

- Thao tác trên task Flowable chưa gắn được với hồ sơ (audit chỉ có `task_id`); D-MET-00 bổ sung `ho_so_id` rồi đo lại.
- Chuyển tay đếm theo người sửa liên tiếp trong `ho_so_lich_su`; cập nhật do dịch vụ (không có `sub`) không tính.

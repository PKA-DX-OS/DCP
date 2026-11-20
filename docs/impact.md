<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Chỉ số tác động

Số liệu cho slide 9 và cảnh 9 của [demo-script.md](demo-script.md). Nguyên tắc: **con số nào cũng phải chạy lại được**. Phần đo từ hệ thống lấy bằng `scripts/impact_metrics.py`. Phần không đo được ghi rõ là **giả định** và nói cách giả định. Không đưa lên slide con số không có nguồn.

## Chạy

```bash
python scripts/impact_metrics.py                     # phường A, qua docker exec dxos-postgres
python scripts/impact_metrics.py --tenant phuong-b
python scripts/impact_metrics.py --json > logs/impact.json   # để dán vào slide
```

Nên chạy **sau khi đi hết kịch bản demo một lần**, để có ít nhất một giấy phép đã ký và một lần kiểm tra quy hoạch không đạt. Dữ liệu demo là dữ liệu tổng hợp, nên số liệu mô tả hệ thống trên bộ dữ liệu đó, không phải số đo tại một phường thật. Trên slide ghi kèm dòng "Đo trên dữ liệu demo ngày …".

## Chỉ số đo từ hệ thống

| Chỉ số | Cách tính | Nguồn dữ liệu |
|---|---|---|
| Thời gian xử lý | Số ngày làm việc (thứ Hai đến thứ Sáu, giờ Việt Nam, chưa trừ ngày lễ) từ lúc nộp đến lúc ký giấy phép; in trung bình và tối đa, so với thời hạn luật **07 ngày làm việc** (Điều 54 NĐ 217/2026/NĐ-CP) | `ho_so.created_at`, `giay_phep.ngay_cap` |
| Tỷ lệ ký đúng hạn | Giấy phép ký trước hạn tổng của hồ sơ / tổng giấy phép | `ho_so.han_tong_at`, `giay_phep.ngay_cap` |
| Tỷ lệ đóng đúng hạn | Hồ sơ đã cấp hoặc từ chối mà không bị gắn quá hạn / hồ sơ đã đóng | `ho_so.trang_thai`, `ho_so.qua_han` |
| Số kiểm tra tự động | Số lần kiểm tra quy hoạch + tệp đã quét virus + bản vẽ đã đánh giá + văn bản ký số + mốc nghiệm thu đã có kết quả | các bảng tương ứng trong `app_construction`, `app_cap_phep`, `core` |
| Hồ sơ phát hiện sai quy hoạch sớm | Số hồ sơ có ít nhất một lần kiểm tra quy hoạch không đạt (phát hiện ở bước thẩm định, trước khi thiết kế được duyệt) | `ket_qua_kiem_tra_quy_hoach.pass` |
| Hồ sơ phải bổ sung | Số hồ sơ từng ở trạng thái cần bổ sung | `ho_so_lich_su.snapshot` |
| Tệp bị chặn vì virus | Tệp quét ra nhiễm | `core.files.status` |
| Mốc nghiệm thu không đạt | Lần nghiệm thu ghi không đạt (sai sót được ghi lại thay vì bỏ qua) | `moc_nghiem_thu.ket_qua` |
| Số vòng thiết kế | Số phiên bản thiết kế trung bình trên một hồ sơ | `phien_ban_thiet_ke.so_phien_ban` |

**Giới hạn cần nói khi trình bày:**
- Không có số liệu "trước khi có hệ thống" của phường, nên chỉ so được với **thời hạn luật**, không so được trước và sau.
- Hồ sơ lịch sử do seed tạo không có giấy phép ký số, nên không tính vào thời gian nộp đến ký. Chỉ hồ sơ đi hết quy trình thật (như hồ sơ ở cảnh 3–6) mới được tính.
- "Số vòng thiết kế giảm" chỉ đo được khi có dữ liệu nhiều tháng; hiện chỉ in số vòng thực tế.

## Giả định (không phải số đo)

| Chỉ số | Giá trị dùng trên slide | Cách giả định |
|---|---|---|
| Giấy tờ giảm | 6 tệp điện tử, nộp một lần | Thành phần bắt buộc theo Điều 60 NĐ 217/2026 (đơn Mẫu số 01, giấy tờ đất, ba bản vẽ, bản cam kết) nộp dạng tệp. Hệ thống báo thiếu ngay khi nộp, không phải mang lại. Khi kết nối CSDL đất đai thì giấy tờ đất đã có trên CSDL quốc gia không phải nộp (Điều 56 khoản 3); kết nối này **chưa làm**. Chưa đo tại phường thật. |
| Mức độ hài lòng | chưa đo | Không có số liệu. Đề xuất khảo sát 5 mức ngay sau khi người dân nhận kết quả. **Không đưa con số hài lòng lên slide** trước khi khảo sát. |

## Gợi ý trình bày slide 9

Ba con số lớn lấy từ đầu ra của script:
1. Thời gian nộp đến ký so với 7 ngày làm việc luật định.
2. Số lần kiểm tra tự động.
3. Số hồ sơ phát hiện sai quy hoạch sớm.

Dưới ba con số đặt một dòng nhỏ: "Đo trên dữ liệu demo tổng hợp ngày …; giấy tờ giảm là giả định, mức hài lòng chưa đo".

Căn cứ pháp lý trích từ bộ `TaiLieuHanhChinh_C3`: `03_PHAN_TICH/05_DANH_MUC_TTHC_CAP_PHEP.md` (Điều 54, 56, 60 NĐ 217/2026/NĐ-CP).

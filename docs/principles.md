<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Bốn Nguyên Lý Định Hướng Của DX-OS Open-Core

DX-OS Open-Core (v5) được thiết kế hiện thực hóa trọn vẹn 4 nguyên lý kiến trúc chuyển đổi số do Hội Tin học Việt Nam (VAIP) và VFOSSA định hướng trong đề thi OLP PMNM 2026.

---

## Nguyên Lý 1: Phân Tách Theo Vòng Đời và Tốc Độ Dữ Liệu

### 1.1 Khái niệm & Thiết kế
Hệ thống phân tách rõ rệt giữa hai luồng dữ liệu:
- **Dữ liệu Nóng (Hot Data - Giao dịch tức thời):** Toàn bộ hồ sơ đang trong quá trình thụ lý (`DA_NOP`, `DANG_THAM_DINH`, `CHO_DUYET`) cùng các số liệu cảm biến tức thời được lưu trữ tại PostgreSQL (với RLS và Transactional Outbox) và hàng đợi sự kiện bộ nhớ nhanh NATS JetStream.
- **Dữ liệu Ấm/Lạnh (Warm/Cold Data - Lưu trữ phân tích hồ sơ):** Sau khi hồ sơ được cấp phép và hoàn tất thủ tục quá 7 ngày, hoặc dữ liệu chuỗi thời gian (timeseries) vượt quá 7 ngày, dịch vụ `export-warm` sẽ tự động đóng gói dữ liệu sang định dạng cột nén cao **Apache Parquet**, lưu trữ trên Data Lake (`lake/<app>/<bảng>/tenant=<t>/thang=<yyyy-mm>/`). Bảng điều hành sử dụng **DuckDB** để tính toán tổng hợp các chỉ số báo cáo từ tệp Parquet mà không làm nghẽn hiệu năng của cơ sở dữ liệu giao dịch chính.

### 1.2 Vị trí trong mã nguồn
- Dịch vụ kết xuất định kỳ: [`services/export-warm/`](../services/export-warm/)
- Dịch vụ truy vấn phân tích DuckDB: [`services/metrics-api/`](../services/metrics-api/)
- Định nghĩa phân vùng hồ sơ trong PostgreSQL: [`core/postgres/01-core-schema.sql`](../core/postgres/01-core-schema.sql)

### 1.3 Lệnh trình diễn (Demo Command)
```bash
# Thực hiện kết xuất hồ sơ đóng sang kho Parquet ngay lập tức
# gọi POST /api/v1/export-warm/run?month=YYYY-MM

# Kiểm tra tệp Parquet được sinh ra trên bucket lake
docker compose exec seaweedfs s3cmd ls s3://lake/
```

---

## Nguyên Lý 2: Hội Tụ IT / OT (Information Technology / Operational Technology)

### 1.1 Khái niệm & Thiết kế
Xóa nhòa khoảng cách giữa hệ thống thông tin quản lý hành chính (IT) và hệ thống cảm biến giám sát hiện trường (OT):
- Các thiết bị đo lường môi trường IoT đặt tại các công trình xây dựng (đo độ ồn tương đương $L_{Aeq}$ theo dBA, bụi mịn PM10/PM2.5) truyền số liệu liên tục qua giao thức công nghiệp nhẹ **MQTT với mã hóa TLS** (cổng `8883`) vào NATS Server.
- Dịch vụ `ingest` áp dụng bộ quy tắc nghiệp vụ theo khung giờ (QCVN 26:2025/BNNMT: 70 dBA ban ngày 6h-21h, 55 dBA ban đêm 21h-6h).
- Khi phát hiện độ ồn vượt ngưỡng liên tục trong cửa sổ tính toán (1 giờ hoặc đột biến trong kịch bản demo), dịch vụ tự động phát sự kiện `alert.threshold` qua outbox. Dịch vụ `flow` bắt sự kiện và **tự động khởi tạo quy trình Hậu kiểm công trường (`hau-kiem`)**, phân việc trực tiếp cho cán bộ Đội Trật tự xây dựng mà không cần sự can thiệp thủ công của con người.

### 1.2 Vị trí trong mã nguồn
- Bộ giả lập thiết bị cảm biến công trường: [`tools/sensor-sim/`](../tools/sensor-sim/)
- Dịch vụ nạp dữ liệu & kiểm tra ngưỡng: [`services/ingest/`](../services/ingest/)
- Quy tắc ngưỡng môi trường theo giờ: [`apps/cap-phep/rules/nguong.yaml`](../apps/cap-phep/rules/nguong.yaml)
- Quy trình BPMN Hậu kiểm: [`apps/cap-phep/bpmn/hau-kiem.bpmn20.xml`](../apps/cap-phep/bpmn/hau-kiem.bpmn20.xml)

### 1.3 Lệnh trình diễn (Demo Command)
```bash
# Kích hoạt giả lập phát sinh đột biến tiếng ồn 78 dBA vượt ngưỡng ban ngày
python tools/sensor-sim/sim.py --tenant phuong-a --spike --duration 30

# Xem phiếu kiểm tra công trường tự động xuất hiện trong danh sách việc cán bộ
```

---

## Nguyên Lý 3: Quản Trị Dữ Liệu: Phả Hệ (Lineage) và Chất Lượng (Quality)

### 1.1 Khái niệm & Thiết kế
- **Phả hệ dữ liệu (Data Lineage theo chuẩn OpenLineage):** Mọi tác vụ tổng hợp dữ liệu (từ sự kiện nhận cảm biến, giao dịch nộp hồ sơ, tác vụ kết xuất Parquet `export-warm`, đến các chỉ số tính toán trên Bảng điều hành) đều ghi nhận một sự kiện `core.lineage_events` gồm đầu vào (`inputs`), đầu ra (`outputs`), thời điểm và job thực thi. Người dùng khi xem bất kỳ chỉ số nào trên Bảng điều hành đều có thể bấm để xem lại toàn bộ "gia phả" hình thành nên số liệu đó.
- **Chất lượng dữ liệu (Data Quality):**
  - Toàn bộ dữ liệu nạp vào đều được kiểm tra tính hợp lệ về cấu trúc JSON Schema.
  - Dữ liệu tệp đính kèm được quét mã độc tại cửa ngõ bằng ClamAV, kiểm tra MIME type và magic bytes thực tế.
  - Cơ chế nhận diện thiết bị mất tín hiệu (`alert.device_silent`) tự động cảnh báo khi không nhận được bản tin từ công trường quá 30 phút.

### 1.2 Vị trí trong mã nguồn
- Bảng ghi nhận phả hệ: Bảng `core.lineage_events`
- API truy xuất phả hệ: [`services/metrics-api/`](../services/metrics-api/)
- Giao diện trực quan hóa phả hệ: [`apps/bang-dieu-hanh/web/`](../apps/bang-dieu-hanh/web/)

### 1.3 Lệnh trình diễn (Demo Command)
1. Mở Bảng điều hành tại `http://localhost:8080/dieu-hanh/`.
2. Bấm vào chỉ số "Hồ sơ mới trong kỳ" hoặc "Cảnh báo công trường".
3. Cửa sổ phả hệ mở ra hiển thị chuỗi sự kiện OpenLineage minh bạch từ nguồn gốc tới kết quả.

---

## Nguyên Lý 4: Zero-Trust Gắn GitOps (Kiểm Dịch Tại Cửa Ngõ, Cấu Hình Bằng Mã, Tự Phục Hồi)

### 1.1 Khái niệm & Thiết kế
- **Kiểm dịch tại cửa ngõ (Quarantine at the Gate):** Không có tệp tin nào được đưa thẳng vào hệ thống lưu trữ mà chưa qua khu vực kiểm dịch `staging` và quét mã độc ClamAV. Tệp chứa mã độc (như mẫu EICAR) bị chặn ngay lập tức tại cổng API.
- **Zero-Trust Trong Phân Quyền:** Mặc định từ chối (Deny by Default). Mọi truy cập vào hồ sơ xây dựng đều phải thông qua hàm `core.can_access` và RLS. Truy cập ngoài phân công bị chặn 403 và ghi nhật ký kiểm toán.
- **Chuỗi kiểm toán bất biến (Cryptographic Audit Chain):** Mỗi hành vi ghi/sửa/xóa trong DB đều được xâu chuỗi băm SHA-256 (`prev_hash || hash`). Bất kỳ thao tác chỉnh sửa trực tiếp vào cơ sở dữ liệu đều làm đứt chuỗi và bị phát hiện ngay lập tức.
- **Cấu hình bằng mã (GitOps) & Tự phục hồi:** Toàn bộ cấu hình hệ thống (routes APISIX, schema DB, quy trình BPMN, compose containers) được quản lý trong Git. Công cụ `ops/reconciler` định kỳ kiểm tra digest container đang chạy với thẻ release đã ký bằng `cosign`. Nếu ai đó sửa tay file trên máy chủ hoặc container bị sự cố, hệ thống sẽ tự động khôi phục về trạng thái chuẩn trong Git.
- **Khóa ký không nằm trong Git:** Private key PAdES nằm trong token SoftHSM2/PKCS#11; source chỉ chứa code gọi token và test CA công khai. Đây là ranh giới giữa cấu hình (Git) và bí mật (HSM).

### 1.2 Vị trí trong mã nguồn
- Cơ chế kiểm dịch tệp: [`services/files/`](../services/files/)
- Trigger băm chuỗi kiểm toán: [`core/postgres/01-core-schema.sql`](../core/postgres/01-core-schema.sql)
- Dịch vụ kiểm tra chuỗi băm: [`services/audit/`](../services/audit/)
- SoftHSM + PAdES: [`scripts/softhsm_init.sh`](../scripts/softhsm_init.sh), [`services/doc-sign/`](../services/doc-sign/)
- GitOps Reconciler: `ops/reconciler/` (C12, chưa có trong bản này)

### 1.3 Lệnh trình diễn (Demo Command)
```bash
# 1. Kiểm tra tính toàn vẹn chuỗi kiểm toán hiện tại
python scripts/verify_audit.py

# 2. Chạy một chu kỳ đối soát GitOps Reconciler
# C12: python ops/reconciler/reconciler.py

# 3. Thử nghiệm nộp tệp kiểm dịch EICAR
python scripts/upload_eicar.py
```

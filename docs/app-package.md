<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Đặc Tả Hợp Đồng Gói Ứng Dụng (App Package Contract)

Hệ sinh thái **DX-OS Open-Core (v5)** áp dụng kiến trúc cắm-rút (Pluggable Architecture). Tầng 1 hoàn toàn độc lập với nghiệp vụ (Headless & Domain-Agnostic). Toàn bộ nghiệp vụ chuyên ngành được đóng gói thành các **Gói Ứng Dụng (App Packages)** đặt trong thư mục `apps/<app_code>/`.

---

## 1. Cấu Trúc Thư Mục Chuẩn Của Một Gói Ứng Dụng

```
apps/<app_code>/
├─ app.yaml              # Tệp hợp đồng khai báo siêu dữ liệu bắt buộc
├─ db/migrations/        # Các tệp kịch bản SQL khởi tạo schema, bảng, RLS và hàm RPC
├─ bpmn/                 # Các tệp định nghĩa quy trình BPMN 2.0 XML
├─ templates/            # Các mẫu phôi tài liệu (HTML/Jinja2) phục vụ doc-sign
├─ rules/                # Các tệp quy tắc xử lý cảm biến và ngưỡng cảnh báo (YAML)
├─ knowledge/            # Các tài liệu tri thức (Markdown) phục vụ Trợ lý AI (RAG)
├─ seed/                 # Kịch bản nạp dữ liệu mẫu ban đầu
└─ web/                  # Ứng dụng giao diện người dùng (SPA)
```

---

## 2. Đặc Tả Tệp Khai Báo `app.yaml`

Mọi gói ứng dụng bắt buộc phải có tệp `app.yaml` tại thư mục gốc của app với cấu trúc như sau:

```yaml
# Định danh mã gói ứng dụng (chữ thường, gạch ngang)
code: cap-phep

# Tên hiển thị đầy đủ của ứng dụng
name: Ứng dụng Cấp phép Xây dựng Nhà ở Riêng lẻ và Hậu kiểm Công trường

# Phiên bản của gói ứng dụng theo SemVer
version: 1.0.0

# Tên schema riêng biệt trong PostgreSQL dành cho ứng dụng này
schema: app_cap_phep

# Danh sách các vai trò nghiệp vụ (Roles) cần tự động tạo trong Keycloak Realm
roles:
  - code: chu-dau-tu
    name: Chủ đầu tư nộp hồ sơ
    description: Công dân hoặc tổ chức nộp hồ sơ xin cấp phép
  - code: mot-cua
    name: Cán bộ Tiếp nhận Một cửa
    description: Tiếp nhận, kiểm tra hồ sơ ban đầu
  - code: tham-dinh
    name: Thẩm định viên
    description: Thẩm định nội dung kỹ thuật hồ sơ
  - code: lanh-dao
    name: Lãnh đạo phê duyệt
    description: Phân công thẩm định và duyệt cấp giấy phép
  - code: trat-tu-xd
    name: Cán bộ Trật tự xây dựng
    description: Hậu kiểm công trường và xử lý cảnh báo

# Danh sách các tệp quy trình BPMN cần deploy vào Flowable Engine
bpmn:
  - bpmn/cap-phep.bpmn20.xml
  - bpmn/hau-kiem.bpmn20.xml

# Khai báo các mẫu tài liệu phục vụ ký số (doc-sign)
doc_templates:
  - doc_type: giay-phep-xay-dung
    template_file: templates/giay-phep.html
    title: Giấy phép xây dựng nhà ở riêng lẻ

# Khai báo quy tắc xử lý dữ liệu cảm biến và ngưỡng cảnh báo
ingest_rules:
  rules_file: rules/nguong.yaml

# Thư mục chứa tài liệu tri thức dùng cho RAG Trợ lý AI
knowledge:
  dir: knowledge/

# Manifest giấy tờ bắt buộc theo thủ tục (P1)
# UI sinh checklist động; app-install seed vào app_cap_phep.document_requirements
document_manifest:
  thu_tuc: cap-phep-nha-o-rieng-le
  ten: Cấp phép xây dựng nhà ở riêng lẻ
  requirements:
    - loai: don
      ten: Đơn xin cấp phép xây dựng
      bat_buoc: true
      yeu_cau_hieu_luc: false
      thong_tin: [ho_ten, cccd]
    - loai: giay_to_dat
      ten: Giấy chứng nhận quyền sử dụng đất
      bat_buoc: true
      yeu_cau_hieu_luc: true
      thong_tin: [so_thua, dien_tich]
    - loai: ban_ve_mat_bang
      ten: Bản vẽ mặt bằng
      bat_buoc: true

# Khai báo các chỉ số đo lường hiển thị trên Bảng điều hành (8 chỉ số theo đặc tả C3)
metrics:
  - code: ho_so_moi
    name: Hồ sơ mới trong kỳ
    unit: hồ sơ
    query_type: lakehouse
    sql: "SELECT count(*) FROM app_cap_phep.ho_so WHERE tenant = $1"
  - code: ho_so_dang_xu_ly
    name: Hồ sơ đang xử lý
    unit: hồ sơ
    query_type: transactional
  - code: ho_so_qua_han
    name: Hồ sơ quá hạn xử lý
    unit: hồ sơ
    query_type: transactional
  - code: thoi_gian_xu_ly_tb
    name: Thời gian xử lý trung bình
    unit: ngày
    query_type: hybrid
  - code: truy_cap_tu_choi
    name: Lượt truy cập hồ sơ bị từ chối (403)
    unit: lượt
    query_type: audit
  - code: phieu_kiem_tra
    name: Số phiếu kiểm tra hiện trường
    unit: phiếu
    query_type: transactional
  - code: canh_bao_cong_truong
    name: Cảnh báo tiếng ồn & bụi vượt ngưỡng
    unit: lượt
    query_type: transactional
  - code: vi_pham
    name: Số vụ vi phạm đã kết luận
    unit: vụ
    query_type: transactional

# Khai báo tệp nạp dữ liệu mẫu
seed:
  script: seed/seed.py
```

---

## 3. Quy Trình Vòng Đời Ứng Dụng (Lifecycle Commands)

### 3.1 Cài đặt Gói Ứng dụng vào Lõi (`make app-install`)
Lệnh `make app-install APP=<app_code>` thực hiện tự động các bước:
1. Đọc tệp `apps/<app_code>/app.yaml`.
2. Thực thi các tệp SQL migration trong `db/migrations/` để tạo schema và bảng trong PostgreSQL.
3. Đồng bộ danh sách vai trò (`roles`) vào Keycloak realm `dxos` dưới tiền tố `app:<app_code>:<role_code>`.
4. Gửi các tệp quy trình BPMN trong `bpmn/` qua REST API của Flowable để kích hoạt luồng nghiệp vụ.
5. Đăng ký các mẫu phôi `doc_templates` vào cấu hình của dịch vụ `doc-sign`.
6. Nạp các tài liệu văn bản từ thư mục `knowledge/` vào cơ sở dữ liệu vector (`core.knowledge_chunks`) phục vụ Trợ lý AI.

### 3.2 Gỡ bỏ Gói Ứng dụng khỏi Lõi (`make app-uninstall`)
Lệnh `make app-uninstall APP=<app_code>` thực hiện:
1. Hủy kích hoạt và lưu trữ các quy trình BPMN tương ứng.
2. Xóa bỏ các vai trò đặc thù của ứng dụng khỏi Keycloak.
3. Thu hồi quyền truy cập API PostgREST đối với schema của ứng dụng.
4. **Phép thử tính toàn vẹn (Decoupling Test):** Sau khi gỡ bỏ gói ứng dụng, Lõi Tầng 1 vẫn hoạt động bình thường, toàn bộ dịch vụ mỏng của Lõi và các kiểm thử đơn vị của Lõi vẫn vượt qua 100%.

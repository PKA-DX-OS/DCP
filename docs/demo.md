<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Hướng Dẫn Kịch Bản Trình Diễn Chi Tiết 11 Bước (DX-OS Demo Guide)

Tài liệu này hướng dẫn chi tiết kịch bản trình diễn trọn vẹn 11 bước của nền tảng **DX-OS Open-Core (Tầng 1 & Tầng 2 - Ứng dụng C3 Cấp phép Xây dựng và Hậu kiểm Công trình)** cho Ban Giám khảo và người dùng trải nghiệm thực tế.

---

## 1. Môi Trường & Danh Sách Tài Khoản Trình Diễn

### 1.1 Khởi động và chuẩn bị hệ thống
- Hệ thống đã khởi tạo hoàn tất qua:
  ```powershell
  .\dx.ps1 init
  .\dx.ps1 up
  .\dx.ps1 app-install cap-phep
  .\dx.ps1 seed
  ```
- **Tệp mảnh khóa OpenBao KMS:** Được lưu tại `secrets/bao-unseal.json` (dùng để mở niêm phong OpenBao khi cần qua `.\dx.ps1 bao-unseal` hoặc `./dx.sh bao-unseal`).
- **Mật khẩu tài khoản demo:** Được sinh ngẫu nhiên an toàn khi chạy `seed` và lưu tại tệp **`secrets/demo-accounts.txt`**. Mở tệp này để lấy mật khẩu đăng nhập của từng tài khoản.

### 1.2 Danh sách 9 tài khoản được sử dụng trong 11 bước

| Tài khoản | Họ và tên (mẫu) | Vai trò hệ thống | Đơn vị (Tenant) | Vai trò trong kịch bản Demo |
| :--- | :--- | :--- | :--- | :--- |
| `cdt.minh` | Trần Văn Minh | `app:cap-phep:chu-dau-tu` | `phuong-a` | Chủ đầu tư chính: nộp hồ sơ, bổ sung, quản lý DSAR, xem nhật ký truy cập |
| `cdt.lan` | Lê Thị Lan | `app:cap-phep:chu-dau-tu` | `phuong-a` | Chủ đầu tư đối chứng: kiểm tra cô lập dữ liệu và thông báo giữa các công dân |
| `mc.thu` | Nguyễn Thị Thu | `app:cap-phep:mot-cua` | `phuong-a` | Cán bộ Một cửa: tiếp nhận hồ sơ, yêu cầu bổ sung, nhận chuông thông báo |
| `ld.hoa` | Phạm Thanh Hoa | `app:cap-phep:lanh-dao` | `phuong-a` | Lãnh đạo UBND: phân công thẩm định, duyệt truy cập khẩn, ký số giấy phép |
| `td.binh` | Hoàng Văn Bình | `app:cap-phep:tham-dinh` | `phuong-a` | Thẩm định viên được phân công: thẩm định kỹ thuật, kiểm tra phân tách nhiệm vụ (SoD) |
| `td.cuong` | Vũ Quốc Cường | `app:cap-phep:tham-dinh` | `phuong-a` | Thẩm định viên chưa phân công: tra cứu hồ sơ theo mã, yêu cầu truy cập khẩn |
| `tt.khanh` | Đặng Quốc Khánh | `app:cap-phep:trat-tu-xd` | `phuong-a` | Cán bộ Trật tự XD: giám sát cảm biến tiếng ồn IoT, lập và xử lý phiếu hậu kiểm |
| `kt.an` | Đỗ Văn An | `dx:auditor` | `phuong-a` | Kiểm toán viên: giám sát tuân thủ, kiểm tra chuỗi băm bất biến WORM |
| `admin` | Quản trị Toàn cục | `dx:platform-admin` | `global` | Quản trị viên hệ thống: kiểm tra toàn cảnh dịch vụ và hạ tầng |

---

## 2. Kịch Bản Trình Diễn Chi Tiết 11 Bước

### Bước 1: Nộp hồ sơ xin cấp phép trực tuyến & Kiểm dịch an toàn tệp tải lên
- **Mục tiêu:** Thể hiện dịch vụ công trực tuyến thân thiện, kiểm soát an toàn tệp tải lên (ClamAV) và bảo vệ dữ liệu cá nhân theo nguyên tắc đồng thuận riêng biệt.
- **Thực hiện:**
  1. Mở trình duyệt truy cập `http://localhost:8080/`.
  2. Bấm nút **"Đăng nhập với tài khoản của bạn"** -> Hệ thống chuyển hướng qua Keycloak SSO. Đăng nhập bằng tài khoản `cdt.minh`.
  3. Bấm **"Nộp hồ sơ mới"**.
  4. Điền thông tin:
     - Họ tên: `Trần Văn Minh`, CCCD: `001200112233`, Điện thoại: `0912345678`.
     - Địa chỉ công trình: `Số 123 Đường Hoa Phượng, Phường A`.
     - Thửa đất: `T-102`, Số tầng: `3`, Diện tích sàn: `150 m²`.
     - Tích chọn đồng thuận dữ liệu cá nhân (từng mục đích riêng biệt).
  5. **Thử chặn thiếu giấy (Poka-yoke):** Bấm **"Kiểm tra và nộp hồ sơ"** khi chưa tải giấy tờ -> hệ thống trả **422** và hiện đúng 6 lỗi thiếu: Đơn, Giấy đất, Bản vẽ mặt bằng, Bản vẽ tầng, Bản vẽ móng, Cam kết an toàn.
  6. Tải đủ 6 giấy bắt buộc bằng checklist động. Với **Giấy chứng nhận QSDĐ**, nhập ngày cấp `01/01/2020`, ngày hết hạn `01/01/2035` (nếu nhập ngày hết hạn trong quá khứ -> 422 "Giấy tờ đã hết hạn").
  7. **Thử nhất quán chéo (L5):** Sau khi chọn tệp, sửa Diện tích sàn từ `150` thành `200` rồi nộp -> 422 "Diện tích trên giấy đất khác hồ sơ".
  8. Sửa lại đúng số liệu và bấm **"Kiểm tra và nộp hồ sơ"**.
- **Kết quả mong đợi trên màn hình:** Thông báo nộp hồ sơ thành công; hồ sơ mới xuất hiện ở đầu bảng với mã hồ sơ dạng `CP-2026-xxxxxx`, trạng thái `DA_NOP`. Mở **Chi tiết** thấy danh sách 6 giấy tờ kèm trạng thái "Chờ kiểm tra".
- **Ghi chú kỹ thuật:** Manifest nằm trong `apps/cap-phep/app.yaml` (`document_manifest`); RPC `nop_ho_so` kiểm tra lại toàn bộ ở server, không tin UI.

---

### Nhánh Bổ sung hồ sơ: Yêu cầu bổ sung ➔ Chủ đầu tư bổ sung ➔ Một cửa nhận lại
- **Mục tiêu:** Minh họa quy trình tương tác hai chiều minh bạch giữa cơ quan chính quyền và công dân khi hồ sơ cần hoàn thiện.
- **Thực hiện:**
  1. Đăng xuất `cdt.minh`, đăng nhập tài khoản một cửa `mc.thu`.
  2. Vào tab **"Việc của tôi"**, chọn nhiệm vụ `Kiểm tra hồ sơ hợp lệ` của hồ sơ vừa nộp.
  3. Chọn **"Cần bổ sung giấy tờ"**, bấm **"Gửi yêu cầu bổ sung"**, nhập lý do: *"Bản vẽ thiếu mặt đứng và chỉ giới đường đỏ, đề nghị chủ đầu tư bổ sung bản vẽ chi tiết"*, rồi xác nhận.
  4. Trạng thái hồ sơ chuyển sang `CAN_BO_SUNG`.
  5. Đăng xuất `mc.thu`, đăng nhập lại `cdt.minh`.
  6. Trong danh sách hồ sơ, hồ sơ hiện trạng thái `Cần bổ sung hồ sơ` kèm nút **"Bổ sung"**.
  7. Bấm vào nút "Bổ sung hồ sơ" (hoặc nút trong modal Chi tiết):
     - Modal hiện rõ ràng dòng chữ: **"Phường yêu cầu bổ sung: Bản vẽ thiếu mặt đứng và chỉ giới đường đỏ..."**.
     - Đính kèm tệp bản vẽ bổ sung `ban-ve-bo-sung.pdf` và bấm **"Gửi bổ sung"**.
  8. Hồ sơ chuyển trạng thái `TIEP_NHAN`.
  9. Đăng nhập lại `mc.thu`: Hồ sơ đã sẵn sàng, bấm **"Tiếp nhận hồ sơ"**.
- **Kết quả mong đợi trên màn hình:** Modal bổ sung hiển thị chính xác lý do yêu cầu từ cán bộ; công dân tải tệp bổ sung thành công; hồ sơ quay trở lại quy trình xử lý của cán bộ một cửa.

---

### Bước 2: Tiếp nhận Một cửa và chuyển giao quy trình
- **Mục tiêu:** Kiểm tra thành phần hồ sơ và chuyển giao bước quy trình số tự động qua Flowable BPMN.
- **Thực hiện:**
  1. Đăng nhập tài khoản Một cửa `mc.thu`.
  2. Vào tab **"Việc của tôi"**.
  3. Chọn hồ sơ tại danh sách "Việc cần xử lý", kiểm tra thông tin hồ sơ và tệp đính kèm. Bấm **"Tiếp nhận hồ sơ"**.
- **Kết quả mong đợi trên màn hình:** Nhiệm vụ của `mc.thu` hoàn thành và biến mất khỏi danh sách việc; hồ sơ chuyển sang trạng thái `TIEP_NHAN` và bước quy trình tự động chuyển sang hàng việc của Lãnh đạo.

---

### Bước 3: Lãnh đạo phân công thẩm định viên
- **Mục tiêu:** Lãnh đạo UBND phân công hồ sơ cho thẩm định viên đúng chuyên môn trên địa bàn.
- **Thực hiện:**
  1. Đăng xuất `mc.thu`, đăng nhập tài khoản Lãnh đạo `ld.hoa`.
  2. Vào tab **"Việc của tôi"**, chọn nhiệm vụ `Phân công thẩm định viên` của hồ sơ.
  3. Chọn cán bộ thẩm định phụ trách là **Hoàng Văn Bình** (`td.binh`) từ danh sách cán bộ đồng bộ theo đơn vị hành chính.
  4. Bấm **"Phân công"**.
- **Kết quả mong đợi trên màn hình:** Hồ sơ chuyển trạng thái `DUOC_PHAN_CONG`. Bản ghi phân công được lưu an toàn vào `core.assignments`.

---

### Bước 4: Tra cứu hồ sơ theo mã và Quy trình Truy cập khẩn cấp (Break-Glass)
- **Mục tiêu:** Chứng minh cơ chế kiểm soát truy cập cấp hàng (RLS), phát hiện truy cập trái quyền (403 có ghi vết), và quy trình Break-Glass có kiểm soát chặt chẽ với phê duyệt của lãnh đạo.
- **Thực hiện:**
  1. Đăng nhập tài khoản thẩm định viên **Vũ Quốc Cường** (`td.cuong`) - người **không** được phân công hồ sơ này.
  2. Tại tab **"Hồ sơ"**, danh sách hồ sơ của Cường hoàn toàn trống (theo cơ chế RLS).
  3. Tại nhóm **"Tra cứu hồ sơ theo mã (cán bộ)"**, quan sát dòng giải thích: *"Hồ sơ chưa được phân công sẽ cần yêu cầu truy cập khẩn có lý do, được lãnh đạo duyệt và ghi nhật ký"*.
  4. Nhập mã hồ sơ đã tạo ở bước 1 (ví dụ `CP-2026-xxxxxx`) vào ô nhập liệu có placeholder `CP-2026-xxxxxx`, bấm nút **"Mở hồ sơ"**.
  5. Hệ thống từ chối truy cập (HTTP 403), tự động ghi nhận nhật ký `access.denied` và hiện hộp thoại **"Bạn chưa có quyền mở hồ sơ này"**. Bấm **"Xin truy cập khẩn"**.
  6. Nhập lý do: *"Hỗ trợ đồng nghiệp thẩm định kết cấu đặc biệt ngoài giờ theo yêu cầu khẩn cấp"* và bấm **"Gửi yêu cầu"**.
  7. Đăng xuất `td.cuong`, đăng nhập tài khoản Lãnh đạo `ld.hoa`.
  8. Quan sát tab **"Việc của tôi"**: Tab có huy hiệu số đếm màu vàng cảnh báo yêu cầu khẩn cấp chờ duyệt.
  9. Trong bảng "Yêu cầu truy cập khẩn cấp đang chờ duyệt", thấy đầy đủ:
     - Mã hồ sơ: `CP-2026-xxxxxx`
     - Chủ đầu tư: `Trần Văn Minh`
     - Cán bộ yêu cầu: `Vũ Quốc Cường`
     - Lý do khẩn cấp: *"Hỗ trợ đồng nghiệp thẩm định kết cấu đặc biệt ngoài giờ theo yêu cầu khẩn cấp"*
  10. Bấm nút **"Duyệt"** (quyền truy cập có hiệu lực có thời hạn).
  11. Đăng xuất `ld.hoa`, đăng nhập lại `td.cuong`.
  12. Nhập lại mã hồ sơ `CP-2026-xxxxxx` vào ô "Tra cứu hồ sơ theo mã (cán bộ)" và bấm "Mở hồ sơ".
- **Kết quả mong đợi trên màn hình:** Hồ sơ được mở ra thành công với đầy đủ dữ liệu; toàn bộ quá trình xin - duyệt được ghi nhật ký WORM bất biến.

---

### Bước 5: Thẩm định kỹ thuật và Phân tách nhiệm vụ (SoD)
- **Mục tiêu:** Thẩm định viên đánh giá các chỉ tiêu xây dựng; kiểm tra nguyên tắc Phân tách nhiệm vụ (Separation of Duties - SoD).
- **Thực hiện:**
  1. Đăng nhập tài khoản thẩm định viên được phân công `td.binh`.
  2. Vào tab **"Việc của tôi"**, chọn nhiệm vụ `Thẩm định hồ sơ`.
  3. Nhập kết quả thẩm định: Chiều cao công trình hợp lệ, Mật độ xây dựng đạt chuẩn QCVN, Chỉ giới đường đỏ đảm bảo.
  4. Bấm **"Gửi kết quả thẩm định"**.
  5. Thử nghiệm SoD: Thẩm định viên `td.binh` không có quyền tự duyệt cấp giấy phép. Giao diện của Bình không có nút ký hay duyệt cấp phép.
- **Kết quả mong đợi trên màn hình:** Hồ sơ chuyển trạng thái `CHO_DUYET` / `CHO_KY`, chuyển sang hàng việc của Lãnh đạo UBND.

---

### Bước 6: Lãnh đạo Ký số PAdES/SoftHSM và Cấp Giấy phép Xây dựng
- **Mục tiêu:** Ký số tài liệu điện tử bằng khóa trong SoftHSM2/PKCS#11 (PAdES) và sinh giấy phép chính thức.
- **Thực hiện:**
  1. Đăng nhập tài khoản Lãnh đạo `ld.hoa`.
  2. Vào tab **"Việc của tôi"**, chọn nhiệm vụ `Phê duyệt cấp phép`.
  3. Bấm nút **"Phê duyệt và ký số"**.
  4. Hệ thống gọi `doc-sign` ký PAdES trên tài liệu PDF và cấp số giấy phép chính thức.
  5. Bấm "Chi tiết" hồ sơ để kiểm tra khối thông tin:
     - **Số giấy phép:** `GPXD-phuong-a-2026-xxxxxx`
     - **Người ký số:** `Phạm Thanh Hoa (Lãnh đạo UBND)`
     - **Thuật toán ký:** `PAdES (PKCS#11)` hoặc `Ed25519` nếu dùng OpenBao Transit
     - **Mã tra cứu công khai:** dạng `DOC-` theo sau 22 ký tự ngẫu nhiên
     - **Mã băm SHA-256 tài liệu:** chuỗi SHA-256 hoàn chỉnh
     - Nút **"Tải giấy phép (PDF)"**
     - Nút **"Mở trang tra cứu"**
- **Kết quả mong đợi trên màn hình:** Khối chữ ký số điện tử hiển thị đầy đủ thông tin xác thực; tải được tệp PDF giấy phép (chỉ khi đã đăng nhập và có quyền với hồ sơ).

---

### Bước 7: Xác minh Giấy phép Công khai (Không cần đăng nhập)
- **Mục tiêu:** Công dân và các bên liên quan kiểm tra tính hợp lệ và chữ ký số của giấy phép mà không cần tài khoản.
- **Thực hiện:**
  1. Mở cửa sổ ẩn danh (Incognito) hoặc trình duyệt mới hoàn toàn không đăng nhập.
  2. Truy cập đường dẫn công khai: `http://localhost:8080/kiem-tra/<ma_tra_cuu_cong_khai>` (hoặc bấm nút "Mở trang tra cứu" từ bước 6).
- **Kết quả mong đợi trên màn hình:** Trang xác minh công khai hiển thị trạng thái **"Hợp lệ"**, mã tra cứu, loại văn bản, đơn vị ban hành, ngày ký, thuật toán và phiên bản khóa, mã băm SHA-256. Trang **không** có họ tên, CCCD hay nút tải bản gốc: bản gốc chỉ tải được sau khi đăng nhập (bước 6).

---

### Bước 8: Quyền Chủ thể Dữ liệu (DSAR & Đồng thuận Consent)
- **Mục tiêu:** Thực thi các quyền của công dân theo Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.
- **Thực hiện:**
  1. Đăng nhập tài khoản công dân `cdt.minh`.
  2. Vào tab **"Dữ liệu cá nhân"**.
  3. Đồng thuận: bật hoặc tắt các mục (đối chiếu danh tính, nhận thông báo tiến độ, giám sát công trường bằng cảm biến), bấm **"Lưu lựa chọn"**.
  4. Nhập nội dung vào ô **"Nội dung yêu cầu"**, bấm một trong các nút:
     - **"Yêu cầu cung cấp dữ liệu"**
     - **"Rút đồng thuận"**
     - **"Yêu cầu xóa dữ liệu"**
  5. Yêu cầu vừa gửi hiện trong bảng bên dưới.
- **Kết quả mong đợi trên màn hình:** Bảng hiện dòng **"Cung cấp dữ liệu"**, trạng thái **"Đã tiếp nhận"**, kèm hạn xác nhận (2 ngày làm việc) và hạn giải quyết.

---

### Bước 9: Giám sát Cảm biến IoT & Phiếu Hậu kiểm Công trình
- **Mục tiêu:** Thể hiện sự hội tụ giữa dữ liệu quy trình IT và dữ liệu cảm biến thực địa OT (IoT/NGSI-LD).
- **Thực hiện:**
  1. Đăng nhập tài khoản Cán bộ Trật tự xây dựng `tt.khanh`.
  2. Vào tab **"Công trình và hậu kiểm"**:
     - Bảng hiển thị danh sách công trình đã được cấp phép (không lộ UUID kỹ thuật, có mã công trình `CT-phuong-a-2026-xxxxxx`).
  3. Kích hoạt cảm biến mô phỏng vượt ngưỡng tiếng ồn công trường từ terminal:
     - Trên PowerShell:
       ```powershell
       .\dx.ps1 demo-sensor CT-phuong-a-2026-000001 78.5
       ```
     - Trên Linux / Bash:
       ```bash
       ./dx.sh demo-sensor CT-phuong-a-2026-000001 78.5
       ```
  4. Quay lại giao diện web: Cột cảnh báo cảm biến hiển thị thẻ màu đỏ: **"Cảnh báo tiếng ồn: 78,5 dBA"**, dòng dưới ghi ngưỡng 70 dBA.
  5. Bấm nút **"Tạo phiếu kiểm tra"** trên dòng công trình đó.
  6. Vào tab **"Việc của tôi"**, chọn nhiệm vụ kiểm tra hiện trường:
     - Nhập kết luận kiểm tra: chọn *Đạt tiêu chuẩn* hoặc *Có vi phạm*.
     - Nhập ghi chú xử lý hiện trường: *"Đã lập biên bản nhắc nhở đơn vị thi công giảm tiếng ồn sau 22h"*.
     - Bấm **"Lưu kết quả kiểm tra"**.
- **Kết quả mong đợi trên màn hình:** Cảnh báo cảm biến hiển thị thời gian thực; phiếu kiểm tra hậu kiểm được tạo và hoàn tất lưu vết đầy đủ.

---

### Bước 10: Chủ đầu tư xem Nhật ký truy cập hồ sơ của mình
- **Mục tiêu:** Minh bạch hóa hoạt động công vụ đối với công dân: chủ đầu tư kiểm tra được ai đã xem hoặc can thiệp vào hồ sơ của mình, đặc biệt là các hành vi truy cập khẩn cấp.
- **Thực hiện:**
  1. Đăng nhập tài khoản chủ đầu tư `cdt.minh`.
  2. Tại tab **"Hồ sơ"**, bấm nút **"Xem"** trên hồ sơ đã nộp ở bước 1.
  3. Cuộn xuống khối **"Ai đã xem và xử lý hồ sơ"**.
  4. Quan sát các dòng lịch sử truy cập:
     - Dòng nổi bật màu đỏ viền đỏ: **"Truy cập khẩn"**, người thực hiện **Vũ Quốc Cường** kèm hộp thông tin màu vàng hiển thị: *"Lý do khẩn cấp: Hỗ trợ đồng nghiệp thẩm định kết cấu đặc biệt ngoài giờ theo yêu cầu khẩn cấp"*.
     - Dòng: **"Duyệt truy cập khẩn"**, người thực hiện **Phạm Thanh Hoa**.
     - Dòng: **"Cấp phép"** - Số giấy phép `GPXD-phuong-a-2026-xxxxxx`.
     - Dòng: **"Nộp hồ sơ"**.
  5. Thử nghiệm bảo mật RLS: `cdt.minh` hoàn toàn không xem được nhật ký hồ sơ của `cdt.lan` (bị từ chối 403).
- **Kết quả mong đợi trên màn hình:** Công dân thấy đầy đủ, rõ ràng các hành vi cán bộ đã thao tác trên hồ sơ của mình, có tên cán bộ và lý do can thiệp khẩn cấp.

---

### Bước 11: Thông báo đẩy Thời gian thực (SSE) & Chuông Thông báo
- **Mục tiêu:** Minh chứng tính tương tác tức thì qua Server-Sent Events (SSE) an toàn không dùng token trên URL và hệ thống lưu trữ thông báo bền bỉ theo vai trò.
- **Thực hiện:**
  1. Mở trình duyệt thứ nhất: Đăng nhập tài khoản Một cửa `mc.thu`. Quan sát biểu tượng **🔔 Chuông thông báo** ở góc phải thanh điều hướng.
  2. Mở trình duyệt thứ hai (hoặc cửa sổ ẩn danh): Đăng nhập tài khoản công dân `cdt.minh`.
  3. Tại trình duyệt thứ hai, `cdt.minh` bấm "Nộp hồ sơ mới" và nộp thành công một hồ sơ mới.
  4. Ngay lập tức tại trình duyệt thứ nhất của `mc.thu`: Trong vòng dưới 15 giây, chuông thông báo tự động nhảy huy hiệu số đếm đỏ (ví dụ `1 mới`).
  5. `mc.thu` bấm vào biểu tượng chuông: Danh sách thông báo mở ra, hiển thị dòng thông báo:
     - Tiêu đề: **"Hồ sơ mới CP-2026-xxxxxx"**
     - Nội dung: *"Hồ sơ cấp phép mới CP-2026-xxxxxx vừa được nộp bởi Trần Văn Minh, đang chờ một cửa tiếp nhận."*
     - Thời gian: *"Vừa xong"*
  6. Bấm vào dòng thông báo đó: Hệ thống tự động mở đúng hồ sơ / nhiệm vụ tiếp nhận.
  7. Bấm nút **"Đánh dấu đã đọc"**: Huy hiệu đỏ biến mất, các dòng thông báo chuyển sang trạng thái đã đọc.
  8. Kiểm tra tính bền vững: Đăng xuất rồi đăng nhập lại `mc.thu` -> Toàn bộ danh sách thông báo vẫn hiển thị đầy đủ (được lưu trữ bền vững trong cơ sở dữ liệu).
  9. Kiểm tra cách ly an toàn: Đăng nhập tài khoản `cdt.lan` -> Chuông thông báo của Lan không chứa thông báo hồ sơ của Minh hay nhiệm vụ của cán bộ một cửa.
- **Kết quả mong đợi trên màn hình:** Chuông thông báo phản hồi thời gian thực không cần tải lại trang; mở đúng việc khi bấm; lưu trữ bền bỉ và cô lập bảo mật tuyệt đối theo vai trò.

---

## 3. Tổng Kết Các Điểm Nổi Bật Kỹ Thuật Trong Bản Trình Diễn

1. **Kiến trúc Tầng 1 / Tầng 2 Chuẩn mực:** Lõi Platform hoàn toàn trung lập nghiệp vụ; toàn bộ biểu mẫu, quy trình BPMN, chính sách SoD, luật hậu kiểm thuộc về ứng dụng `cap-phep`.
2. **Bảo Mật Zero-Trust & Phân Quyền Cấp Hàng (RLS):** Bắt buộc cách ly đa đơn vị (multi-tenant) ở mọi câu lệnh SQL; từ chối truy cập có ghi vết kiểm toán.
3. **Quy Trình Truy Cập Khẩn Cấp (Break-Glass):** Có cơ chế tự khám phá trực quan trên giao diện, phê duyệt 2 mắt (Four-Eyes Principle) và đếm ngược thời gian tự động thu hồi.
4. **Ký Số Độc Lập An Toàn:** Chữ ký PAdES được ký bằng khóa trong SoftHSM2/PKCS#11, xác minh tính toàn vẹn và hợp lệ công khai mà không cần đăng nhập.
5. **Minh Bạch Hóa Với Công Dân:** Chủ đầu tư theo dõi được toàn bộ nhật ký cán bộ đã xem/xử lý hồ sơ và quản lý toàn diện quyền riêng tư dữ liệu cá nhân (DSAR).

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử V2-11: Toàn bộ giao diện màn hình P0 cho ứng dụng Cấp phép xây dựng (App.vue)
- Nộp hồ sơ + tải tệp (F-02, F-03)
- Chi tiết hồ sơ (F-05)
- Bổ sung hồ sơ (F-07)
- Bàn làm việc cán bộ 3 cột: danh sách việc, biểu mẫu xử lý, đồng hồ hạn & nhật ký kiểm toán (F-06, F-09)
- Xử lý 403 Forbidden & modal xin truy cập khẩn Break-Glass (F-11, V2-09)
- Màn hình Công trình & Hậu kiểm: danh sách công trình, lập phiếu kiểm tra (F-14)
- Chuông thông báo SSE thời gian thực (F-15)
- Dữ liệu của tôi: đồng thuận consents và yêu cầu DSAR (F-18, V2-10)
"""

from pathlib import Path


def test_v2_11_p0_screens_vue_components_exist():
    """Kiểm tra mã nguồn giao diện (App.vue, views/, components/) chứa đầy đủ các thành phần giao diện P0 bắt buộc."""
    src_dir = Path(__file__).resolve().parent.parent.parent / "apps" / "cap-phep" / "web" / "src"
    content = ""
    for f in src_dir.rglob("*.vue"):
        content += f.read_text(encoding="utf-8") + "\n"

    # 1. Nộp hồ sơ + tải tệp
    assert "showCreateModal" in content, "Thiếu modal nộp hồ sơ"
    assert "submitHoSo" in content, "Thiếu hàm nộp hồ sơ"
    assert "handleFileUpload" in content or "uploadFile" in content, "Thiếu hàm tải tệp"
    assert "Tải tệp đính kèm" in content or "Chọn tệp đính kèm" in content, "Thiếu giao diện tải tệp đính kèm"

    # 2. Chi tiết hồ sơ
    assert "detailHoSo" in content, "Thiếu state/modal chi tiết hồ sơ"
    assert "Chi tiết hồ sơ" in content, "Thiếu tiêu đề chi tiết hồ sơ"

    # 3. Bổ sung hồ sơ
    assert "supplementingHoSo" in content, "Thiếu modal/state bổ sung hồ sơ"
    assert "handleSupplementHoSo" in content or "supplementHoSo" in content, "Thiếu hàm bổ sung hồ sơ"
    assert "CAN_BO_SUNG" in content, "Thiếu kiểm tra trạng thái CẦN BỔ SUNG"

    # 4. Màn hình cán bộ 3 cột (việc / chi tiết / nhật ký + đồng hồ hạn)
    assert "col-span-3" in content or "grid-cols-12" in content, "Thiếu bố cục 3 cột cho cán bộ"
    assert "formatCountdown" in content or "countdown" in content.lower(), "Thiếu đồng hồ đếm ngược thời hạn"
    assert "Nhật ký kiểm toán" in content or "audit" in content.lower(), "Thiếu cột nhật ký kiểm toán"

    # 5. Thông báo 403 + Xin truy cập khẩn (Break-Glass)
    assert "showBreakGlassModal" in content, "Thiếu modal xin truy cập khẩn cấp"
    assert "403" in content, "Thiếu xử lý mã lỗi 403"
    assert "xin_truy_cap_khan" in content or "requestBreakGlass" in content, "Thiếu RPC xin truy cập khẩn cấp"
    assert "duyet_truy_cap_khan" in content or "approveBreakGlass" in content, "Thiếu RPC duyệt truy cập khẩn cấp"

    # 6. Công trình + Phiếu kiểm tra
    assert "activeTab === 'construction'" in content, "Thiếu tab công trình"
    assert "fetchCongTrinh" in content, "Thiếu hàm lấy danh sách công trình"
    assert "fetchPhieuKiemTra" in content, "Thiếu hàm lấy phiếu kiểm tra"

    # 7. Chuông thông báo SSE
    assert "EventSource" in content or "sse" in content.lower(), "Thiếu kết nối SSE"
    assert "notifications" in content, "Thiếu danh sách thông báo"
    assert "notifications.length" in content, "Thiếu badge đếm số lượng thông báo"

    # 8. "Dữ liệu của tôi" lưu thật qua API
    assert "activeTab === 'consent'" in content, "Thiếu tab dữ liệu của tôi"
    assert "saveConsents" in content, "Thiếu lưu đồng thuận dữ liệu"
    assert "submitDsar" in content, "Thiếu gửi yêu cầu DSAR"


def test_v2_11_web_api_contracts():
    """Kiểm tra các hợp đồng API trong api.ts kết nối đúng PostgREST endpoints."""
    api_ts = Path(__file__).resolve().parent.parent.parent / "apps" / "cap-phep" / "web" / "src" / "api.ts"
    assert api_ts.exists()
    content = api_ts.read_text(encoding="utf-8")

    assert "/rpc/nop_ho_so" in content
    assert "/rpc/bo_sung_ho_so" in content
    assert "/rpc/dinh_kem_tep" in content
    assert "/rpc/xin_truy_cap_khan" in content
    assert "/rpc/duyet_truy_cap_khan" in content
    assert "/cong_trinh" in content
    assert "/phieu_kiem_tra" in content
    assert "/consents" in content
    assert "/dsar_requests" in content

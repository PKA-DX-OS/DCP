# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V2-11: màn hình P0 của web cấp phép có đủ thành phần và gọi đúng API.

Kiểm tra tĩnh mã nguồn `apps/cap-phep/web/src` (không cần stack):
- Mỗi màn hình P0 có component riêng với phần tử giao diện chính.
- Lớp API gọi đúng endpoint PostgREST / flow / files / events.
- App.vue gắn các màn hình vào giao diện theo vai.
"""

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "apps" / "cap-phep" / "web" / "src"


def _doc(rel: str) -> str:
    p = SRC / rel
    assert p.exists(), f"Thiếu {rel}"
    return p.read_text(encoding="utf-8")


def _api() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((SRC / "api").glob("*.ts")))


# Màn hình P0 -> (file, các chuỗi bắt buộc trong file). Component chỉ hiển thị và
# phát sự kiện; lời gọi API nằm ở composables/useDossierActions.ts và api/*.ts.
MAN_HINH = {
    "nộp hồ sơ + tải tệp": ("components/CreateDossierModal.vue", ["form-nop-ho-so", "btn-submit-nop-ho-so", "DocumentChecklist"]),
    "checklist giấy tờ": ("components/DocumentChecklist.vue", ["document-checklist", "DUOI_CHO_PHEP"]),
    "chi tiết hồ sơ": ("components/DetailDossierModal.vue", ["Chi tiết hồ sơ", "fetchDossierFiles", "fetchDossierHistory"]),
    "bổ sung hồ sơ": ("components/SupplementModal.vue", ["form-bo-sung-ho-so", "han-bo-sung", "file-bo-sung"]),
    "hồ sơ của tôi": ("views/DossiersView.vue", ["CAN_BO_SUNG", "txt-tim-ho-so"]),
    "bàn làm việc cán bộ": ("views/WorkspaceView.vue", ["fetchTasks", "useDossierActions", "hoanThanhViec"]),
    "hành động hồ sơ": ("composables/useDossierActions.ts", ["nopHoSo", "supplementHoSo", "completeTask"]),
    "403": ("components/Forbidden403Modal.vue", ["403", "alertdialog"]),
    "truy cập khẩn": ("components/BreakGlassModal.vue", ["btn-confirm-break-glass", "chk-break-glass-ack"]),
    "công trình và hậu kiểm": ("views/ConstructionView.vue", ["fetchCongTrinh", "fetchPhieuKiemTra", "createInspection"]),
    "dữ liệu của tôi": ("views/ConsentView.vue", ["saveConsents", "btn-confirm-withdraw"]),
    "chuông thông báo SSE": ("composables/useNotifications.ts", ["EventSource", "/events/ticket"]),
}


@pytest.mark.parametrize("ten", sorted(MAN_HINH))
def test_v2_11_p0_screen_components(ten):
    rel, can_co = MAN_HINH[ten]
    noi_dung = _doc(rel)
    thieu = [x for x in can_co if x not in noi_dung]
    assert not thieu, f"{ten} ({rel}) thiếu: {thieu}"


def test_v2_11_web_api_contracts():
    api = _api()
    for ep in [
        "/rest/rpc/nop_ho_so", "/rest/rpc/bo_sung_ho_so", "/rest/rpc/dinh_kem_tep",
        "/rest/rpc/mo_ho_so", "/rest/rpc/xin_truy_cap_khan", "/rest/rpc/duyet_truy_cap_khan",
        "/rest/rpc/lap_phieu_kiem_tra", "/rest/rpc/thong_tin_giay_phep", "/rest/rpc/lay_nhat_ky_ho_so",
        "/rest/consents", "/rest/dsar_requests", "/rest/rpc/gui_yeu_cau_dsar",
        "/files", "/flow/tasks", "/flow/processes/start",
    ]:
        assert ep in api, f"Lớp API thiếu endpoint {ep}"
    # Công trình và phiếu kiểm tra đọc qua view/bảng tương ứng
    assert re.search(r"fetchCongTrinh[\s\S]*cong_trinh", api), "fetchCongTrinh phải đọc cong_trinh"
    assert re.search(r"fetchPhieuKiemTra[\s\S]*phieu_kiem_tra", api), "fetchPhieuKiemTra phải đọc phieu_kiem_tra"


def test_v2_11_app_mounts_staff_screens():
    app = _doc("App.vue")
    for comp in ("Navbar", "WorkspaceView", "ConstructionView"):
        assert f"<{comp}" in app, f"App.vue chưa gắn {comp}"


def test_v2_11_app_mounts_citizen_screens():
    app = _doc("App.vue")
    thieu = [c for c in ("DossiersView", "ConsentView", "CreateDossierModal", "DetailDossierModal",
                         "SupplementModal", "Forbidden403Modal", "BreakGlassModal") if f"<{c}" not in app]
    assert not thieu, f"App.vue chưa gắn: {thieu}"

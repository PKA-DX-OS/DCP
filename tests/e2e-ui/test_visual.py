# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-TEST-02: hồi quy hình ảnh các màn hình chính (Playwright + so ảnh bằng Pillow).

So ảnh chụp với ảnh nền trong tests/e2e-ui/baseline/<tên>.png.

**Ngưỡng:** một điểm ảnh coi là khác khi có kênh màu lệch quá 40/255. Màn hình đạt khi tỷ lệ điểm
khác **≤ 2 %** (NGUONG_TY_LE). Vùng thay đổi theo dữ liệu (mã hồ sơ, giờ, số đếm, biểu đồ) được che
trước khi chụp; hiệu ứng chuyển động tắt.

- Chưa có ảnh nền: test tạo ảnh nền, cảnh báo (không skip) để một lần chạy tạo đủ, ghi rõ để commit ảnh.
- Cập nhật ảnh nền có chủ đích: `UPDATE_BASELINE=1 pytest tests/e2e-ui/test_visual.py`.
- Ảnh chụp và ảnh khác biệt khi lỗi: E2E_OUT_DIR/visual (mặc định logs/e2e-ui/visual).

Ảnh nền chụp bằng Chromium 1366×900, nền tối; trình duyệt khác bỏ qua test này.
Cần stack đã `dx up` với DEMO_MODE=true và `python scripts/seed_hero.py`.
"""

import os
import re
import warnings
from pathlib import Path

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, ROOT

sync_api = pytest.importorskip("playwright.sync_api")
Image = pytest.importorskip("PIL.Image")
ImageChops = pytest.importorskip("PIL.ImageChops")
expect = sync_api.expect

BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")
BASELINE = Path(__file__).parent / "baseline"
OUT = Path(os.getenv("E2E_OUT_DIR") or ROOT / "logs" / "e2e-ui") / "visual"
NGUONG_KENH = 40
NGUONG_TY_LE = 0.02
CHO = 20000
VIEWPORT = {"width": 1366, "height": 900}


def _mat_khau(user: str) -> str:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.skip("Thiếu secrets/demo-accounts.txt")
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 2 and parts[0] == user:
            return parts[1]
    pytest.skip(f"Thiếu tài khoản demo {user}")


def _dang_nhap(page, user: str, url: str = "/") -> None:
    dich = f"{BASE_URL}{url}"
    page.goto(dich, wait_until="domcontentloaded")
    page.get_by_role("button", name="Đăng nhập", exact=True).click()
    page.locator("#username").fill(user)
    page.locator("#password").fill(_mat_khau(user))
    page.locator("#kc-login").click()
    page.wait_for_url(re.compile(re.escape(dich) + r"(\?.*)?$"), timeout=CHO)


def ty_le_khac(a, b) -> float:
    """Tỷ lệ điểm ảnh có ít nhất một kênh lệch quá NGUONG_KENH; khác kích thước coi như khác hết."""
    if a.size != b.size:
        return 1.0
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    # Mỗi kênh: 255 nếu lệch quá ngưỡng; gộp sang L thì điểm nào có kênh lệch sẽ khác 0
    mask = diff.point(lambda v: 255 if v > NGUONG_KENH else 0).convert("L")
    so_khac = a.size[0] * a.size[1] - mask.histogram()[0]
    return so_khac / (a.size[0] * a.size[1])


def so_voi_nen(page, ten: str, che: list, vung=None) -> None:
    """Chụp khung nhìn rồi so với ảnh nền. Có `vung` thì cuộn vùng đó lên đầu khung cuộn trước khi chụp,
    để phần phía trên (đổi theo dữ liệu) không làm lệch ảnh.

    Chưa có ảnh nền thì tạo và cảnh báo, không dừng test, để một lần chạy tạo đủ ảnh nền của mọi màn.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_load_state("networkidle")
    if vung is not None:
        vung.evaluate("(e) => e.scrollIntoView({block: 'start', behavior: 'instant'})")
    # Chờ khung tải biến mất và bố cục đứng yên để vùng che khớp vị trí khi chụp
    page.wait_for_function("() => !document.querySelector('[aria-busy=\"true\"]')", timeout=CHO)
    page.wait_for_timeout(300)
    anh = OUT / f"{ten}.png"
    page.screenshot(path=str(anh), animations="disabled", caret="hide", mask=che, mask_color="#7f7f7f")
    nen = BASELINE / f"{ten}.png"
    if os.getenv("UPDATE_BASELINE") == "1" or not nen.exists():
        BASELINE.mkdir(parents=True, exist_ok=True)
        nen.write_bytes(anh.read_bytes())
        warnings.warn(f"Đã tạo ảnh nền {nen.relative_to(ROOT)}; kiểm bằng mắt rồi commit ảnh này")
        return
    with Image.open(nen) as a, Image.open(anh) as b:
        tl = ty_le_khac(a, b)
        if tl > NGUONG_TY_LE:
            ImageChops.difference(a.convert("RGB"), b.convert("RGB")).save(OUT / f"{ten}-khac.png")
    assert tl <= NGUONG_TY_LE, f"{ten}: {tl:.2%} điểm ảnh khác ảnh nền (ngưỡng {NGUONG_TY_LE:.0%}); xem {OUT}"


@pytest.fixture()
def page(trinh_duyet, request):
    if trinh_duyet.browser_type.name != "chromium":
        pytest.skip("Ảnh nền chụp bằng Chromium")
    ctx = trinh_duyet.new_context(viewport=VIEWPORT, locale="vi-VN", color_scheme="dark", reduced_motion="reduce")
    # Cố định chế độ tối để ảnh không đổi theo cài đặt máy
    ctx.add_init_script("try{localStorage.setItem('dxos-giao-dien','dark');localStorage.setItem('dxos-bdh-theme','toi')}catch(e){}")
    p = ctx.new_page()
    yield p
    ctx.close()


def test_dang_nhap(page):
    page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
    expect(page.get_by_role("button", name="Đăng nhập", exact=True)).to_be_visible(timeout=CHO)
    so_voi_nen(page, "trang-chao", [page.locator("footer")])
    page.get_by_role("button", name="Đăng nhập", exact=True).click()
    page.locator("#username").wait_for(timeout=CHO)
    so_voi_nen(page, "dang-nhap-keycloak", [])


def test_dashboard(page):
    _dang_nhap(page, "ld.hoa", "/dieu-hanh/")
    expect(page.get_by_text("Hồ sơ theo trạng thái")).to_be_visible(timeout=CHO)
    # Số liệu, biểu đồ và danh sách đổi theo dữ liệu: che, chỉ so bố cục và khung
    che = [page.locator("svg"), page.locator("main ul"), page.locator("main table"), page.locator(".text-2xl"),
           page.locator("input[type='month']"), page.get_by_text(re.compile("^Thời điểm tính"))]
    so_voi_nen(page, "dashboard", che)


def test_ban_lam_viec_va_chi_tiet_ho_so(page):
    _dang_nhap(page, "mc.thu")
    page.locator("nav[aria-label='Điều hướng']").get_by_role("button", name="Bàn làm việc", exact=True).click()
    page.locator("aside button").first.wait_for(timeout=CHO)
    so_voi_nen(
        page,
        "ban-lam-viec",
        [
            page.locator("aside button"),
            page.locator("section dd"),
            page.locator("section li"),
            page.locator("header [aria-label^='Thông báo']"),
        ],
    )
    page.get_by_role("button", name="Mở hồ sơ đầy đủ").first.click()
    dlg = page.locator("[role='dialog']").first
    expect(dlg).to_be_visible(timeout=CHO)
    che = [dlg.locator("dd"), dlg.locator("li"), dlg.locator("td"), dlg.locator("h3"), dlg.locator("svg")]
    so_voi_nen(page, "chi-tiet-ho-so", che)
    # Nhật ký xem hồ sơ dài thêm sau mỗi lần chạy nên chỉ chụp đúng phần cần so
    so_voi_nen(page, "quy-hoach", che + [page.locator(".leaflet-container")], page.locator("#block-dossier-planning"))
    so_voi_nen(page, "nghiem-thu", che, page.locator("#block-dossier-acceptance"))


def test_tra_cuu(page):
    page.goto(f"{BASE_URL}/kiem-tra/", wait_until="domcontentloaded")
    page.locator("input[name='ma']").wait_for(timeout=CHO)
    so_voi_nen(page, "tra-cuu", [])


def test_tham_dinh_thiet_ke(page):
    _dang_nhap(page, "cdt.minh")
    page.locator("#txt-tim-ho-so").fill("CP-HERO-2026-001")
    hang = page.get_by_text("CP-HERO-2026-001").first
    expect(hang).to_be_visible(timeout=CHO)
    page.locator("tr, li").filter(has_text="CP-HERO-2026-001").first.get_by_role("button").first.click()
    dlg = page.locator("[role='dialog']").first
    expect(dlg).to_be_visible(timeout=CHO)
    muc = page.locator("#muc-thiet-ke")
    muc.scroll_into_view_if_needed()
    expect(muc).to_be_visible(timeout=CHO)
    # Chỉ chụp phần thẩm định thiết kế: nhật ký phía trên dài thêm sau mỗi lần mở hồ sơ
    so_voi_nen(page, "tham-dinh-thiet-ke", [muc.locator("time"), muc.locator("td")], muc)

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-TEST-02: hồi quy hình ảnh các màn chính.

Ngưỡng: sai khác <= 3% số điểm ảnh (kênh màu lệch > 16/255) thì đạt.
Màn có dữ liệu động (bảng điều hành, thiết kế) được che các vùng số liệu/ngày giờ
trước khi so sánh; 3% dành cho phần nội dung động còn lại.
Tạo/ cập nhật baseline:
    $env:E2E_UPDATE_BASELINE="1"; pytest tests/e2e-ui/test_visual.py -q
"""

import io
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, ROOT, get_token
from tests.integration._ho_so import normalize_payload, start_cap_phep, submit_dossier

sync_api = pytest.importorskip("playwright.sync_api")
Image = pytest.importorskip("PIL.Image")
ImageChops = pytest.importorskip("PIL.ImageChops")
BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")
BASELINE = Path(__file__).parent / "baseline"
NGUONG_SAI_KHAC = 0.03
CAP_NHAT = os.getenv("E2E_UPDATE_BASELINE", "") == "1"
TAO_MOI: list[str] = []


def _mat_khau() -> dict[str, str]:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.skip("Thiếu secrets/demo-accounts.txt")
    ds = {}
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 2 and parts[0] and not parts[0].startswith("#"):
            ds[parts[0]] = parts[1]
    return ds


def _dang_nhap(page, username: str, password: str, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded")
    page.get_by_role("button", name="Đăng nhập", exact=True).click()
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#kc-login").click()
    page.wait_for_url(re.compile(re.escape(url) + r"(\?.*)?$"), timeout=20000)


def _chup(locator, ten: str, mask: list | None = None) -> None:
    locator.wait_for(state="visible", timeout=20000)
    png = locator.screenshot(animations="disabled", mask=mask or [])
    path = BASELINE / f"{ten}.png"
    if CAP_NHAT or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
        TAO_MOI.append(ten)
        return

    a = Image.open(io.BytesIO(path.read_bytes())).convert("RGB")
    b = Image.open(io.BytesIO(png)).convert("RGB")
    assert a.size == b.size, f"{ten}: kích thước ảnh đổi {a.size} -> {b.size}"
    diff = ImageChops.difference(a, b)
    r, g, bl = diff.split()
    lon_nhat = ImageChops.lighter(ImageChops.lighter(r, g), bl)
    diem = lon_nhat.point(lambda p: 255 if p > 16 else 0)
    so_diem_khac = diem.histogram()[255]
    ty_le = so_diem_khac / (a.size[0] * a.size[1])
    assert ty_le <= NGUONG_SAI_KHAC, (
        f"{ten}: {ty_le:.2%} điểm ảnh lệch, vượt ngưỡng {NGUONG_SAI_KHAC:.0%}. "
        f"Xem ảnh mới tại {path}"
    )


def test_BTEST02_hoi_quy_hinh_anh_cac_man_chinh():
    accounts = _mat_khau()
    if "cdt.minh" not in accounts or "mc.thu" not in accounts:
        pytest.skip("Thiếu tài khoản demo")
    subprocess.run([sys.executable, "scripts/seed_hero.py"], cwd=ROOT, check=True)

    # Tạo một việc thật cho Một cửa để tab quy hoạch/nghiệm thu có dữ liệu.
    payload = {
        "ho_ten": "Nguyễn Văn Ảnh",
        "cccd": "001099008888",
        "dien_thoai": "0908888888",
        "dia_chi_cong_trinh": "Số 88 Đường Ảnh, phường A",
        "thua_dat": "TD-A-01",
        "so_tang": 3,
        "dien_tich_san_m2": 120.0,
        "khu_quan_ly_kien_truc": True,
    }
    cdt = get_token("cdt.minh")
    resp = submit_dossier(cdt, payload, tag_prefix="VIS")
    assert resp.status_code == 200, resp.text
    ho_so = resp.json()
    ma_ho_so_vis = ho_so["ma_ho_so"]
    data = normalize_payload(payload)
    start_cap_phep(
        cdt,
        ho_so,
        {
            "dien_tich_san_m2": data["dien_tich_san_m2"],
            "khu_quan_ly_kien_truc": bool(data.get("khu_quan_ly_kien_truc")),
            "dia_chi_cong_trinh": payload["dia_chi_cong_trinh"],
        },
    )

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")

        # 1. Trang chào và đăng nhập hai ứng dụng
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 900},
            locale="vi-VN",
            device_scale_factor=1,
            color_scheme="light",
            reduced_motion="reduce",
        )
        page = ctx.new_page()
        try:
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            _chup(page.locator("#main"), "login-cap-phep")
            page.goto(f"{BASE_URL}/dieu-hanh/", wait_until="domcontentloaded")
            _chup(page.locator("main.brand-hero"), "login-dieu-hanh")
            page.goto(f"{BASE_URL}/kiem-tra/", wait_until="domcontentloaded")
            _chup(
                page.locator("main .the"),
                "public-lookup",
                mask=[page.locator("main code")],
            )
        finally:
            ctx.close()

        # 2. Bảng điều hành
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 900},
            locale="vi-VN",
            device_scale_factor=1,
            color_scheme="light",
            reduced_motion="reduce",
        )
        page = ctx.new_page()
        try:
            _dang_nhap(page, "ld.hoa", accounts["ld.hoa"], f"{BASE_URL}/dieu-hanh/")
            page.get_by_role("heading", name="Bảng điều hành lãnh đạo").wait_for(timeout=20000)
            page.get_by_text("Đang tải chỉ số…").wait_for(state="detached", timeout=30000)
            _chup(
                page.locator("main#bdh-main"),
                "dashboard",
                mask=[
                    page.locator("main#bdh-main .text-2xl"),
                    page.locator("main#bdh-main .text-xs"),
                    page.locator("main#bdh-main table"),
                ],
            )
        finally:
            ctx.close()

        # 3. Bàn làm việc
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 900},
            locale="vi-VN",
            device_scale_factor=1,
            color_scheme="light",
            reduced_motion="reduce",
        )
        page = ctx.new_page()
        try:
            _dang_nhap(page, "mc.thu", accounts["mc.thu"], f"{BASE_URL}/")
            page.get_by_role("button", name="Bàn làm việc", exact=True).click()
            page.get_by_role("heading", name="Bàn làm việc").wait_for(timeout=20000)
            _chup(page.locator("main .flex.flex-wrap.items-end.gap-3").first, "workspace")
        finally:
            ctx.close()

        # 4. Chi tiết hồ sơ, thiết kế, quy hoạch, nghiệm thu
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 900},
            locale="vi-VN",
            device_scale_factor=1,
            color_scheme="light",
            reduced_motion="reduce",
        )
        page = ctx.new_page()
        try:
            _dang_nhap(page, "cdt.minh", accounts["cdt.minh"], f"{BASE_URL}/")
            page.get_by_role("button", name="Hồ sơ của tôi", exact=True).click()
            page.locator("#btn-detail-CP-HERO-2026-001").wait_for(timeout=20000)
            page.locator("#btn-detail-CP-HERO-2026-001").click()
            page.locator("#modal-detail-dossier").wait_for(timeout=20000)
            page.wait_for_function(
                "() => !document.querySelector('#modal-detail-dossier')?.innerText.includes('Đang tải')",
                timeout=20000,
            )
            _chup(
                page.locator("#modal-detail-dossier .hop"),
                "dossier-detail",
                mask=[
                    page.locator("#modal-detail-dossier dd"),
                    page.locator("#modal-detail-dossier .tt"),
                    page.locator("#block-dossier-files"),
                    page.locator("#block-dossier-progress time"),
                    page.locator("#block-giay-phep-signature"),
                    page.locator("#block-dossier-audit"),
                ],
            )

            page.get_by_role("button", name="Thiết kế", exact=True).click()
            page.locator("#block-design-review").wait_for(timeout=20000)
            page.locator("#design-review-summary").wait_for(timeout=20000)
            _chup(page.locator("#block-design-review"), "design-review")
        finally:
            ctx.close()

        # 5. Quy hoạch và nghiệm thu trên hồ sơ do Một cửa xử lý
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 900},
            locale="vi-VN",
            device_scale_factor=1,
            color_scheme="light",
            reduced_motion="reduce",
        )
        page = ctx.new_page()
        try:
            _dang_nhap(page, "mc.thu", accounts["mc.thu"], f"{BASE_URL}/")
            page.get_by_role("button", name="Bàn làm việc", exact=True).click()
            viec = page.locator("li", has_text=ma_ho_so_vis).first
            viec.wait_for(timeout=20000)
            viec.get_by_role("button", name="Xem hồ sơ").click()
            page.locator("#modal-detail-dossier").wait_for(timeout=20000)
            page.wait_for_function(
                "() => !document.querySelector('#modal-detail-dossier')?.innerText.includes('Đang tải')",
                timeout=20000,
            )

            page.locator("#tab-chi-tiet-block-dossier-planning").click()
            page.get_by_role("heading", name="Quy hoạch và chỉ tiêu xây dựng").wait_for(timeout=20000)
            page.locator("#block-dossier-planning").wait_for(timeout=20000)
            page.locator(".leaflet-container").first.wait_for(timeout=20000)
            _chup(page.locator("#block-dossier-planning"), "planning")

            page.locator("#tab-chi-tiet-block-dossier-acceptance").click()
            page.get_by_role("heading", name="Nghiệm thu và hoàn công").wait_for(timeout=20000)
            page.locator("#block-dossier-acceptance").wait_for(timeout=20000)
            _chup(page.locator("#block-dossier-acceptance"), "acceptance")
        finally:
            ctx.close()
            browser.close()

    if TAO_MOI:
        pytest.skip(f"Đã tạo baseline: {', '.join(TAO_MOI)}. Chạy lại để so sánh.")

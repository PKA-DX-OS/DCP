# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-DS-05: kiểm axe-core mức serious/critical trên các màn chính."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, ROOT

sync_api = pytest.importorskip("playwright.sync_api")
BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")
AXE = ROOT / "apps" / "cap-phep" / "web" / "node_modules" / "axe-core" / "axe.min.js"


def _tai_khoan() -> dict[str, str]:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.skip("Thiếu secrets/demo-accounts.txt")
    ds = {}
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        p = line.strip().split(":")
        if len(p) >= 2 and p[0] and not p[0].startswith("#"):
            ds[p[0]] = p[1]
    return ds


def _axe(page) -> list[dict]:
    page.add_script_tag(path=str(AXE))
    # Kết thúc transition màu trước khi đo tương phản (theme đổi trong 500ms).
    page.evaluate("() => document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} })")
    res = page.evaluate("async () => await axe.run(document, {resultTypes:['violations']})")
    return [v for v in res["violations"] if v["impact"] in ("serious", "critical")]


def _dang_nhap(page, username: str, password: str, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded")
    page.get_by_role("button", name="Đăng nhập", exact=True).click()
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#kc-login").click()
    page.wait_for_url(re.compile(re.escape(url) + r"(\?.*)?$"), timeout=20000)
    # URL khớp ngay khi Keycloak chuyển về (?code=...), trước khi ứng dụng đổi mã lấy token
    page.get_by_role("button", name="Đăng xuất").wait_for(timeout=20000)


def _cho(page, selector: str, ten: str) -> None:
    """Chờ phần tử; nếu không thấy thì lưu ảnh và chữ trên trang vào E2E_OUT_DIR để biết vì sao."""
    try:
        page.locator(selector).wait_for(timeout=20000)
    except Exception:
        thu_muc = Path(os.getenv("E2E_OUT_DIR", ROOT / "tests" / "e2e-ui" / "_out")) / "a11y"
        thu_muc.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(thu_muc / f"{ten}.png"), full_page=True)
        (thu_muc / f"{ten}.txt").write_text(f"URL: {page.url}\n\n{page.inner_text('body')}", encoding="utf-8")
        raise


def test_a11y_login_danh_sach_dashboard():
    accounts = _tai_khoan()
    if "cdt.minh" not in accounts or "ld.hoa" not in accounts:
        pytest.skip("Thiếu tài khoản demo")
    subprocess.run([sys.executable, "scripts/seed_hero.py"], cwd=ROOT, check=True)

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN", bypass_csp=True)
        page = ctx.new_page()
        try:
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            assert _axe(page) == []
            page.get_by_role("button", name=re.compile("nền", re.I)).click()
            page.wait_for_timeout(250)
            assert _axe(page) == []
            page.get_by_role("button", name=re.compile("nền", re.I)).click()

            _dang_nhap(page, "cdt.minh", accounts["cdt.minh"], f"{BASE_URL}/")
            page.locator("nav[aria-label='Điều hướng']").get_by_role("button", name="Hồ sơ của tôi", exact=True).click()
            _cho(page, "#table-ho-so", "danh-sach-ho-so")
            assert _axe(page) == []

            page.locator("#btn-detail-CP-HERO-2026-001").wait_for(timeout=20000)
            page.locator("#btn-detail-CP-HERO-2026-001").click()
            page.locator("#modal-detail-dossier").wait_for(timeout=20000)
            page.get_by_role("button", name="Thiết kế", exact=True).click()
            page.locator("#design-review-summary").wait_for(timeout=20000)
            assert _axe(page) == []
        finally:
            ctx.close()

        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN", bypass_csp=True)
        page = ctx.new_page()
        try:
            _dang_nhap(page, "ld.hoa", accounts["ld.hoa"], f"{BASE_URL}/dieu-hanh/")
            page.get_by_role("heading", name="Chỉ số điều hành").wait_for(timeout=20000)
            assert _axe(page) == []
            page.get_by_role("button", name=re.compile("Nền (sáng|tối)")).click()
            page.wait_for_timeout(250)
            assert _axe(page) == []
        finally:
            ctx.close()

        if "kt.an" in accounts:
            ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN", bypass_csp=True)
            page = ctx.new_page()
            try:
                _dang_nhap(page, "kt.an", accounts["kt.an"], f"{BASE_URL}/dieu-hanh/")
                page.get_by_role("button", name="Kiểm toán", exact=True).click()
                page.get_by_text("Nhật ký kiểm toán").wait_for(timeout=20000)
                assert _axe(page) == []
            finally:
                ctx.close()

        if "admin" in accounts:
            ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN", bypass_csp=True)
            page = ctx.new_page()
            try:
                _dang_nhap(page, "admin", accounts["admin"], f"{BASE_URL}/dieu-hanh/")
                page.get_by_role("button", name="Quản trị", exact=True).click()
                page.get_by_role("heading", name="Quản trị địa bàn").wait_for(timeout=20000)
                assert _axe(page) == []
            finally:
                ctx.close()
        browser.close()


def test_a11y_link_panel_can_bo():
    """H-LINK: tab Liên ngành chỉ dành cho cán bộ; kiểm axe sau khi mở panel."""
    accounts = _tai_khoan()
    if "mc.thu" not in accounts:
        pytest.skip("Thiếu tài khoản demo mc.thu")
    subprocess.run([sys.executable, "scripts/seed_hero.py"], cwd=ROOT, check=True)

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN", bypass_csp=True)
        page = ctx.new_page()
        try:
            _dang_nhap(page, "mc.thu", accounts["mc.thu"], f"{BASE_URL}/")
            page.keyboard.press("Control+K")
            o = page.get_by_label("Từ khóa tìm kiếm toàn cục")
            o.fill("CP-HERO-2026-001")
            page.get_by_role("button").filter(has_text="CP-HERO-2026-001").first.click()
            page.locator("#btn-close-modal-detail").wait_for(timeout=20000)
            page.get_by_role("button", name="Liên ngành", exact=True).click()
            page.locator("#block-dossier-link").wait_for(timeout=20000)
            assert _axe(page) == []
        finally:
            ctx.close()
            browser.close()

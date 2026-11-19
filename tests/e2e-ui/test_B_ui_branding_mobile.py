# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-UX-06/07/08/09/10 và B-DS-03/04/05: branding, responsive, dark mode, accessibility."""

import os
import re
import subprocess
import sys

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, ROOT

sync_api = pytest.importorskip("playwright.sync_api")
BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")


def _mat_khau() -> dict[str, str]:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.skip("Thiếu secrets/demo-accounts.txt")
    ds = {}
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 2 and parts[0] and not parts[0].startswith("#"):
            ds[parts[0]] = parts[1]
    return ds


def test_BU06_branding_dark_mode_va_danh_sach_di_dong():
    accounts = _mat_khau()
    if "cdt.minh" not in accounts:
        pytest.skip("Thiếu tài khoản demo cdt.minh")
    subprocess.run([sys.executable, "scripts/seed_hero.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "scripts/seed_demo_history.py"], cwd=ROOT, check=True)

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="vi-VN")
        page = ctx.new_page()
        try:
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            page.get_by_text("DX-OS Open-Core").first.wait_for(timeout=20000)
            page.get_by_text("Nền tảng cấp phép xây dựng số, bảo mật và minh bạch.").wait_for(timeout=20000)
            page.get_by_role("button", name=re.compile("Dành cho công dân")).wait_for(timeout=20000)
            page.get_by_role("button", name=re.compile("Dành cho cán bộ")).wait_for(timeout=20000)
            assert page.locator('a[href="#main"]').count() >= 1

            truoc = page.evaluate("document.documentElement.dataset.theme")
            page.get_by_role("button", name=re.compile("nền (sáng|tối)", re.I)).click()
            sau = page.evaluate("document.documentElement.dataset.theme")
            assert truoc != sau

            page.get_by_role("button", name="Đăng nhập", exact=True).click()
            page.locator("#username").fill("cdt.minh")
            page.locator("#password").fill(accounts["cdt.minh"])
            page.locator("#kc-login").click()
            page.wait_for_url(re.compile(re.escape(BASE_URL) + r"/(\?.*)?$"), timeout=20000)
            page.get_by_role("button", name="Hồ sơ của tôi", exact=True).click()
            page.get_by_role("button", name="Nộp hồ sơ mới", exact=True).click()
            page.get_by_text("Bước 1/3").wait_for(timeout=20000)
            page.get_by_role("button", name="Tiếp tục", exact=True).click()
            page.get_by_text("Bước 2/3").wait_for(timeout=20000)
            page.get_by_role("button", name="Tiếp tục", exact=True).click()
            page.get_by_text("Bước 3/3").wait_for(timeout=20000)
            page.locator(".hop .nut-dong").first.click()

            page.locator("#btn-detail-mobile-CP-HERO-2026-001").wait_for(timeout=20000)
            page.locator("#btn-detail-mobile-CP-HERO-2026-001").click()
            page.locator("#modal-detail-dossier").wait_for(timeout=20000)
            page.get_by_role("button", name="Giấy tờ", exact=True).click()
            page.locator("#block-dossier-files").wait_for(timeout=20000)
            assert page.locator("#block-dossier-audit").is_hidden()
            page.get_by_role("button", name="Thiết kế", exact=True).click()
            page.locator("#block-design-review").wait_for(timeout=20000)
        finally:
            ctx.close()
            browser.close()

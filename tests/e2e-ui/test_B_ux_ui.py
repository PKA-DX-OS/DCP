# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-UX-01/04/05/06: dashboard, thông báo, kiểm toán trên UI thật."""

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


def _dang_nhap(page, username: str, password: str, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded")
    page.get_by_role("button", name="Đăng nhập", exact=True).click()
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#kc-login").click()
    page.wait_for_url(re.compile(re.escape(url) + r"(\?.*)?$"), timeout=20000)


def test_BU01_dashboard_lanh_dao_co_kpi_chart_va_danh_sach():
    accounts = _mat_khau()
    if "ld.hoa" not in accounts:
        pytest.skip("Thiếu tài khoản demo ld.hoa")
    subprocess.run([sys.executable, "scripts/seed_hero.py"], cwd=ROOT, check=True)

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            _dang_nhap(page, "ld.hoa", accounts["ld.hoa"], f"{BASE_URL}/dieu-hanh/")
            page.get_by_text("Bảng điều hành lãnh đạo").wait_for(timeout=20000)
            page.get_by_text("Hồ sơ theo trạng thái").wait_for(timeout=20000)
            page.get_by_text("Hồ sơ theo tháng (6 tháng)").wait_for(timeout=20000)
            page.get_by_text("Tải việc theo cán bộ").wait_for(timeout=20000)
            page.get_by_text("Hồ sơ quá hạn").first.wait_for(timeout=20000)
            page.get_by_text("Việc cần xử lý hôm nay").wait_for(timeout=20000)
            assert page.get_by_text("Hồ sơ mới trong kỳ").count() >= 1
            assert page.get_by_role("button", name="Xuất Excel").count() >= 1
            assert page.get_by_role("button", name="Xuất PDF").count() >= 1
        finally:
            ctx.close()
            browser.close()


def test_BU05_auditor_ui_va_BU04_thong_bao():
    accounts = _mat_khau()
    if "kt.an" not in accounts:
        pytest.skip("Thiếu tài khoản demo kt.an")

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            _dang_nhap(page, "kt.an", accounts["kt.an"], f"{BASE_URL}/dieu-hanh/")
            page.get_by_role("button", name="Kiểm toán", exact=True).click()
            page.get_by_text("Nhật ký kiểm toán").wait_for(timeout=20000)
            page.get_by_text(re.compile("Chuỗi (hợp lệ|không hợp lệ)")).wait_for(timeout=20000)
        finally:
            ctx.close()
            browser.close()

    if "cdt.minh" not in accounts:
        pytest.skip("Thiếu tài khoản demo cdt.minh")
    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            _dang_nhap(page, "cdt.minh", accounts["cdt.minh"], f"{BASE_URL}/")
            page.get_by_role("button", name=re.compile("Thông báo")).click()
            page.get_by_text("Có nhận xét thẩm định mới").wait_for(timeout=20000)
            page.get_by_role("button", name="Đánh dấu tất cả đã đọc").click()
        finally:
            ctx.close()
            browser.close()

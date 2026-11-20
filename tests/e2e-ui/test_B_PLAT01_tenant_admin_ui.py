# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-PLAT-01: giao diện quản trị địa bàn cho quản trị nền tảng."""

import os
import re
import uuid

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL
from tests.integration._ho_so import run_sql

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


def test_BPLAT01_quan_tri_dia_ban_tao_va_xem_nguoi_dung():
    accounts = _mat_khau()
    if "admin" not in accounts:
        pytest.skip("Thiếu tài khoản demo admin")

    ma_moi = f"qa-ui-{uuid.uuid4().hex[:6]}"
    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            _dang_nhap(page, "admin", accounts["admin"], f"{BASE_URL}/dieu-hanh/")
            page.get_by_role("heading", name="Chỉ số điều hành").wait_for(timeout=20000)
            page.get_by_role("button", name="Quản trị", exact=True).click()
            page.get_by_role("heading", name="Quản trị địa bàn").wait_for(timeout=20000)
            page.get_by_text("phuong-a").first.wait_for(timeout=20000)
            page.get_by_text("Tạo địa bàn mới").wait_for(timeout=20000)

            page.get_by_role("button", name=re.compile("Phường A")).click()
            page.get_by_text("Nguyễn Thị Thu").wait_for(timeout=20000)
            page.get_by_text("Minh họa cách ly dữ liệu").wait_for(timeout=20000)
            page.get_by_text("RLS", exact=True).wait_for(timeout=20000)

            page.locator("#tenant-ma").fill(ma_moi)
            page.locator("#tenant-ten").fill("QA UI Tạm")
            page.locator("#tenant-dvhc").fill("799998")
            page.get_by_role("button", name="Tạo địa bàn", exact=True).click()
            page.get_by_text(f"Đã tạo địa bàn QA UI Tạm ({ma_moi})").wait_for(timeout=20000)
        finally:
            ctx.close()
            browser.close()
            run_sql(f"DELETE FROM core.tenants WHERE tenant = '{ma_moi}';")


def test_BPLAT01_lanh_dao_khong_thay_tab_quan_tri():
    accounts = _mat_khau()
    if "ld.hoa" not in accounts:
        pytest.skip("Thiếu tài khoản demo ld.hoa")

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            _dang_nhap(page, "ld.hoa", accounts["ld.hoa"], f"{BASE_URL}/dieu-hanh/")
            page.get_by_role("heading", name="Chỉ số điều hành").wait_for(timeout=20000)
            assert page.get_by_role("button", name="Quản trị", exact=True).count() == 0
        finally:
            ctx.close()
            browser.close()

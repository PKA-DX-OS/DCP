# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-TEST-02: mỗi vai đi được luồng chính trên giao diện thật."""

import os
import re

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL

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


def _vao_tab(page, ten: str) -> None:
    page.get_by_role("button", name=ten, exact=True).click()


@pytest.mark.parametrize(
    "username,tab,kiem_tra",
    [
        ("cdt.minh", "Hồ sơ của tôi", "#table-ho-so"),
        ("mc.thu", "Bàn làm việc", "h2:has-text('Bàn làm việc')"),
        ("td.binh", "Bàn làm việc", "h2:has-text('Bàn làm việc')"),
        ("tt.khanh", "Bàn làm việc", "h2:has-text('Bàn làm việc')"),
        ("ld.hoa", "Bàn làm việc", "h2:has-text('Bàn làm việc')"),
        ("ld.hoa", "Truy cập khẩn", "text=Truy cập khẩn"),
    ],
)
def test_BTEST02_vai_di_duoc_luong_chinh_cap_phep(username: str, tab: str, kiem_tra: str):
    accounts = _mat_khau()
    if username not in accounts:
        pytest.skip(f"Thiếu tài khoản demo {username}")

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            _dang_nhap(page, username, accounts[username], f"{BASE_URL}/")
            _vao_tab(page, tab)
            page.locator(kiem_tra).first.wait_for(timeout=20000)
        finally:
            ctx.close()
            browser.close()


def test_BTEST02_lanh_dao_vao_bang_dieu_hanh():
    accounts = _mat_khau()
    if "ld.hoa" not in accounts:
        pytest.skip("Thiếu tài khoản demo ld.hoa")

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            _dang_nhap(page, "ld.hoa", accounts["ld.hoa"], f"{BASE_URL}/dieu-hanh/")
            page.get_by_role("heading", name="Bảng điều hành lãnh đạo").wait_for(timeout=20000)
            page.get_by_role("button", name="Chỉ số", exact=True).click()
            page.get_by_text("Đang tải chỉ số…").wait_for(state="detached", timeout=30000)
            page.get_by_role("button", name="Trợ lý", exact=True).click()
            page.get_by_role("heading", name="Trợ lý pháp lý").wait_for(timeout=20000)
        finally:
            ctx.close()
            browser.close()


def test_BTEST02_kiem_toan_vien_vao_nhat_ky():
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
            page.get_by_role("heading", name="Nhật ký kiểm toán").wait_for(timeout=20000)
            page.get_by_text("Chuỗi hợp lệ").or_(page.get_by_text("Chuỗi không hợp lệ")).wait_for(timeout=20000)
        finally:
            ctx.close()
            browser.close()


def test_BTEST02_quan_tri_vien_vao_quan_tri_dia_ban():
    accounts = _mat_khau()
    if "admin" not in accounts:
        pytest.skip("Thiếu tài khoản demo admin")

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            _dang_nhap(page, "admin", accounts["admin"], f"{BASE_URL}/dieu-hanh/")
            page.get_by_role("button", name="Quản trị", exact=True).click()
            page.get_by_role("heading", name="Quản trị địa bàn").wait_for(timeout=20000)
            page.get_by_text("phuong-a").first.wait_for(timeout=20000)
        finally:
            ctx.close()
            browser.close()

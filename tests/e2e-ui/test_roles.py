# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-TEST-02: luồng chính của từng vai trên giao diện thật (Playwright).

Mỗi vai đăng nhập, vào đúng không gian làm việc của mình và thấy đúng thứ được thấy, không thấy thứ
không được thấy. Các luồng chỉ đọc (không nộp, không duyệt) để chạy lặp lại được trên cùng dữ liệu.

Cần stack đã `dx up` với DEMO_MODE=true và `python scripts/seed_hero.py`.
Trình duyệt chọn bằng `--browser` (conftest.py), mặc định Chromium.
"""

import os
import re

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL

sync_api = pytest.importorskip("playwright.sync_api")
expect = sync_api.expect
BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")
CHO = 20000


def _mat_khau(user: str) -> str:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.skip("Thiếu secrets/demo-accounts.txt: chạy `dx up` với DEMO_MODE=true")
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 2 and parts[0] == user:
            return parts[1]
    pytest.skip(f"Thiếu tài khoản demo {user}")


def dang_nhap(page, user: str, url: str = "/") -> None:
    dich = f"{BASE_URL}{url}"
    page.goto(dich, wait_until="domcontentloaded")
    page.get_by_role("button", name="Đăng nhập", exact=True).click()
    page.locator("#username").fill(user)
    page.locator("#password").fill(_mat_khau(user))
    page.locator("#kc-login").click()
    page.wait_for_url(re.compile(re.escape(dich) + r"(\?.*)?$"), timeout=CHO)


def nav(page):
    return page.locator("nav[aria-label='Điều hướng']")


def mo_viec_dau_tien(page) -> None:
    nav(page).get_by_role("button", name="Bàn làm việc", exact=True).click()
    page.get_by_role("button", name="Xem hồ sơ").first.click(timeout=CHO)
    expect(page.locator("[role='dialog']").first).to_be_visible(timeout=CHO)


@pytest.fixture()
def page(trinh_duyet):
    ctx = trinh_duyet.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
    p = ctx.new_page()
    yield p
    ctx.close()


def test_chu_dau_tu(page):
    dang_nhap(page, "cdt.minh")
    tabs = nav(page)
    expect(tabs.get_by_role("button", name="Hồ sơ của tôi", exact=True)).to_be_visible(timeout=CHO)
    expect(tabs.get_by_role("button", name="Dữ liệu của tôi", exact=True)).to_be_visible()
    for khong_duoc in ("Bàn làm việc", "Truy cập khẩn", "Công trình"):
        expect(tabs.get_by_role("button", name=khong_duoc, exact=True)).to_have_count(0)
    # Hồ sơ hero có trong danh sách; mở được hộp nộp hồ sơ với danh mục giấy tờ Điều 60
    expect(page.get_by_text("CP-HERO-2026-001").first).to_be_visible(timeout=CHO)
    page.locator("#btn-nop-ho-so-modal").click()
    expect(page.locator("#form-nop-ho-so")).to_be_visible()
    page.keyboard.press("Escape")


def test_mot_cua(page):
    dang_nhap(page, "mc.thu")
    tabs = nav(page)
    expect(tabs.get_by_role("button", name="Bàn làm việc", exact=True)).to_be_visible(timeout=CHO)
    expect(tabs.get_by_role("button", name="Hồ sơ của tôi", exact=True)).to_have_count(0)
    expect(tabs.get_by_role("button", name="Truy cập khẩn", exact=True)).to_have_count(0)
    mo_viec_dau_tien(page)
    # Hồ sơ mở từ việc của mình có thanh hành động "Việc đang chờ bạn"
    expect(page.locator("#block-dossier-actions")).to_be_visible(timeout=CHO)
    expect(page.get_by_text(re.compile("^Việc đang chờ bạn"))).to_be_visible()


def test_tham_dinh(page):
    dang_nhap(page, "td.binh")
    tabs = nav(page)
    expect(tabs.get_by_role("button", name="Bàn làm việc", exact=True)).to_be_visible(timeout=CHO)
    expect(tabs.get_by_role("button", name="Truy cập khẩn", exact=True)).to_have_count(0)
    mo_viec_dau_tien(page)
    # Thẩm định viên thấy phần quy hoạch có nút kiểm tra
    expect(page.locator("#block-dossier-planning")).to_be_visible(timeout=CHO)
    expect(page.locator("#planning-check-btn")).to_be_visible()


def test_lanh_dao(page):
    dang_nhap(page, "ld.hoa")
    tabs = nav(page)
    expect(tabs.get_by_role("button", name="Bàn làm việc", exact=True)).to_be_visible(timeout=CHO)
    expect(tabs.get_by_role("button", name="Truy cập khẩn", exact=True)).to_be_visible()
    tabs.get_by_role("button", name="Truy cập khẩn", exact=True).click()
    expect(page.get_by_role("heading", name="Truy cập khẩn chờ duyệt")).to_be_visible(timeout=CHO)
    # Bảng điều hành dùng chung phiên đăng nhập
    page.goto(f"{BASE_URL}/dieu-hanh/", wait_until="domcontentloaded")
    expect(page.get_by_text("Bảng điều hành lãnh đạo").first).to_be_visible(timeout=CHO)
    expect(page.get_by_role("button", name="Chỉ số", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Trợ lý", exact=True)).to_be_visible()


def test_trat_tu_xay_dung(page):
    dang_nhap(page, "tt.khanh")
    tabs = nav(page)
    expect(tabs.get_by_role("button", name="Công trình", exact=True)).to_be_visible(timeout=CHO)
    expect(tabs.get_by_role("button", name="Truy cập khẩn", exact=True)).to_have_count(0)
    tabs.get_by_role("button", name="Công trình", exact=True).click()
    expect(page.get_by_text("CT-01").first).to_be_visible(timeout=CHO)


def test_kiem_toan_vien(page):
    dang_nhap(page, "kt.an", "/dieu-hanh/")
    page.get_by_role("button", name="Kiểm toán", exact=True).click()
    expect(page.get_by_text("Nhật ký kiểm toán").first).to_be_visible(timeout=CHO)
    expect(page.get_by_role("button", name="Xác minh")).to_be_visible()
    # Chỉ đọc: không có nút sửa hay xoá bản ghi
    expect(page.get_by_role("button", name=re.compile(r"^(Sửa|Xoá|Xóa)\b"))).to_have_count(0)


def test_cong_khai_khong_dang_nhap(page):
    r = page.goto(f"{BASE_URL}/kiem-tra/", wait_until="domcontentloaded")
    assert r is not None and r.status == 200
    expect(page.locator("input[name='ma']")).to_be_visible(timeout=CHO)
    assert page.locator("script").count() == 0, "Trang tra cứu công khai không được có script"

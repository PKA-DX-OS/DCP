# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-FLOW-05: duyệt hồ sơ trên UI thật qua action bar (Playwright)."""

import os
import re

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL
from tests.integration._ho_so import cap_phep_den_buoc_duyet

sync_api = pytest.importorskip("playwright.sync_api")
BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")

PAYLOAD = {
    "ho_ten": "Nguyễn Văn UI Duyệt",
    "cccd": "001099007777",
    "dien_thoai": "0907777777",
    "dia_chi_cong_trinh": "Số 77 Đường UI Duyệt, phường A",
    "thua_dat": "TD-A-01",
    "so_tang": 3,
    "dien_tich_san_m2": 150.0,
    "khu_quan_ly_kien_truc": True,
}


def _mat_khau() -> dict[str, str]:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.skip("Thiếu secrets/demo-accounts.txt")
    ds = {}
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 2 and parts[0] and not parts[0].startswith("#"):
            ds[parts[0]] = parts[1]
    return ds


def test_AFLOW_05_phe_duyet_tren_ui():
    accounts = _mat_khau()
    if "ld.hoa" not in accounts:
        pytest.skip("Thiếu tài khoản demo ld.hoa")

    ctx = cap_phep_den_buoc_duyet("cdt.minh", PAYLOAD, "AFLOW-UI")
    ma = ctx["ho_so"]["ma_ho_so"]

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        page_ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = page_ctx.new_page()
        try:
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            page.get_by_role("button", name="Đăng nhập", exact=True).click()
            page.locator("#username").fill("ld.hoa")
            page.locator("#password").fill(accounts["ld.hoa"])
            page.locator("#kc-login").click()
            page.wait_for_url(re.compile(re.escape(BASE_URL) + r"/(\?.*)?$"), timeout=20000)
            page.get_by_role("button", name="Đăng xuất").wait_for(timeout=20000)

            page.get_by_role("button", name="Bàn làm việc", exact=True).click()
            viec = page.locator("li").filter(has_text=f"Mã hồ sơ: {ma}")
            viec.get_by_role("button", name="Xem hồ sơ").click()
            page.locator("#modal-detail-dossier").wait_for(timeout=20000)
            page.locator("#block-dossier-actions").wait_for(timeout=20000)

            page.get_by_role("button", name="Phê duyệt và ký", exact=True).click()
            page.get_by_role("button", name="Xác nhận", exact=True).click()
            page.locator("#detail-trang-thai").filter(has_text="cấp phép").wait_for(timeout=30000)
        finally:
            page_ctx.close()
            browser.close()

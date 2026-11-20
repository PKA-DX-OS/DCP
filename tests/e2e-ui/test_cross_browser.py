# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-TEST-03: chạy giao diện trên Chromium, Firefox, WebKit và đo hiệu năng cơ bản."""

import json
import os
import re
import time
from pathlib import Path

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, ROOT

sync_api = pytest.importorskip("playwright.sync_api")
BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")
BROWSERS = ("chromium", "firefox", "webkit")
KET_QUA = ROOT / "logs" / "qa-ui"


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


def _chi_so_hieu_nang(page) -> dict:
    return page.evaluate(
        """() => {
          const nav = performance.getEntriesByType('navigation')[0] || {};
          const paint = performance.getEntriesByType('paint');
          const fcp = paint.find((p) => p.name === 'first-contentful-paint');
          const tai = performance.getEntriesByType('resource')
            .reduce((tong, r) => tong + (r.transferSize || 0), 0);
          return {
            fcp_ms: fcp ? Math.round(fcp.startTime) : null,
            dom_content_loaded_ms: Math.round(nav.domContentLoadedEventEnd || 0),
            load_ms: Math.round(nav.loadEventEnd || 0),
            transfer_kb: Math.round(tai / 1024),
          };
        }"""
    )


@pytest.mark.parametrize("browser_name", BROWSERS)
def test_BTEST03_giao_dien_chay_tren_da_trinh_duyet(browser_name: str):
    accounts = _mat_khau()
    if "ld.hoa" not in accounts:
        pytest.skip("Thiếu tài khoản demo ld.hoa")

    with sync_api.sync_playwright() as pw:
        kwargs: dict = {"headless": os.getenv("E2E_HEADED", "") != "1"}
        if browser_name == "firefox":
            # Windows có thể có listener IPv4 khác trên 8080 (Docker/WSL/Hyper-V);
            # ưu tiên IPv6 giúp Firefox đi đúng cổng của stack cục bộ.
            kwargs["firefox_user_prefs"] = {"network.dns.preferIPv6": True}
        browser = getattr(pw, browser_name).launch(**kwargs)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            page.get_by_text("DX-OS Open-Core").first.wait_for(timeout=20000)
            page.get_by_role("button", name="Đăng nhập", exact=True).wait_for(timeout=20000)

            _dang_nhap(page, "ld.hoa", accounts["ld.hoa"], f"{BASE_URL}/dieu-hanh/")
            page.get_by_role("heading", name="Bảng điều hành lãnh đạo").wait_for(timeout=20000)
            page.get_by_role("button", name="Chỉ số", exact=True).click()
            page.get_by_text("Đang tải chỉ số…").wait_for(state="detached", timeout=30000)
        finally:
            ctx.close()
            browser.close()


def test_BTEST03_do_hieu_nang_trang_chinh():
    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        ket_qua: dict[str, dict] = {}
        try:
            luc = time.perf_counter()
            page.goto(f"{BASE_URL}/", wait_until="load")
            page.get_by_text("DX-OS Open-Core").first.wait_for(timeout=20000)
            ket_qua["trang_chao"] = _chi_so_hieu_nang(page)
            ket_qua["trang_chao"]["do_bang_ms"] = round((time.perf_counter() - luc) * 1000)

            page.goto(f"{BASE_URL}/kiem-tra/", wait_until="load")
            page.locator("#ma-tra-cuu").wait_for(timeout=20000)
            ket_qua["tra_cuu"] = _chi_so_hieu_nang(page)
        finally:
            ctx.close()
            browser.close()

    KET_QUA.mkdir(parents=True, exist_ok=True)
    tep = KET_QUA / "performance.json"
    tep.write_text(
        json.dumps(
            {
                "base_url": BASE_URL,
                "browser": "chromium",
                "viewport": "1366x900",
                "ket_qua": ket_qua,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # Ngưỡng rộng cho máy CI/Windows; mục tiêu là phát hiện hồi quy lớn, không phải benchmark.
    assert ket_qua["trang_chao"]["fcp_ms"] is None or ket_qua["trang_chao"]["fcp_ms"] < 5000
    assert ket_qua["trang_chao"]["dom_content_loaded_ms"] < 10000
    assert ket_qua["tra_cuu"]["dom_content_loaded_ms"] < 10000

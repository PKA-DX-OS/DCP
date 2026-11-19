# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B-REVIEW-04..07: tab Thiết kế, phiên bản, nhận xét trên UI thật."""

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


def test_B_design_review_tab_versions_comments():
    accounts = _mat_khau()
    if "cdt.minh" not in accounts:
        pytest.skip("Thiếu tài khoản demo cdt.minh")
    subprocess.run([sys.executable, "scripts/seed_hero.py"], cwd=ROOT, check=True)

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            page.get_by_role("button", name="Đăng nhập", exact=True).click()
            page.locator("#username").fill("cdt.minh")
            page.locator("#password").fill(accounts["cdt.minh"])
            page.locator("#kc-login").click()
            page.wait_for_url(re.compile(re.escape(BASE_URL) + r"/(\?.*)?$"), timeout=20000)
            page.get_by_role("button", name="Đăng xuất").wait_for(timeout=20000)

            page.get_by_role("button", name="Hồ sơ của tôi", exact=True).click()
            page.locator("#btn-detail-CP-HERO-2026-001").click()
            page.locator("#modal-detail-dossier").wait_for(timeout=20000)
            page.get_by_role("button", name="Thiết kế", exact=True).click()
            page.locator("#block-design-review").wait_for(timeout=20000)
            page.get_by_text("Đủ bộ môn bắt buộc").wait_for(timeout=20000)

            page.get_by_role("tab", name=re.compile("Phiên bản")).click()
            page.locator("#design-review-versions").wait_for(timeout=20000)
            page.get_by_text(re.compile("v1 → v2")).wait_for(timeout=20000)
            page.locator("#design-review-version-1").click()
            page.wait_for_timeout(800)

            page.get_by_role("tab", name=re.compile("Nhận xét")).click()
            page.locator("#design-review-comments").wait_for(timeout=20000)
            page.get_by_text("Bổ sung sơ đồ cấp điện").wait_for(timeout=20000)
        finally:
            ctx.close()
            browser.close()

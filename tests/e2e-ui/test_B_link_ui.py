# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""H-LINK: tra cứu liên ngành mock trong chi tiết hồ sơ, không lưu PII."""

import os
import re
import subprocess
import sys

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, ROOT
from tests.integration._ho_so import run_sql

sync_api = pytest.importorskip("playwright.sync_api")
BASE_URL = os.getenv("E2E_BASE_URL", GATEWAY_URL).rstrip("/")
MA_HO_SO = "CP-HERO-2026-001"


def _mat_khau() -> dict[str, str]:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.skip("Thiếu secrets/demo-accounts.txt")
    ds = {}
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 2 and parts[0] and not parts[0].startswith("#"):
            ds[parts[0]] = parts[1]
    return ds


def _dang_nhap(page, username: str, password: str) -> None:
    page.goto(BASE_URL + "/", wait_until="domcontentloaded")
    page.get_by_role("button", name="Đăng nhập", exact=True).click()
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("#kc-login").click()
    page.wait_for_url(re.compile(re.escape(BASE_URL) + r"/(\?.*)?$"), timeout=20000)
    page.get_by_role("button", name="Đăng xuất").wait_for(timeout=20000)


def _mo_ho_so(page, ma: str) -> None:
    page.keyboard.press("Control+K")
    o = page.get_by_label("Từ khóa tìm kiếm toàn cục")
    o.fill(ma)
    page.get_by_role("button").filter(has_text=ma).first.click()
    page.locator("#btn-close-modal-detail").wait_for(timeout=20000)


def test_H_LINK_tra_cuu_mock_va_khong_luu_pii():
    accounts = _mat_khau()
    if "mc.thu" not in accounts:
        pytest.skip("Thiếu tài khoản demo mc.thu")
    subprocess.run([sys.executable, "scripts/seed_hero.py"], cwd=ROOT, check=True)

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            _dang_nhap(page, "mc.thu", accounts["mc.thu"])
            _mo_ho_so(page, MA_HO_SO)
            page.get_by_role("button", name="Liên ngành", exact=True).first.click()

            panel = page.locator("#block-dossier-link")
            panel.get_by_text("Đối chiếu liên ngành", exact=True).wait_for(timeout=20000)
            panel.get_by_text("Dữ liệu mẫu", exact=True).wait_for(timeout=20000)
            panel.get_by_text("Liên kết dữ liệu chủ bên dưới dùng API MDM thật", exact=False).wait_for(timeout=20000)

            panel.get_by_role("button", name="Tra cứu", exact=True).click()
            panel.get_by_text("Khớp hồ sơ", exact=True).wait_for(timeout=20000)
            text = panel.inner_text()
            assert re.search(r"\d{4}\*{4}\d{4}", text), text[:1200]
            assert "001099000001" not in text
            assert "0901234567" not in text

            panel.get_by_role("button", name="Xác nhận đối chiếu", exact=True).click()
            panel.get_by_text("Đã xác nhận 1/4 nguồn", exact=False).wait_for(timeout=20000)

            # Liên kết dữ liệu chủ thật qua API MDM, có audit.
            panel.get_by_label("Từ khóa tìm dữ liệu chủ").fill("td-a-01")
            panel.get_by_role("button", name="Tìm", exact=True).click()
            panel.get_by_text("Thửa td-a-01", exact=False).first.wait_for(timeout=20000)
            panel.get_by_role("button", name="Liên kết", exact=True).first.click()
            panel.get_by_text("Đã liên kết Thửa td-a-01", exact=False).first.wait_for(timeout=20000)
            assert "mdm.entity.linked" in panel.inner_text()

            dossier_id = run_sql("SELECT id FROM app_cap_phep.ho_so WHERE ma_ho_so = 'CP-HERO-2026-001'")
            so_audit = run_sql(
                "SELECT count(*) FROM core.audit_log "
                f"WHERE action = 'mdm.entity.linked' AND object_id = '{dossier_id}'"
            )
            assert int(so_audit) >= 1, f"không thấy audit mdm.entity.linked cho {dossier_id}"

            storage = page.evaluate("() => JSON.stringify({...localStorage, ...sessionStorage})")
            assert "001099000001" not in storage
            assert "0901234567" not in storage
        finally:
            ctx.close()
            browser.close()

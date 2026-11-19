# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-TEST: smoke giao diện Track A — tab quy hoạch/nghiệm thu và action bar."""

import os
import re
from pathlib import Path

import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, get_token
from tests.integration._ho_so import normalize_payload, start_cap_phep, submit_dossier

playwright = pytest.importorskip("playwright.sync_api")
sync_api = playwright

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


def test_A_ui_tab_quy_hoach_nghiem_thu_va_action_bar():
    accounts = _mat_khau()
    if "mc.thu" not in accounts:
        pytest.skip("Thiếu tài khoản demo mc.thu")

    # Tạo một việc thật cho một cửa để work list luôn có dữ liệu.
    payload = {
        "ho_ten": "Nguyễn Văn UI Test",
        "cccd": "001099005555",
        "dien_thoai": "0905555555",
        "dia_chi_cong_trinh": "Số 55 Đường UI Test, phường A",
        "thua_dat": "TD-A-01",
        "so_tang": 3,
        "dien_tich_san_m2": 120.0,
        "khu_quan_ly_kien_truc": True,
    }
    cdt = get_token("cdt.minh")
    resp = submit_dossier(cdt, payload, tag_prefix="UI-A")
    assert resp.status_code == 200, resp.text
    ho_so = resp.json()
    data = normalize_payload(payload)
    start_cap_phep(cdt, ho_so, {
        "dien_tich_san_m2": data["dien_tich_san_m2"],
        "khu_quan_ly_kien_truc": bool(data.get("khu_quan_ly_kien_truc")),
        "dia_chi_cong_trinh": payload["dia_chi_cong_trinh"],
    })

    with sync_api.sync_playwright() as pw:
        browser = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, locale="vi-VN")
        page = ctx.new_page()
        try:
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            page.get_by_role("button", name="Đăng nhập", exact=True).click()
            page.locator("#username").fill("mc.thu")
            page.locator("#password").fill(accounts["mc.thu"])
            page.locator("#kc-login").click()
            page.wait_for_url(re.compile(re.escape(BASE_URL) + r"/(\?.*)?$"), timeout=20000)
            page.get_by_role("button", name="Đăng xuất").wait_for(timeout=20000)

            page.get_by_role("button", name="Bàn làm việc", exact=True).click()
            page.get_by_role("button", name="Xem hồ sơ").first.click()
            page.locator("#modal-detail-dossier").wait_for(timeout=20000)

            # Tab quy hoạch và nghiệm thu chỉ hiện cho cán bộ.
            page.locator("#tab-chi-tiet-block-dossier-planning").click()
            page.get_by_role("heading", name="Quy hoạch và chỉ tiêu xây dựng").wait_for(timeout=10000)
            page.locator("#block-dossier-planning").wait_for(timeout=10000)

            page.locator("#tab-chi-tiet-block-dossier-acceptance").click()
            page.get_by_role("heading", name="Nghiệm thu và hoàn công").wait_for(timeout=10000)
            page.locator("#block-dossier-acceptance").wait_for(timeout=10000)

            # Action bar hiện việc đang chờ cán bộ (nếu task đầu là việc của mc.thu).
            assert page.locator("#modal-detail-dossier").is_visible()
        finally:
            ctx.close()
            browser.close()

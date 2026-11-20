# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Fixture dùng chung cho test giao diện.

`trinh_duyet`: một trình duyệt Playwright, chạy lại test theo từng giá trị `--browser`
(chromium, firefox, webkit; mặc định chromium):

    pytest tests/e2e-ui -q --browser chromium --browser firefox --browser webkit

Nếu đã cài pytest-playwright thì dùng luôn tuỳ chọn `--browser` của plugin đó.
Fixture có phạm vi module: Playwright đóng sau mỗi tệp test, nên các test tự mở `sync_playwright()`
(test_demo_flow, test_B_*) vẫn chạy chung một phiên pytest được.
"""

import os

import pytest

TRINH_DUYET = ("chromium", "firefox", "webkit")


def pytest_addoption(parser):
    try:
        parser.addoption(
            "--browser",
            action="append",
            default=[],
            choices=TRINH_DUYET,
            help="Trình duyệt chạy test giao diện; lặp lại để chạy nhiều trình duyệt (mặc định chromium)",
        )
    except ValueError:
        pass  # pytest-playwright đã khai báo --browser


def pytest_generate_tests(metafunc):
    if "ten_trinh_duyet" in metafunc.fixturenames:
        ds = metafunc.config.getoption("browser") or ["chromium"]
        metafunc.parametrize("ten_trinh_duyet", list(dict.fromkeys(ds)), scope="module")


@pytest.fixture(scope="module")
def trinh_duyet(ten_trinh_duyet):
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as pw:
        try:
            b = getattr(pw, ten_trinh_duyet).launch(headless=os.getenv("E2E_HEADED", "") != "1")
        except Exception as exc:  # chưa tải trình duyệt này
            pytest.skip(f"Không mở được {ten_trinh_duyet}: chạy `python -m playwright install {ten_trinh_duyet}` ({exc})")
        yield b
        b.close()

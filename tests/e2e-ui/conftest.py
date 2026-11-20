# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Fixture dùng chung cho test giao diện: một trình duyệt Playwright cho cả phiên test."""

import os

import pytest


@pytest.fixture(scope="session")
def trinh_duyet():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as pw:
        b = pw.chromium.launch(headless=os.getenv("E2E_HEADED", "") != "1")
        yield b
        b.close()

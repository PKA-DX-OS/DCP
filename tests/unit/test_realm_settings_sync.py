# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Đồng bộ theme đăng nhập và ngôn ngữ của realm Keycloak đang chạy theo template."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))

from dxos_core import user_sync  # noqa: E402


def test_template_co_theme_dxos_va_tieng_viet():
    s = user_sync.realm_settings_from_template()
    assert s["loginTheme"] == "dxos"
    assert s["defaultLocale"] == "vi"
    assert "vi" in s["supportedLocales"]
    assert s["internationalizationEnabled"] is True


def test_chi_lay_khoa_giao_dien(tmp_path):
    t = tmp_path / "realm.json"
    t.write_text(json.dumps({"loginTheme": "dxos", "sslRequired": "none", "clients": []}), encoding="utf-8")
    assert user_sync.realm_settings_from_template(t) == {"loginTheme": "dxos"}
    assert user_sync.realm_settings_from_template(tmp_path / "khong-co.json") == {}


def test_chi_cap_nhat_khoa_khac():
    wanted = {"loginTheme": "dxos", "supportedLocales": ["vi", "en"], "defaultLocale": "vi"}
    assert user_sync.realm_settings_diff({"loginTheme": "dxos", "supportedLocales": ["en", "vi"], "defaultLocale": "vi"}, wanted) == {}
    assert user_sync.realm_settings_diff({"loginTheme": None, "supportedLocales": [], "defaultLocale": "vi"}, wanted) == {
        "loginTheme": "dxos",
        "supportedLocales": ["vi", "en"],
    }


def test_theme_co_nhan_tieng_viet_cho_trang_dang_nhap_va_loi():
    thu_muc = ROOT / "core" / "keycloak" / "themes" / "dxos" / "login"
    props = (thu_muc / "theme.properties").read_text(encoding="utf-8")
    assert "vi" in next(d for d in props.splitlines() if d.startswith("locales=")).split("=", 1)[1].split(",")
    vi = (thu_muc / "messages" / "messages_vi.properties").read_text(encoding="utf-8")
    khoa = {d.split("=", 1)[0] for d in vi.splitlines() if "=" in d and not d.startswith("#")}
    for k in ("doLogIn", "usernameOrEmail", "password", "errorTitle", "cookieNotFoundMessage", "backToApplication"):
        assert k in khoa, k

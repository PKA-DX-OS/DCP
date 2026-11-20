# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Ghép route APISIX: CSP lấy từ .env và mọi route fragment đều có trong apisix.yaml kết xuất."""

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("build_apisix", ROOT / "scripts" / "build_apisix.py")
build_apisix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_apisix)


def test_csp_tu_env_mac_dinh_va_nhieu_origin():
    assert build_apisix.csp_tu_env({}) == "http://localhost:8080 http://localhost:8081 http://localhost:8080/auth"
    csp = build_apisix.csp_tu_env(
        {"PUBLIC_BASE_URL": "http://localhost:8080, https://dxos.example.vn/", "KEYCLOAK_PUBLIC_URL": "https://id.example.vn/"}
    )
    assert csp.split() == ["http://localhost:8080", "https://dxos.example.vn", "https://id.example.vn", "http://localhost:8080/auth"]


def test_doc_env_bo_chu_thich(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# chu thich\nPUBLIC_BASE_URL=https://a.vn\n\nKHAC = 1\n", encoding="utf-8")
    assert build_apisix.doc_env(env) == {"PUBLIC_BASE_URL": "https://a.vn", "KHAC": "1"}
    assert build_apisix.doc_env(tmp_path / "khong-co") == {}


def test_from_env_ghi_du_route_fragment(tmp_path):
    out = tmp_path / "apisix.yaml"
    assert build_apisix.main(["--from-env", "--output", str(out)]) == 0
    ids = {r["id"] for r in yaml.safe_load(out.read_text(encoding="utf-8").replace("#END", ""))["routes"]}
    for frag in (ROOT / "core" / "apisix" / "routes").glob("*.yaml"):
        for route in (yaml.safe_load(frag.read_text(encoding="utf-8")) or {}).get("routes") or []:
            assert route["id"] in ids, f"{frag.name}: thiếu {route['id']}"

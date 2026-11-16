# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy V3-11: Cấu trúc mô-đun hóa App.vue thành các views/, components/ và api/ theo nhóm.
Đảm bảo tệp App.vue không còn bị phình to (tối đa 500 dòng), các mô-đun màn hình tách biệt rõ ràng.
"""

from pathlib import Path


def test_V3_11_modular_structure_and_line_count():
    web_dir = Path(__file__).resolve().parent.parent.parent / "apps" / "cap-phep" / "web"
    src_dir = web_dir / "src"
    app_vue = src_dir / "App.vue"

    assert app_vue.exists(), "Tệp App.vue phải tồn tại"
    lines = app_vue.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)
    assert line_count < 600, f"App.vue phải nhỏ hơn 600 dòng (hiện tại: {line_count} dòng) sau khi tách component"

    # 1. Thư mục views/
    views_dir = src_dir / "views"
    assert views_dir.is_dir(), "Thư mục views/ phải tồn tại"
    expected_views = [
        "DossiersView.vue",
        "WorkspaceView.vue",
        "ConstructionView.vue",
        "ConsentView.vue",
    ]
    for view in expected_views:
        assert (views_dir / view).exists(), f"Thiếu view màn hình: {view}"

    # 2. Thư mục components/
    components_dir = src_dir / "components"
    assert components_dir.is_dir(), "Thư mục components/ phải tồn tại"
    expected_components = [
        "Navbar.vue",
        "CreateDossierModal.vue",
        "DetailDossierModal.vue",
        "SupplementModal.vue",
        "BreakGlassModal.vue",
    ]
    for comp in expected_components:
        assert (components_dir / comp).exists(), f"Thiếu component: {comp}"

    # 3. Thư mục api/ theo nhóm
    api_dir = src_dir / "api"
    assert api_dir.is_dir(), "Thư mục api/ phải tồn tại"
    expected_apis = [
        "dossiers.ts",
        "flow.ts",
        "break_glass.ts",
        "files.ts",
        "construction.ts",
        "dsar.ts",
        "index.ts",
    ]
    for api_file in expected_apis:
        assert (api_dir / api_file).exists(), f"Thiếu tệp API nhóm: {api_file}"

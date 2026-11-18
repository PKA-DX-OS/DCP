# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V3-11: web cấp phép tách thành views/, components/, composables/, api/; App.vue chỉ làm khung."""

from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "apps" / "cap-phep" / "web" / "src"

CAN_CO = {
    "views": ["DossiersView.vue", "WorkspaceView.vue", "ConstructionView.vue", "ConsentView.vue", "TruyCapKhanView.vue"],
    "components": ["Navbar.vue", "CreateDossierModal.vue", "DetailDossierModal.vue", "SupplementModal.vue",
                   "BreakGlassModal.vue", "Forbidden403Modal.vue", "DocumentChecklist.vue", "ToastHost.vue"],
    "composables": ["useCongDan.ts", "useDossierActions.ts", "useNotifications.ts", "useModal.ts", "useToast.ts"],
    "api": ["client.ts", "dossiers.ts", "flow.ts", "break_glass.ts", "files.ts", "construction.ts", "dsar.ts", "index.ts"],
}


def test_V3_11_modular_structure_and_line_count():
    app = SRC / "App.vue"
    assert app.exists()
    so_dong = len(app.read_text(encoding="utf-8").splitlines())
    assert so_dong < 400, f"App.vue {so_dong} dòng: logic màn hình phải nằm trong views/composables"
    for thu_muc, ds in CAN_CO.items():
        for ten in ds:
            assert (SRC / thu_muc / ten).exists(), f"Thiếu {thu_muc}/{ten}"


def test_V3_11_component_khong_goi_api_truc_tiep():
    # Component chỉ hiển thị và phát sự kiện; gọi API qua api/*.ts (DetailDossierModal tự tải tệp, lịch sử)
    cho_phep = {"DetailDossierModal.vue"}
    for f in (SRC / "components").glob("*.vue"):
        if f.name in cho_phep:
            continue
        text = f.read_text(encoding="utf-8")
        assert "fetch(" not in text and "/api/v1/" not in text, f"{f.name} gọi API trực tiếp"

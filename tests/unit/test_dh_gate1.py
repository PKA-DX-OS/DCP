# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""D Gate 1: migration 20–24, API theo contracts/dh (trừ OCR), route APISIX, worker DQ, khóa HMAC.

Phần cần DB được kiểm ở tests/integration/test_dh_gate1_api.py; ở đây kiểm hàm thuần, cấu hình,
độ phủ route so với hợp đồng và lỗi theo hợp đồng khi sai vai (không cần DB)."""

import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
PG = ROOT / "core" / "postgres"


def _nap(ten: str, duong_dan: Path):
    spec = importlib.util.spec_from_file_location(ten, duong_dan)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[ten] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ung_dung():
    pytest.importorskip("openpyxl")
    from construction import main
    return main


def test_che_du_lieu_ca_nhan():
    from construction.dh import che_cccd, che_dien_thoai
    assert che_cccd("001234567890") == "0012******90"
    assert che_cccd("12345") is None and che_cccd(None) is None
    assert che_dien_thoai("0901234567") == "090****567"
    assert che_dien_thoai("+84 901 234 567") == "090****567"
    assert che_dien_thoai("123") is None


def test_hmac_cccd_can_khoa(tmp_path):
    from construction.dh import cccd_hmac
    assert cccd_hmac("001234567890", tmp_path / "khong-co.key") is None
    khoa = tmp_path / "k.key"
    khoa.write_text("a" * 64, encoding="utf-8")
    h1, h2 = cccd_hmac("001234567890", khoa), cccd_hmac("0012 3456 7890", khoa)
    assert h1 == h2 and len(h1) == 64 and "001234567890" not in h1
    assert cccd_hmac("12345", khoa) is None


def test_tach_thua_dat():
    from construction.dh_mdm import tach_thua_dat
    assert tach_thua_dat("12/3") == ("12", "3")
    assert tach_thua_dat("Thửa 12, tờ 3") == ("12", "3")
    assert tach_thua_dat("Thua abc") == ("thua abc", None)
    assert tach_thua_dat("  ") == (None, None)


def test_do_thi_pha_he():
    lineage = _nap("dh_lineage_test", ROOT / "services/construction/routers/lineage.py")
    g = lineage.do_thi("ho_so", "x", [{"job": "cap_phep", "run_id": "r1", "event_time": "t",
                                        "inputs": [{"namespace": "app", "name": "ho_so"}],
                                        "outputs": [{"namespace": "core", "name": "signed_docs"}]}])
    kinds = {n["kind"] for n in g["nodes"]}
    assert kinds == {"entity", "job", "dataset"}
    assert {(e["from"], e["to"]) for e in g["edges"]} == {
        ("entity:ho_so:x", "job:cap_phep"), ("dataset:app.ho_so", "job:cap_phep"), ("job:cap_phep", "dataset:core.signed_docs")}
    assert lineage.do_thi("ho_so", "x", [])["edges"] == []


def test_chi_so_h_cung_cong_thuc():
    am = _nap("dh_auto_test", ROOT / "services/construction/routers/automation_metrics.py")
    kq = am.tinh({"tong_ho_so": 4, "thao_tac": [1, 3, 2, 2], "chuyen_tay": [0, 1], "ho_so_phai_bo_sung": 1,
                  "thao_tac_chu_dau_tu": 2, "thao_tac_nguoi_dung": 8, "giay_phep": 2, "ky_dung_han": 1,
                  "ngay_lam_viec": [4, 9]}, 0)
    assert kq["thao_tac_thu_cong_tb"] == 2.0 and kq["chuyen_tay_tb"] == 0.5
    assert kq["ty_le_ho_so_phai_bo_sung_pct"] == 25.0 and kq["ty_le_tu_phuc_vu_pct"] == 25.0
    assert kq["thoi_gian_xu_ly_tb_ngay_lam_viec"] == 6.5 and kq["ty_le_ky_dung_han_pct"] == 50.0
    trong = am.tinh({"tong_ho_so": 0}, None)
    assert all(v is None for v in trong.values())
    assert am.chenh_lech(3.0, 4.0) == -25.0 and am.chenh_lech(3.0, None) is None
    assert [k for k, *_ in am.CHI_SO] == yaml.safe_load(
        (ROOT / "contracts/dh/automation.yaml").read_text(encoding="utf-8"))["components"]["schemas"]["KhoaChiSo"]["enum"]


def test_worker_tong_hop_va_trang_thai():
    w = _nap("dh_worker_test", ROOT / "scripts/data_quality_worker.py")
    kq = w.tong_hop({"a": 10, "b": 0}, [{"tenant": "a", "entity_id": str(i)} for i in range(7)] + [{"tenant": "b", "entity_id": "x"}])
    assert kq["a"] == {"total": 10, "failed": 7, "sample_ids": ["0", "1", "2", "3", "4"], "score": 30.0}
    assert kq["b"]["total"] == 1 and kq["b"]["score"] == 0.0
    assert w.trang_thai_lan_chay(3, 0) == "succeeded"
    assert w.trang_thai_lan_chay(3, 1) == "partial"
    assert w.trang_thai_lan_chay(3, 3) == "failed"


def test_khoa_hmac_khong_ghi_de(tmp_path):
    k = _nap("dh_khoa_test", ROOT / "scripts/dh_khoa.py")
    assert k.dam_bao_khoa(tmp_path) is True
    cu = (tmp_path / "mdm-hmac.key").read_text(encoding="utf-8")
    assert re.fullmatch(r"[0-9a-f]{64}\n", cu)
    assert k.dam_bao_khoa(tmp_path) is False
    assert (tmp_path / "mdm-hmac.key").read_text(encoding="utf-8") == cu


def test_migration_d_du_bang_va_idempotent():
    can = {
        "20-data-governance.sql": ["core.data_owners", "core.data_assets", "core.data_asset_columns"],
        "21-mdm.sql": ["core.mdm_subject", "core.mdm_parcel", "core.mdm_construction", "core.mdm_organization",
                       "core.mdm_dossier_link", "core.mdm_link_candidate", "core.mdm_merge_log", "core.dh_idempotency"],
        "22-data-quality.sql": ["core.data_quality_rules", "core.data_quality_runs", "core.data_quality_results",
                                "core.data_quality_issues"],
        "23-catalog-lineage.sql": ["core.data_contracts", "core.h_baseline"],
        "24-external-refs.sql": ["core.external_refs"],
    }
    for tep, bang in can.items():
        sql = (PG / tep).read_text(encoding="utf-8")
        for b in bang:
            assert f"CREATE TABLE IF NOT EXISTS {b}" in sql, (tep, b)
        assert "FORCE ROW LEVEL SECURITY" in sql, tep
        assert "DROP TABLE" not in sql.upper(), tep
    # CCCD chỉ lưu HMAC
    mdm = (PG / "21-mdm.sql").read_text(encoding="utf-8")
    assert "cccd_hmac" in mdm and re.search(r"\bcccd\s+text", mdm) is None


def test_rule_dq_du_va_dung_dinh_dang():
    sql = (PG / "22-data-quality.sql").read_text(encoding="utf-8")
    ma = re.findall(r"^\('(DQ-[A-Z]+-\d{2})', '([a-z_]+)', '([a-z]+)', '([a-z]+)'", sql, re.MULTILINE)
    assert len(ma) >= 20
    mien = {m[1] for m in ma}
    hop_dong = yaml.safe_load((ROOT / "contracts/dh/data-quality.yaml").read_text(encoding="utf-8"))["components"]["schemas"]
    assert mien <= set(hop_dong["MienDuLieu"]["enum"])
    assert {m[2] for m in ma} <= set(hop_dong["ChieuDQ"]["enum"])
    assert {m[3] for m in ma} <= set(hop_dong["MucDo"]["enum"])
    assert len({m[0] for m in ma}) == len(ma)
    # web_user không đọc được câu SQL của rule
    assert "GRANT SELECT (code, domain, dimension, severity, entity_type, description, owner, enabled, created_at)" in sql


def test_danh_muc_du_9_mien():
    sql = (PG / "20-data-governance.sql").read_text(encoding="utf-8")
    mien = set(re.findall(r"^\s+\('([a-z_]+)', '[^']+', '[^']+', '[^']*'", sql, re.MULTILINE))
    hop_dong = yaml.safe_load((ROOT / "contracts/dh/data-quality.yaml").read_text(encoding="utf-8"))
    assert mien == set(hop_dong["components"]["schemas"]["MienDuLieu"]["enum"])


def test_route_apisix_va_dich_vu_phu_du_hop_dong(ung_dung):
    route = yaml.safe_load((ROOT / "core/apisix/routes/dh.yaml").read_text(encoding="utf-8"))["routes"]
    tien_to = {r["uri"].rstrip("*") for r in route}
    assert all(r["upstream"]["nodes"] == {"construction:8000": 1} for r in route)
    assert all("openid-connect" in r["plugins"] for r in route)
    co = {(r.path, m.lower()) for r in ung_dung.app.routes for m in getattr(r, "methods", set()) or set()}
    for tep in sorted((ROOT / "contracts/dh").glob("*.yaml")):
        if tep.stem == "ocr":  # dịch vụ ocr riêng (DH_OCR), Gate 3
            continue
        spec = yaml.safe_load(tep.read_text(encoding="utf-8"))
        for duong_dan, ops in spec["paths"].items():
            assert any(duong_dan.startswith(t) for t in tien_to), duong_dan
            for m in ops:
                ten = re.sub(r"\{[^}]+\}", "{x}", duong_dan)
                assert any(re.sub(r"\{[^}]+\}", "{x}", p) == ten and mm == m for p, mm in co), (m, duong_dan)


def test_loi_sai_vai_dung_hop_dong(ung_dung, monkeypatch):
    goi = SimpleNamespace(sub="s", tenant="t", roles=["app:cap-phep:mot-cua"], preferred_username="u")
    from construction.routers import automation_metrics, catalog, mdm
    for mod in (catalog, automation_metrics, mdm):
        monkeypatch.setattr(mod, "verify_jwt_token", lambda _a: goi)
    c = TestClient(ung_dung.app)
    r = c.get("/api/v1/catalog/assets", headers={"Authorization": "Bearer x"})
    assert r.status_code == 403 and set(r.json()) == {"code", "message", "details"}
    assert c.get("/api/v1/automation/metrics", headers={"Authorization": "Bearer x"}).status_code == 403
    r = c.post("/api/v1/mdm/merge", headers={"Authorization": "Bearer x", "Idempotency-Key": "k" * 10},
               json={"entity_type": "parcel", "giu_id": "6f0c2b9e-1111-4c1a-9e0a-000000000001",
                     "gop_ids": ["6f0c2b9e-1111-4c1a-9e0a-000000000002"], "ly_do": "thử quyền"})
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"

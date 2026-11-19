# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""B-P0-06: contract 5.2 (contracts/design-review.yaml) đọc được, tự nhất quán, và fixture của giao diện
khớp schema. Bộ kiểm schema tối giản ở đây (type, required, enum, const, pattern, items, oneOf, allOf, $ref)
để không thêm phụ thuộc."""
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts" / "design-review.yaml"
FIXTURES = ROOT / "apps" / "cap-phep" / "web" / "src" / "features" / "design-review" / "fixtures"
SPEC = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
SCHEMAS = SPEC["components"]["schemas"]

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "boolean": bool,
    "null": type(None),
}


def _resolve(ref: str) -> dict:
    assert ref.startswith("#/components/schemas/"), ref
    return SCHEMAS[ref.rsplit("/", 1)[1]]


def _errors(value, schema: dict, path: str = "$") -> list[str]:
    if "$ref" in schema:
        return _errors(value, _resolve(schema["$ref"]), path)
    if "allOf" in schema:
        return [e for s in schema["allOf"] for e in _errors(value, s, path)]
    if "oneOf" in schema:
        ok = [s for s in schema["oneOf"] if not _errors(value, s, path)]
        return [] if len(ok) == 1 else [f"{path}: khớp {len(ok)} nhánh oneOf"]
    out: list[str] = []
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(isinstance(value, _TYPES[x]) and not (x == "integer" and isinstance(value, bool)) for x in types):
            return [f"{path}: kiểu {type(value).__name__}, cần {types}"]
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path}: {value!r} không thuộc {schema['enum']}")
    if "const" in schema and value != schema["const"]:
        out.append(f"{path}: cần {schema['const']!r}")
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        out.append(f"{path}: không khớp {schema['pattern']}")
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                out.append(f"{path}: thiếu {k}")
        for k, sub in schema.get("properties", {}).items():
            if k in value:
                out += _errors(value[k], sub, f"{path}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            out += _errors(v, schema["items"], f"{path}[{i}]")
    return out


def _walk_refs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref":
                yield v
            else:
                yield from _walk_refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_refs(v)


def test_contract_la_openapi_31_va_moi_ref_deu_ton_tai():
    assert SPEC["openapi"] == "3.1.0"
    for ref in _walk_refs(SPEC):
        kind, name = ref.split("/")[-2:]
        assert name in SPEC["components"][kind], ref


def test_moi_thao_tac_co_operation_id_khong_trung_va_tra_loi_postgrest():
    ids = []
    for path, ops in SPEC["paths"].items():
        assert path.startswith("/api/v1/rest/"), path
        for method, op in ops.items():
            ids.append(op["operationId"])
            if method == "post":
                # RPC PostgREST: tên hàm khớp operationId, lỗi theo dạng LoiPostgrest
                assert path.endswith("/rpc/" + op["operationId"]), path
                for code, resp in op["responses"].items():
                    if code != "200":
                        assert resp == {"$ref": "#/components/responses/Loi"}, (path, code)
    assert len(ids) == len(set(ids))


def test_rpc_tao_moi_nhan_khoa_idempotency_va_khong_nhan_tenant():
    for path, ops in SPEC["paths"].items():
        for op in ops.values():
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
            props = body.get("properties", {})
            assert not any("tenant" in k for k in props), path
            if op["operationId"] in {"tao_phien_ban", "them_ban_ve", "them_nhan_xet"}:
                assert "p_idempotency_key" in props, path


def test_du_bo_mon_ke_hoach_yeu_cau():
    assert SCHEMAS["MaBoMon"]["enum"] == ["kien_truc", "ket_cau", "mep", "pccc"]


@pytest.mark.parametrize(
    ("tep", "schema"),
    [
        ("bo-mon.json", {"type": "array", "items": {"$ref": "#/components/schemas/BoMon"}}),
        ("v1-ds-ban-ve.json", {"$ref": "#/components/schemas/DanhSachBanVe"}),
        ("v2-ds-ban-ve.json", {"$ref": "#/components/schemas/DanhSachBanVe"}),
        ("ds-phien-ban.json", {"type": "array", "items": {"$ref": "#/components/schemas/PhienBanDayDu"}}),
        ("nhan-xet.json", {"type": "array", "items": {"$ref": "#/components/schemas/NhanXet"}}),
        ("v1-trang-thai.json", {"$ref": "#/components/schemas/TrangThaiThamDinh"}),
        ("v2-trang-thai.json", {"$ref": "#/components/schemas/TrangThaiThamDinh"}),
    ],
)
def test_fixture_khop_schema(tep, schema):
    data = json.loads((FIXTURES / tep).read_text(encoding="utf-8"))
    assert _errors(data, schema) == []


def test_bo_kiem_schema_bat_duoc_loi():
    bad = {"id": "x", "bo_mon": "dien", "ten": 3}
    errs = _errors(bad, {"$ref": "#/components/schemas/BanVe"})
    assert any("thiếu phien_ban_id" in e for e in errs)
    assert any("'dien'" in e for e in errs)
    assert any(".ten" in e for e in errs)


def test_kich_ban_demo_v1_thieu_ket_cau_v2_du():
    v1 = json.loads((FIXTURES / "v1-trang-thai.json").read_text(encoding="utf-8"))
    v2 = json.loads((FIXTURES / "v2-trang-thai.json").read_text(encoding="utf-8"))
    assert v1["thieu_bo_mon"] == ["ket_cau"] and v1["ket_luan"] == "khong_dat"
    assert v2["thieu_bo_mon"] == [] and v2["ket_luan"] == "dat"
    assert v2["so_phien_ban"] == v1["so_phien_ban"] + 1

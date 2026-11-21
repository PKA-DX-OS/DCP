# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""D-P0-03: hợp đồng API D & H (contracts/dh/*.yaml) đọc được, tự nhất quán, theo quy ước chung,
và mỗi thao tác có mock khớp schema phản hồi. Bộ kiểm schema tối giản để không thêm phụ thuộc."""

import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DH = ROOT / "contracts" / "dh"
MOCKS = DH / "mocks"
FILES = sorted(DH.glob("*.yaml"))
SPECS = {p.stem: yaml.safe_load(p.read_text(encoding="utf-8")) for p in FILES}
METHODS = ("get", "post", "put", "patch", "delete")

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


def _resolve(spec: dict, ref: str) -> dict:
    assert ref.startswith("#/"), ref
    node = spec
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _type_ok(value, t: str) -> bool:
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[t])


def _errors(spec: dict, value, schema: dict, path: str = "$") -> list[str]:
    if "$ref" in schema:
        return _errors(spec, value, _resolve(spec, schema["$ref"]), path)
    errs: list[str] = []
    if "allOf" in schema:
        for s in schema["allOf"]:
            errs += _errors(spec, value, s, path)
    if "oneOf" in schema:
        ok = [s for s in schema["oneOf"] if not _errors(spec, value, s, path)]
        if len(ok) != 1:
            errs.append(f"{path}: khớp {len(ok)} nhánh oneOf")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(value, t) for t in types):
            return errs + [f"{path}: cần {types}, có {type(value).__name__}"]
    if value is None:
        return errs
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} không thuộc enum")
    if "const" in schema and value != schema["const"]:
        errs.append(f"{path}: cần {schema['const']!r}")
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errs.append(f"{path}: {value!r} sai pattern")
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 10**9):
            errs.append(f"{path}: độ dài sai")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append(f"{path}: nhỏ hơn {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errs.append(f"{path}: lớn hơn {schema['maximum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 10**9):
            errs.append(f"{path}: số phần tử sai")
        if "items" in schema:
            for i, v in enumerate(value):
                errs += _errors(spec, v, schema["items"], f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{path}: thiếu {k}")
        if schema.get("additionalProperties") is False:
            for k in value:
                if k not in props:
                    errs.append(f"{path}: thừa {k}")
        for k, v in value.items():
            if k in props:
                errs += _errors(spec, v, props[k], f"{path}.{k}")
    return errs


def _operations(spec: dict):
    for path, item in spec["paths"].items():
        for method in METHODS:
            if method in item:
                yield path, method, item[method]


def _refs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref":
                yield v
            else:
                yield from _refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _refs(v)


def _param(spec: dict, p: dict) -> dict:
    return _resolve(spec, p["$ref"]) if "$ref" in p else p


def test_du_bay_hop_dong():
    assert set(SPECS) == {"automation", "catalog", "data-quality", "lineage", "mdm", "ocr", "search"}


@pytest.mark.parametrize("name", sorted(SPECS))
def test_khung_chung(name):
    spec = SPECS[name]
    assert spec["openapi"].startswith("3.1")
    assert re.match(r"^1\.\d+\.\d+$", spec["info"]["version"]), "v1 dùng phiên bản 1.x.y"
    assert spec["info"]["license"]["identifier"] == "AGPL-3.0-or-later"
    assert spec["security"] == [{"bearer": []}]
    assert spec["components"]["securitySchemes"]["bearer"]["scheme"] == "bearer"
    loi = spec["components"]["schemas"]["Loi"]
    assert set(loi["required"]) == {"code", "message"}
    for ref in _refs(spec):
        _resolve(spec, ref)  # ném KeyError nếu $ref treo


@pytest.mark.parametrize("name", sorted(SPECS))
def test_quy_uoc_duong_dan_va_thao_tac(name):
    spec = SPECS[name]
    for path, method, op in _operations(spec):
        assert path.startswith("/api/v1/"), path
        assert op.get("operationId"), f"{method} {path} thiếu operationId"
        assert op.get("tags"), f"{method} {path} thiếu tags"
        params = [_param(spec, p) for p in op.get("parameters", [])]
        assert all(p["name"] != "tenant" for p in params), "tenant lấy từ JWT, không nhận tham số"
        if method == "post":
            assert any(p["in"] == "header" and p["name"] == "Idempotency-Key" for p in params), \
                f"POST {path} cần header Idempotency-Key"
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
            if body:
                body = _resolve(spec, body["$ref"]) if "$ref" in body else body
                assert "tenant" not in body.get("properties", {})
        for code, resp in op["responses"].items():
            resp = _resolve(spec, resp["$ref"]) if "$ref" in resp else resp
            if int(code) >= 400:
                schema = resp["content"]["application/json"]["schema"]
                assert schema == {"$ref": "#/components/schemas/Loi"}, f"{method} {path} {code} phải trả Loi"


def test_operation_id_khong_trung_giua_cac_tep():
    ids = [op["operationId"] for spec in SPECS.values() for _, _, op in _operations(spec)]
    assert len(ids) == len(set(ids)), sorted(i for i in ids if ids.count(i) > 1)


@pytest.mark.parametrize("name", sorted(SPECS))
def test_moi_thao_tac_co_mock_khop_schema(name):
    spec = SPECS[name]
    mocks = json.loads((MOCKS / f"{name}.json").read_text(encoding="utf-8"))
    ops = {op["operationId"]: op for _, _, op in _operations(spec)}
    assert set(mocks) == set(ops), f"mock thừa/thiếu: {set(mocks) ^ set(ops)}"
    for op_id, mock in mocks.items():
        resp = ops[op_id]["responses"][str(mock["status"])]
        resp = _resolve(spec, resp["$ref"]) if "$ref" in resp else resp
        schema = resp["content"]["application/json"]["schema"]
        errs = _errors(spec, mock["body"], schema)
        assert not errs, f"{name}.{op_id}: {errs[:5]}"


def _strings(node, key=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v, key)
    elif isinstance(node, str):
        yield key, node


@pytest.mark.parametrize("name", sorted(SPECS))
def test_mock_khong_co_du_lieu_ca_nhan_that(name):
    mocks = json.loads((MOCKS / f"{name}.json").read_text(encoding="utf-8"))
    for key, s in _strings(mocks):
        assert not re.fullmatch(r"(0|\+84)[0-9]{9}", s), f"{name}: {key} giống số điện thoại thật"
        if "cccd" in key:
            assert "*" in s, f"{name}: {key} phải ở dạng che"
        if "dien_thoai" in key:
            assert "*" in s, f"{name}: {key} phải ở dạng che"


def test_che_du_lieu_ca_nhan_trong_schema():
    """Không schema phản hồi nào có trường CCCD/điện thoại đầy đủ; chỉ có dạng *_mask."""
    def ten_truong(node):
        if isinstance(node, dict):
            yield from node.get("properties", {}).keys()
            for v in node.values():
                yield from ten_truong(v)
        elif isinstance(node, list):
            for v in node:
                yield from ten_truong(v)

    for name, spec in SPECS.items():
        truong = set(ten_truong(spec["components"]["schemas"]))
        for cot in ("cccd", "cccd_hmac", "dien_thoai", "so_dien_thoai"):
            assert cot not in truong, f"{name} lộ trường {cot}"

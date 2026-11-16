# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_ACCOUNTS_FILE = ROOT / "secrets" / "demo-accounts.txt"
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8080")

REQUIRED_DOC_LOAI = [
    "don",
    "giay_to_dat",
    "ban_ve_mat_bang",
    "ban_ve_tang",
    "ban_ve_mong",
    "cam_ket_an_toan",
]


def make_pdf(tag: str) -> bytes:
    """PDF tối thiểu, nội dung khác nhau để không trùng SHA-256."""
    return (
        f"%PDF-1.4\n% {tag}\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
    ).encode()


def normalize_payload(payload: dict) -> dict:
    """Chuẩn hóa dữ liệu test để vượt qua kiểm tra nghiệp vụ L7."""
    data = dict(payload)
    cccd = re.sub(r"\D", "", str(data.get("cccd") or ""))
    if len(cccd) < 12:
        cccd = (cccd + "0" * 12)[:12]
    data["cccd"] = cccd[:12]
    if len(str(data.get("ho_ten") or "").strip()) < 3:
        data["ho_ten"] = "Nguyen Van Test"
    if not str(data.get("thua_dat") or "").strip():
        data["thua_dat"] = "Thua 1 To 1"
    try:
        floors = int(data.get("so_tang") or 1)
    except (TypeError, ValueError):
        floors = 1
    data["so_tang"] = min(max(floors, 1), 5)
    try:
        area = float(data.get("dien_tich_san_m2") or 100.0)
    except (TypeError, ValueError):
        area = 100.0
    data["dien_tich_san_m2"] = min(max(area, 1.0), 500.0)
    return data


def _doc_metadata(loai: str, payload: dict) -> dict:
    if loai == "don":
        return {"ho_ten": payload["ho_ten"], "cccd": payload["cccd"]}
    if loai == "giay_to_dat":
        return {
            "so_thua": payload["thua_dat"],
            "dien_tich": payload["dien_tich_san_m2"],
        }
    if loai == "ban_ve_tang":
        return {"so_tang": payload["so_tang"]}
    return {}


def _tep_entry(loai: str, file_id: str, payload: dict) -> dict:
    entry = {
        "file_id": file_id,
        "loai": loai,
        "thong_tin": _doc_metadata(loai, payload),
        "ngay_cap": None,
        "ngay_het_han": None,
    }
    if loai == "giay_to_dat":
        entry["ngay_cap"] = "2020-01-01"
        entry["ngay_het_han"] = "2035-01-01"
    return entry


def upload_document(token: str, ho_so_id: str, loai: str, tag: str, client: httpx.Client | None = None) -> str:
    owns_client = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        resp = client.post(
            f"{GATEWAY_URL}/api/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (f"{loai}.pdf", make_pdf(tag), "application/pdf")},
            data={"object_type": "draft.ho_so", "object_id": ho_so_id},
        )
        assert resp.status_code == 201, f"Upload {loai} thất bại: {resp.status_code} {resp.text}"
        return resp.json()["file_id"]
    finally:
        if owns_client:
            client.close()


async def upload_document_async(
    client: httpx.AsyncClient, token: str, ho_so_id: str, loai: str, tag: str
) -> str:
    resp = await client.post(
        f"{GATEWAY_URL}/api/v1/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (f"{loai}.pdf", make_pdf(tag), "application/pdf")},
        data={"object_type": "draft.ho_so", "object_id": ho_so_id},
    )
    assert resp.status_code == 201, f"Upload {loai} thất bại: {resp.status_code} {resp.text}"
    return resp.json()["file_id"]


def build_tep(token: str, ho_so_id: str, payload: dict, tag_prefix: str, client: httpx.Client | None = None) -> list:
    tep = []
    for loai in REQUIRED_DOC_LOAI:
        file_id = upload_document(token, ho_so_id, loai, f"{tag_prefix}-{loai}", client=client)
        tep.append(_tep_entry(loai, file_id, payload))
    return tep


def submit_dossier(
    token: str,
    payload: dict,
    tag_prefix: str = "test",
    client: httpx.Client | None = None,
) -> httpx.Response:
    """Nộp hồ sơ kèm đủ 6 giấy bắt buộc (P1)."""
    data = normalize_payload(payload)
    ho_so_id = str(uuid.uuid4())
    owns_client = client is None
    client = client or httpx.Client(timeout=60.0)
    try:
        tep = build_tep(token, ho_so_id, data, f"{tag_prefix}-{ho_so_id[:8]}", client=client)
        body = dict(data)
        body["p_ho_so_id"] = ho_so_id
        body["p_tep"] = tep
        return client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/nop_ho_so",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
    finally:
        if owns_client:
            client.close()


async def submit_dossier_async(
    client: httpx.AsyncClient,
    token: str,
    payload: dict,
    tag_prefix: str = "test",
) -> httpx.Response:
    data = normalize_payload(payload)
    ho_so_id = str(uuid.uuid4())
    tep = []
    for loai in REQUIRED_DOC_LOAI:
        file_id = await upload_document_async(client, token, ho_so_id, loai, f"{tag_prefix}-{ho_so_id[:8]}-{loai}")
        tep.append(_tep_entry(loai, file_id, data))
    body = dict(data)
    body["p_ho_so_id"] = ho_so_id
    body["p_tep"] = tep
    return await client.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/nop_ho_so",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )


def load_demo_accounts() -> dict:
    accounts = {}
    if DEMO_ACCOUNTS_FILE.exists():
        for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(":")
                accounts[parts[0]] = parts[1]
    return accounts


_ACCOUNTS = load_demo_accounts()
_TOKEN_CACHE = {}


def get_token(username: str, force_fresh: bool = False) -> str:
    if not force_fresh and username in _TOKEN_CACHE:
        token = _TOKEN_CACHE[username]
        try:
            raw = token.split(".")[1]
            raw += "=" * (-len(raw) % 4)
            payload = json.loads(base64.urlsafe_b64decode(raw))
            if payload.get("exp", 0) > time.time() + 120:  # chừa sai lệch đồng hồ máy chủ/container
                return token
        except Exception:
            pass

    password = _ACCOUNTS.get(username, "Demo@123456")
    data = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": "dx-test",
        "username": username,
        "password": password,
    }).encode()

    token_url = f"{GATEWAY_URL}/auth/realms/dxos/protocol/openid-connect/token"
    req = urllib.request.Request(token_url, data=data)
    with urllib.request.urlopen(req, timeout=5) as resp:
        token = json.loads(resp.read().decode())["access_token"]
        _TOKEN_CACHE[username] = token
        return token

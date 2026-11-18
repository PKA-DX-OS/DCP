# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Fixture/helper dùng chung cho test tích hợp.

Bản rút gọn: re-export từ `_auth`/`_ho_so` để các test A11–A13 không phụ thuộc
bản conftest đầy đủ của C14.
"""

import uuid
from pathlib import Path

import httpx

from tests.integration._auth import GATEWAY_URL, ROOT, get_token
from tests.integration._ho_so import (
    REQUIRED_DOC_LOAI,
    _tep_entry,
    make_pdf,
    normalize_payload,
    submit_dossier,
)

DEMO_ACCOUNTS_FILE = ROOT / "secrets" / "demo-accounts.txt"


def load_demo_accounts() -> dict:
    accounts = {}
    if DEMO_ACCOUNTS_FILE.exists():
        for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(":")
                accounts[parts[0]] = parts[1]
    return accounts


def get_sensor_token(tenant: str = "phuong-a") -> str:
    secret_file = ROOT / "secrets" / f"sensor-{tenant}-secret.txt"
    if secret_file.exists():
        secret = secret_file.read_text(encoding="utf-8").strip()
    else:
        secret = (
            "dxos_dev_sensor_phuong_a_secret_2026"
            if tenant == "phuong-a"
            else "dxos_dev_sensor_phuong_b_secret_2026"
        )

    token_url = f"{GATEWAY_URL}/auth/realms/dxos/protocol/openid-connect/token"
    client_id = f"dxos-sensor-{tenant}"
    with httpx.Client(timeout=5.0) as client:
        resp = client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": secret,
            },
        )
        assert resp.status_code == 200, f"Lỗi lấy token sensor {client_id}: {resp.text}"
        return resp.json()["access_token"]


async def upload_document_async(
    client: httpx.AsyncClient,
    token: str,
    ho_so_id: str,
    loai: str,
    tag: str,
) -> str:
    resp = await client.post(
        f"{GATEWAY_URL}/api/v1/files",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (f"{loai}.pdf", make_pdf(tag), "application/pdf")},
        data={"object_type": "draft.ho_so", "object_id": ho_so_id},
    )
    assert resp.status_code == 201, f"Tải {loai} thất bại: {resp.status_code} {resp.text}"
    return resp.json()["file_id"]


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
        file_id = await upload_document_async(
            client, token, ho_so_id, loai, f"{tag_prefix}-{ho_so_id[:8]}-{loai}"
        )
        tep.append(_tep_entry(loai, file_id, data))
    body = dict(data)
    body["p_ho_so_id"] = ho_so_id
    body["p_tep"] = tep
    return await client.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/nop_ho_so",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )

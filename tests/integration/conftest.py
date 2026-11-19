# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Fixture dùng chung cho test tích hợp (C14).

- `tai_khoan`: tài khoản demo đọc từ secrets/demo-accounts.txt (do seed sinh). Thiếu tệp thì
  test fail ngay với hướng dẫn, không đoán mật khẩu.
- `token`: hàm lấy access token theo username (có cache trong `_auth`).
- `tenant`: địa bàn mặc định của test (`DX_TEST_TENANT`, mặc định phuong-a).
- `don_dep`: đăng ký việc dọn dẹp; chạy ngược thứ tự đăng ký khi test kết thúc, kể cả khi test fail.
- `ho_so_moi`: nộp một hồ sơ mới của cdt.minh với đủ giấy tờ bắt buộc.

Helper (nộp hồ sơ, đi quy trình, SQL) nằm ở `_auth.py`, `_ho_so.py`, `_iot.py`; tên ở đây được
xuất lại để test cũ viết `from tests.integration.conftest import get_token, submit_dossier` vẫn chạy.
Không có bí mật nào viết cứng trong tệp này.
"""

import os
import uuid
from typing import Callable

import httpx
import pytest

from tests.integration._auth import DEMO_ACCOUNTS_FILE, GATEWAY_URL, ROOT, get_token
from tests.integration._ho_so import (
    REQUIRED_DOC_LOAI,
    _tep_entry,
    build_tep,
    complete_task,
    flowable,
    make_pdf,
    normalize_payload,
    run_psql,
    run_sql,
    start_cap_phep,
    start_process,
    sub_of,
    submit_dossier,
    upload_document,
    wait_task,
)
from tests.integration._iot import get_sensor_token

__all__ = [
    "DEMO_ACCOUNTS_FILE", "GATEWAY_URL", "REQUIRED_DOC_LOAI", "ROOT",
    "build_tep", "complete_task", "flowable", "get_sensor_token", "get_token", "load_demo_accounts",
    "make_pdf", "normalize_payload", "run_psql", "run_sql", "start_cap_phep", "start_process", "sub_of",
    "submit_dossier", "submit_dossier_async", "upload_document", "upload_document_async", "wait_task",
]


def load_demo_accounts() -> dict:
    """Đọc secrets/demo-accounts.txt thành {username: mật khẩu}; thiếu tệp thì trả dict rỗng."""
    accounts = {}
    if DEMO_ACCOUNTS_FILE.exists():
        for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(":")
                accounts[parts[0]] = parts[1]
    return accounts


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


@pytest.fixture(scope="session")
def tai_khoan() -> dict[str, str]:
    if not DEMO_ACCOUNTS_FILE.exists():
        pytest.fail(f"Thiếu {DEMO_ACCOUNTS_FILE.relative_to(ROOT)}: chạy `dx up` với DEMO_MODE=true để seed sinh tài khoản demo")
    ds = {}
    for line in DEMO_ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 2 and parts[0] and not parts[0].startswith("#"):
            ds[parts[0]] = parts[1]
    if not ds:
        pytest.fail(f"{DEMO_ACCOUNTS_FILE.relative_to(ROOT)} rỗng")
    return ds


@pytest.fixture
def token(tai_khoan) -> Callable[[str], str]:
    def lay(username: str) -> str:
        if username not in tai_khoan:
            pytest.fail(f"Không có tài khoản demo {username}")
        return get_token(username)
    return lay


@pytest.fixture(scope="session")
def tenant() -> str:
    return os.getenv("DX_TEST_TENANT", "phuong-a")


@pytest.fixture
def don_dep():
    viec: list[Callable[[], object]] = []
    yield viec.append
    loi = []
    for fn in reversed(viec):
        try:
            fn()
        except Exception as e:  # dọn tiếp các việc sau, báo lỗi ở cuối
            loi.append(repr(e))
    if loi:
        pytest.fail("Dọn dẹp lỗi: " + "; ".join(loi))


@pytest.fixture
def ho_so_moi(token) -> dict:
    tag = uuid.uuid4().hex[:6]
    resp = submit_dossier(token("cdt.minh"), {
        "ho_ten": f"Nguyen Van Fixture {tag}",
        "cccd": "001099007777",
        "dien_thoai": "0907777777",
        "dia_chi_cong_trinh": f"So {tag} Duong Fixture",
        "thua_dat": f"Thua {tag}",
        "so_tang": 2,
        "dien_tich_san_m2": 120.0,
        "khu_quan_ly_kien_truc": True,
    }, tag_prefix="fixture")
    assert resp.status_code == 200, f"Nộp hồ sơ fixture thất bại: {resp.status_code} {resp.text}"
    return resp.json()

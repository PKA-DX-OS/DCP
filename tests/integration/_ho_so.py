# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Helper dùng chung cho test tích hợp app cấp phép (B14, B15).

Tách khỏi `conftest.py` (C14) giống `_auth.py`: các test hồ sơ và quy trình
không phải chờ C14. Mỗi test tự nộp hồ sơ mới, không dựa vào dữ liệu do test
khác tạo, nên chạy riêng lẻ hay đảo thứ tự đều được.
"""

import base64
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import httpx

from tests.integration._auth import GATEWAY_URL, ROOT, get_token

__all__ = [
    "GATEWAY_URL",
    "REQUIRED_DOC_LOAI",
    "build_tep",
    "cap_phep_den_buoc_duyet",
    "complete_task",
    "flowable",
    "get_token",
    "make_pdf",
    "normalize_payload",
    "run_psql",
    "run_sql",
    "start_cap_phep",
    "start_process",
    "sub_of",
    "submit_dossier",
    "upload_document",
    "wait_task",
]

REQUIRED_DOC_LOAI = [
    "don",
    "giay_to_dat",
    "ban_ve_mat_bang",
    "ban_ve_tang",
    "ban_ve_mong",
    "cam_ket_an_toan",
]

FLOWABLE_HOST_URL = os.getenv("FLOWABLE_HOST_URL", "http://localhost:8082/flowable-rest")


# --- CSDL ---------------------------------------------------------------

def run_psql(sql: str, user: str = "postgres") -> subprocess.CompletedProcess:
    """Chạy SQL trong container dxos-postgres; dừng ở lỗi đầu tiên."""
    cmd = [
        "docker", "exec", "dxos-postgres", "psql", "-U", user, "-d", "dxos",
        "-v", "ON_ERROR_STOP=1", "-t", "-A", "-c", sql,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def run_sql(sql: str) -> str:
    """Chạy SQL bằng superuser, trả stdout; lỗi SQL thì test fail ngay."""
    res = run_psql(sql)
    assert res.returncode == 0, f"SQL lỗi: {res.stderr.strip()}\n{sql}"
    return res.stdout.strip()


# --- Token --------------------------------------------------------------

def sub_of(token: str) -> str:
    raw = token.split(".")[1]
    raw += "=" * (-len(raw) % 4)
    return json.loads(base64.urlsafe_b64decode(raw))["sub"]


# --- Nộp hồ sơ ----------------------------------------------------------

def make_pdf(tag: str) -> bytes:
    """PDF tối thiểu, nội dung khác nhau để không trùng SHA-256."""
    return (
        f"%PDF-1.4\n% {tag}\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
    ).encode()


def normalize_payload(payload: dict) -> dict:
    """Đưa dữ liệu test về dạng qua được kiểm tra nghiệp vụ của nop_ho_so."""
    data = dict(payload)
    cccd = re.sub(r"\D", "", str(data.get("cccd") or ""))
    data["cccd"] = (cccd + "0" * 12)[:12]
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
        return {"so_thua": payload["thua_dat"], "dien_tich": payload["dien_tich_san_m2"]}
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
    owns = client is None
    client = client or httpx.Client(timeout=30.0)
    try:
        resp = client.post(
            f"{GATEWAY_URL}/api/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (f"{loai}.pdf", make_pdf(tag), "application/pdf")},
            data={"object_type": "draft.ho_so", "object_id": ho_so_id},
        )
        assert resp.status_code == 201, f"Tải {loai} thất bại: {resp.status_code} {resp.text}"
        return resp.json()["file_id"]
    finally:
        if owns:
            client.close()


def build_tep(token: str, ho_so_id: str, payload: dict, tag_prefix: str, client: httpx.Client | None = None) -> list:
    return [
        _tep_entry(loai, upload_document(token, ho_so_id, loai, f"{tag_prefix}-{loai}", client=client), payload)
        for loai in REQUIRED_DOC_LOAI
    ]


def submit_dossier(token: str, payload: dict, tag_prefix: str = "test", client: httpx.Client | None = None) -> httpx.Response:
    """Nộp hồ sơ kèm đủ 6 loại giấy bắt buộc qua RPC nop_ho_so."""
    data = normalize_payload(payload)
    ho_so_id = str(uuid.uuid4())
    owns = client is None
    client = client or httpx.Client(timeout=60.0)
    try:
        body = dict(data)
        body["p_ho_so_id"] = ho_so_id
        body["p_tep"] = build_tep(token, ho_so_id, data, f"{tag_prefix}-{ho_so_id[:8]}", client=client)
        return client.post(
            f"{GATEWAY_URL}/api/v1/rest/rpc/nop_ho_so",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
    finally:
        if owns:
            client.close()


# --- Quy trình ----------------------------------------------------------

def start_process(token: str, process_key: str, variables: dict, business_key: str | None = None) -> str:
    """Khởi động quy trình qua service flow (tenant lấy từ token), trả process id."""
    body = {"process_key": process_key, "variables": variables}
    if business_key:
        body["business_key"] = business_key
    resp = httpx.post(
        f"{GATEWAY_URL}/api/v1/flow/processes/start",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=15.0,
    )
    assert resp.status_code in (200, 201), f"Khởi động {process_key} thất bại: {resp.status_code} {resp.text}"
    return resp.json()["process_id"]


def start_cap_phep(token: str, ho_so: dict, extra: dict | None = None) -> str:
    """Khởi động quy trình cap-phep cho hồ sơ vừa nộp (như giao diện), trả process id.

    Nếu nop_ho_so đã khởi động quy trình (trả `process_instance_id`) thì dùng luôn.
    """
    if ho_so.get("process_instance_id"):
        return ho_so["process_instance_id"]
    variables = {
        "ho_so_id": ho_so["id"],
        "object_id": ho_so["id"],
        "ma_ho_so": ho_so["ma_ho_so"],
        "chu_dau_tu_sub": sub_of(token),
        "dia_chi_cong_trinh": ho_so.get("dia_chi_cong_trinh"),
        "trang_thai_ho_so": ho_so.get("trang_thai", "DA_NOP"),
        "do_uu_tien": "binh_thuong",
    }
    variables.update(extra or {})
    return start_process(token, "cap-phep", variables, business_key=ho_so["ma_ho_so"])


def wait_task(token: str, proc_id: str, task_def: str, tries: int = 15) -> dict:
    """Chờ task `task_def` của quy trình `proc_id` hiện trong danh sách việc của người dùng."""
    last = None
    for _ in range(tries):
        resp = httpx.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
        if resp.status_code == 200:
            body = resp.json()
            tasks = body.get("tasks", []) if isinstance(body, dict) else body
            last = [(t.get("taskDefinitionKey"), t.get("processInstanceId")) for t in tasks]
            for t in tasks:
                if t.get("processInstanceId") == proc_id and t.get("taskDefinitionKey") == task_def:
                    return t
        time.sleep(1)
    raise AssertionError(f"Không thấy {task_def} của quy trình {proc_id}; danh sách việc: {last}")


def complete_task(token: str, task_id: str, variables: dict, timeout: float = 20.0) -> httpx.Response:
    return httpx.post(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{task_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={"variables": variables},
        timeout=timeout,
    )


def cap_phep_den_buoc_duyet(cdt: str, payload: dict, tag_prefix: str) -> dict:
    """Nộp hồ sơ của `cdt` và đi hết các bước tới taskDuyetCapPhep.

    Một cửa (mc.thu) duyệt hợp lệ, lãnh đạo (ld.hoa) phân công td.binh, td.binh
    thẩm định đạt. Trả dict: ho_so, proc_id, task (taskDuyetCapPhep), tokens.
    """
    tok = {u: get_token(u) for u in (cdt, "mc.thu", "ld.hoa", "td.binh")}
    resp = submit_dossier(tok[cdt], payload, tag_prefix=tag_prefix)
    assert resp.status_code == 200, f"Nộp hồ sơ thất bại: {resp.status_code} {resp.text}"
    ho_so = resp.json()
    data = normalize_payload(payload)
    proc_id = start_cap_phep(tok[cdt], ho_so, {
        "dien_tich_san_m2": data["dien_tich_san_m2"],
        "khu_quan_ly_kien_truc": bool(data.get("khu_quan_ly_kien_truc")),
    })
    # Cổng gwPhanLoai: ≤ 100 m² và ngoài khu quản lý kiến trúc thì thẩm định rút gọn
    rut_gon = data["dien_tich_san_m2"] <= 100.0 and not data.get("khu_quan_ly_kien_truc")
    task_td = "taskThamDinhNhanh" if rut_gon else "taskThamDinh"

    buoc = [
        ("mc.thu", "taskKiemTraHopLe", {"hoSoHopLe": True}),
        ("ld.hoa", "taskPhanCong", {"nguoiThamDinh": sub_of(tok["td.binh"]), "lanhDaoPhanCong": sub_of(tok["ld.hoa"])}),
        ("td.binh", task_td, {"ketQuaThamDinh": "DAT", "noiDungThamDinh": "Bản vẽ đạt chuẩn"}),
    ]
    for user, task_def, variables in buoc:
        task = wait_task(tok[user], proc_id, task_def)
        r = complete_task(tok[user], task["id"], variables)
        assert r.status_code == 200, f"{user} hoàn thành {task_def} thất bại: {r.status_code} {r.text}"

    task = wait_task(tok["ld.hoa"], proc_id, "taskDuyetCapPhep")
    return {"ho_so": ho_so, "proc_id": proc_id, "task": task, "tokens": tok}


def _flowable_creds() -> tuple[str, str]:
    user = os.getenv("FLOWABLE_USER")
    pw = os.getenv("FLOWABLE_PASSWORD")
    env_file = Path(ROOT) / ".env"
    if (not user or not pw) and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if not user and line.startswith("FLOWABLE_USER="):
                user = line.split("=", 1)[1].strip()
            elif not pw and line.startswith("FLOWABLE_PASSWORD="):
                pw = line.split("=", 1)[1].strip()
    assert pw, "Thiếu FLOWABLE_PASSWORD (biến môi trường hoặc .env)"
    return user or "rest-admin", pw


def flowable() -> httpx.Client:
    """Client REST quản trị Flowable (cổng 127.0.0.1:8082 của stack) để kiểm tra trạng thái engine."""
    return httpx.Client(base_url=FLOWABLE_HOST_URL, auth=_flowable_creds(), timeout=15.0)

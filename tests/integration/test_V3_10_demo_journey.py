# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy V3-10: Kiểm tra toàn bộ chuỗi trạng thái quy trình nghiệp vụ 8 bước
qua REST/RPC và Flowable engine thật (không mock).
"""

import uuid
import httpx

from tests.integration.conftest import submit_dossier

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
GATEWAY_URL = "http://localhost:8080"


def load_demo_passwords() -> dict[str, str]:
    pw_file = ROOT / "secrets" / "demo-accounts.txt"
    passwords = {}
    if pw_file.exists():
        for line in pw_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and ":" in line:
                parts = line.split(":")
                passwords[parts[0]] = parts[1]
    return passwords


def get_token(username: str) -> str:
    pws = load_demo_passwords()
    pw = pws.get(username, "Demo@123456")
    resp = httpx.post(
        f"{GATEWAY_URL}/auth/realms/dxos/protocol/openid-connect/token",
        data={
            "client_id": "dx-test",
            "username": username,
            "password": pw,
            "grant_type": "password",
        },
        timeout=10.0,
    )
    assert resp.status_code == 200, f"Lỗi lấy token {username}: {resp.text}"
    return f"Bearer {resp.json()['access_token']}"


def test_V3_10_workflow_dossier_journey_state_progression():
    token_minh = get_token("cdt.minh")
    token_mc = get_token("mc.thu")
    token_hoa = get_token("ld.hoa")
    token_cuong = get_token("td.cuong")
    token_binh = get_token("td.binh")

    # Lấy sub của td.binh và ld.hoa
    import base64
    import json
    def parse_sub(tok):
        raw = tok.replace("Bearer ", "").split(".")[1]
        raw += "=" * (-len(raw) % 4)
        return json.loads(base64.urlsafe_b64decode(raw))["sub"]

    binh_sub = parse_sub(token_binh)
    hoa_sub = parse_sub(token_hoa)
    cuong_sub = parse_sub(token_cuong)

    # 1. cdt.minh nộp hồ sơ
    uid = uuid.uuid4().hex[:6]
    nop_resp = submit_dossier(
        token_minh.replace("Bearer ", ""),
        {
            "ho_ten": f"Nguyễn Văn Minh {uid}",
            "cccd": "001090123456",
            "dien_thoai": "0901234567",
            "dia_chi_cong_trinh": f"Số {uid} Đường Mẫu, Phường A (mẫu)",
            "thua_dat": f"Thửa {uid}",
            "so_tang": 2,
            "dien_tich_san_m2": 120.0,
            "khu_quan_ly_kien_truc": True,
        },
        tag_prefix="V3-10",
    )
    assert nop_resp.status_code == 200, f"Nộp hồ sơ thất bại: {nop_resp.text}"
    hs_data = nop_resp.json()
    ho_so_id = hs_data["id"]
    ma_ho_so = hs_data["ma_ho_so"]

    # Khởi động quy trình Flowable
    start_wf = httpx.post(
        f"{GATEWAY_URL}/api/v1/flow/processes/start",
        headers={"Authorization": token_minh, "Content-Type": "application/json"},
        json={
            "process_key": "cap-phep",
            "business_key": ma_ho_so,
            "variables": {
                "ma_ho_so": ma_ho_so,
                "ho_so_id": ho_so_id,
                "dien_tich_san_m2": 120.0,
                "khu_quan_ly_kien_truc": True,
            },
        },
        timeout=10.0,
    )
    assert start_wf.status_code == 200, f"Khởi động quy trình thất bại: {start_wf.text}"
    proc_id = start_wf.json()["process_id"]
    assert proc_id is not None

    # 2. mc.thu tiếp nhận
    tasks_mc = httpx.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": token_mc}, timeout=10.0).json().get("tasks", [])
    task_tn = next((t for t in tasks_mc if t.get("processInstanceId") == proc_id), None)
    assert task_tn is not None, f"Không tìm thấy taskKiemTraHopLe cho process {proc_id}"
    comp_tn = httpx.post(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{task_tn['id']}/complete",
        headers={"Authorization": token_mc, "Content-Type": "application/json"},
        json={"variables": {"hoSoHopLe": True}},
        timeout=10.0,
    )
    assert comp_tn.status_code == 200

    # 3. ld.hoa phân công cho td.binh
    tasks_ld = httpx.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": token_hoa}, timeout=10.0).json().get("tasks", [])
    task_pc = next((t for t in tasks_ld if t.get("processInstanceId") == proc_id), None)
    assert task_pc is not None
    comp_pc = httpx.post(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{task_pc['id']}/complete",
        headers={"Authorization": token_hoa, "Content-Type": "application/json"},
        json={"variables": {"nguoiThamDinh": binh_sub, "lanhDaoPhanCong": hoa_sub}},
        timeout=10.0,
    )
    assert comp_pc.status_code == 200

    # 4. td.cuong 403 -> xin truy cập khẩn -> ld.hoa duyệt -> 200
    chk_403 = httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/mo_ho_so",
        headers={"Authorization": token_cuong, "Content-Type": "application/json"},
        json={"p_id": ho_so_id},
        timeout=10.0,
    )
    assert chk_403.status_code == 403

    bg_req = httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/xin_truy_cap_khan",
        headers={"Authorization": token_cuong, "Content-Type": "application/json"},
        json={"p_ho_so_id": ho_so_id, "p_ly_do": "Hỗ trợ thẩm định khẩn cấp (mẫu)"},
        timeout=10.0,
    )
    assert bg_req.status_code == 200

    bg_appr = httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/duyet_truy_cap_khan",
        headers={"Authorization": token_hoa, "Content-Type": "application/json"},
        json={"p_ho_so_id": ho_so_id, "p_user_sub": cuong_sub, "p_dong_y": True},
        timeout=10.0,
    )
    assert bg_appr.status_code == 200

    chk_200 = httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/mo_ho_so",
        headers={"Authorization": token_cuong, "Content-Type": "application/json"},
        json={"p_id": ho_so_id},
        timeout=10.0,
    )
    assert chk_200.status_code == 200

    # 5. td.binh thẩm định
    tasks_td = httpx.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": token_binh}, timeout=10.0).json().get("tasks", [])
    task_td = next((t for t in tasks_td if t.get("processInstanceId") == proc_id), None)
    assert task_td is not None
    comp_td = httpx.post(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{task_td['id']}/complete",
        headers={"Authorization": token_binh, "Content-Type": "application/json"},
        json={"variables": {"ketQuaThamDinh": "DAT", "noiDungThamDinh": "Bản vẽ đạt chuẩn"}},
        timeout=10.0,
    )
    assert comp_td.status_code == 200

    # 6. ld.hoa phê duyệt -> DA_CAP
    tasks_appr = httpx.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": token_hoa}, timeout=10.0).json().get("tasks", [])
    task_duyet = next((t for t in tasks_appr if t.get("processInstanceId") == proc_id), None)
    assert task_duyet is not None
    comp_duyet = httpx.post(
        f"{GATEWAY_URL}/api/v1/flow/tasks/{task_duyet['id']}/complete",
        headers={"Authorization": token_hoa, "Content-Type": "application/json"},
        json={"variables": {"pheDuyet": True, "dongYCapPhep": True, "yKienPheDuyet": "Đồng ý cấp"}},
        timeout=10.0,
    )
    assert comp_duyet.status_code == 200

    # Ký số phát hành giấy phép
    sign_doc = httpx.post(
        f"{GATEWAY_URL}/api/v1/docs/sign",
        headers={"Authorization": token_hoa, "Content-Type": "application/json"},
        json={
            "doc_type": "giay_phep",
            "data": {"ma_ho_so": ma_ho_so, "chu_dau_tu": "Nguyễn Văn Minh", "dia_chi": "Phường A"},
        },
        timeout=10.0,
    )
    assert sign_doc.status_code == 201
    public_code = sign_doc.json()["public_code"]

    # 7. Cổng công khai tra cứu giấy phép
    chk_pub = httpx.get(f"{GATEWAY_URL}/kiem-tra/{public_code}", timeout=10.0)
    assert chk_pub.status_code == 200
    assert chk_pub.json().get("trang_thai") == "Hop_le"

    # 8. Rút đồng thuận và gửi DSAR
    grant_consent = httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/dong_y_du_lieu",
        headers={"Authorization": token_minh, "Content-Type": "application/json"},
        json={"p_purpose": "xu_ly_ho_so", "p_text_version": "v1.0"},
        timeout=10.0,
    )
    assert grant_consent.status_code == 200

    revoke_consent = httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/rut_dong_y_du_lieu",
        headers={"Authorization": token_minh, "Content-Type": "application/json"},
        json={"p_purpose": "xu_ly_ho_so"},
        timeout=10.0,
    )
    assert revoke_consent.status_code == 200

    dsar_req = httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/gui_yeu_cau_dsar",
        headers={"Authorization": token_minh, "Content-Type": "application/json"},
        json={"p_type": "access", "p_legal_basis_note": "Yêu cầu trích xuất dữ liệu"},
        timeout=10.0,
    )
    assert dsar_req.status_code == 200

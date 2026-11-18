# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""V3-10: luồng demo 6 chặng chạy hết trong một test, qua gateway và Flowable thật.

1. Chủ đầu tư nộp hồ sơ đủ giấy tờ.
2. Một cửa tiếp nhận.
3. Lãnh đạo phân công; thẩm định viên khác bị chặn 403, xin truy cập khẩn và được duyệt.
4. Thẩm định viên được phân công thẩm định đạt.
5. Lãnh đạo phê duyệt; hook ký số sinh giấy phép, hồ sơ sang DA_CAP.
6. Tra cứu công khai giấy phép; chủ đầu tư đồng ý, rút đồng ý dữ liệu và gửi yêu cầu DSAR.
"""

import time
import uuid

import httpx

from tests.integration._ho_so import (
    GATEWAY_URL, complete_task, get_token, run_sql, start_cap_phep, sub_of, submit_dossier, wait_task,
)


def _rpc(token: str, ten: str, body: dict) -> httpx.Response:
    return httpx.post(f"{GATEWAY_URL}/api/v1/rest/rpc/{ten}",
                      headers={"Authorization": f"Bearer {token}"}, json=body, timeout=15.0)


def test_V3_10_workflow_dossier_journey_state_progression():
    tok = {u: get_token(u) for u in ("cdt.minh", "mc.thu", "ld.hoa", "td.binh", "td.cuong")}

    def trang_thai(hs_id: str) -> str:
        return run_sql(f"SELECT trang_thai FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")

    # Chặng 1: nộp hồ sơ
    uid = uuid.uuid4().hex[:6]
    r = submit_dossier(tok["cdt.minh"], {
        "ho_ten": f"Nguyễn Văn Minh {uid}",
        "cccd": "001090123456",
        "dien_thoai": "0901234567",
        "dia_chi_cong_trinh": f"Số {uid} Đường Mẫu, Phường A",
        "thua_dat": f"Thửa {uid}",
        "so_tang": 2,
        "dien_tich_san_m2": 120.0,
        "khu_quan_ly_kien_truc": True,
    }, tag_prefix="V3-10")
    assert r.status_code == 200, f"Chặng 1 nộp hồ sơ thất bại: {r.text}"
    ho_so = r.json()
    hs_id = ho_so["id"]
    proc_id = start_cap_phep(tok["cdt.minh"], ho_so, {"dien_tich_san_m2": 120.0, "khu_quan_ly_kien_truc": True})

    # Chặng 2: một cửa tiếp nhận
    t = wait_task(tok["mc.thu"], proc_id, "taskKiemTraHopLe")
    r = complete_task(tok["mc.thu"], t["id"], {"hoSoHopLe": True})
    assert r.status_code == 200, f"Chặng 2 tiếp nhận thất bại: {r.text}"

    # Chặng 3: phân công td.binh; td.cuong bị chặn, xin truy cập khẩn, lãnh đạo duyệt
    t = wait_task(tok["ld.hoa"], proc_id, "taskPhanCong")
    r = complete_task(tok["ld.hoa"], t["id"], {"nguoiThamDinh": sub_of(tok["td.binh"]), "lanhDaoPhanCong": sub_of(tok["ld.hoa"])})
    assert r.status_code == 200, f"Chặng 3 phân công thất bại: {r.text}"
    assert _rpc(tok["td.cuong"], "mo_ho_so", {"p_id": hs_id}).status_code == 403
    r = _rpc(tok["td.cuong"], "xin_truy_cap_khan", {"p_ho_so_id": hs_id, "p_ly_do": "Hỗ trợ thẩm định khẩn cấp"})
    assert r.status_code == 200, r.text
    r = _rpc(tok["ld.hoa"], "duyet_truy_cap_khan", {"p_ho_so_id": hs_id, "p_user_sub": sub_of(tok["td.cuong"]), "p_dong_y": True})
    assert r.status_code == 200, r.text
    assert _rpc(tok["td.cuong"], "mo_ho_so", {"p_id": hs_id}).status_code == 200

    # Chặng 4: thẩm định
    t = wait_task(tok["td.binh"], proc_id, "taskThamDinh")
    r = complete_task(tok["td.binh"], t["id"], {"ketQuaThamDinh": "DAT", "noiDungThamDinh": "Bản vẽ đạt chuẩn"})
    assert r.status_code == 200, f"Chặng 4 thẩm định thất bại: {r.text}"

    # Chặng 5: phê duyệt, hook ký số và cấp phép
    t = wait_task(tok["ld.hoa"], proc_id, "taskDuyetCapPhep")
    r = complete_task(tok["ld.hoa"], t["id"], {"dongYCapPhep": True, "pheDuyet": True, "yKienPheDuyet": "Đồng ý cấp"})
    assert r.status_code == 200, f"Chặng 5 phê duyệt thất bại: {r.text}"
    for _ in range(10):
        if trang_thai(hs_id) == "DA_CAP":
            break
        time.sleep(1)
    assert trang_thai(hs_id) == "DA_CAP", f"Hồ sơ phải sang DA_CAP, đang là {trang_thai(hs_id)}"

    # Chặng 6: tra cứu công khai và quyền dữ liệu của chủ đầu tư
    r = _rpc(tok["cdt.minh"], "thong_tin_giay_phep", {"p_ho_so_id": hs_id})
    assert r.status_code == 200, r.text
    ma = r.json()["ma_cong_khai"]
    pub = httpx.get(f"{GATEWAY_URL}/kiem-tra/{ma}", headers={"Accept": "application/json"}, timeout=10.0)
    assert pub.status_code == 200 and pub.json().get("trang_thai") == "Hop_le", pub.text

    assert _rpc(tok["cdt.minh"], "dong_y_du_lieu", {"p_purpose": "xu_ly_ho_so", "p_text_version": "v1.0"}).status_code == 200
    assert _rpc(tok["cdt.minh"], "rut_dong_y_du_lieu", {"p_purpose": "xu_ly_ho_so"}).status_code == 200
    r = _rpc(tok["cdt.minh"], "gui_yeu_cau_dsar", {"p_type": "access", "p_legal_basis_note": "Yêu cầu trích xuất dữ liệu"})
    assert r.status_code == 200, r.text

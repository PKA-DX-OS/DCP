# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""FIX-V11-08: phiếu lập tay mở quy trình hau-kiem, việc vào hàng đợi trật tự xây dựng,
kết luận ở bước kiểm tra hiện trường được ghi vào phiếu."""

import httpx

from tests.integration._auth import get_token
from tests.integration._ho_so import GATEWAY_URL, complete_task, run_sql, start_process, wait_task
from tests.integration._iot import don_iot, ma_site, tao_cong_trinh

TTXD = "tt.khanh"


def _lap_phieu(token: str, site_id: str) -> str:
    ct_id = run_sql(f"SELECT id FROM app_cap_phep.cong_trinh WHERE ma_cong_trinh = '{site_id}';")
    r = httpx.post(
        f"{GATEWAY_URL}/api/v1/rest/rpc/lap_phieu_kiem_tra",
        headers={"Authorization": f"Bearer {token}"},
        json={"p_cong_trinh_id": ct_id, "p_ghi_chu": "Kiểm thử V11-08"},
        timeout=10.0,
    )
    assert r.status_code == 200, r.text
    return r.json()["phieu_id"]


def _phieu(phieu_id: str) -> list[str]:
    return run_sql(
        "SELECT COALESCE(process_instance_id, '') || '|' || trang_thai || '|' || COALESCE(ket_luan, '') "
        f"FROM app_cap_phep.phieu_kiem_tra WHERE id = '{phieu_id}';"
    ).split("|")


def test_V11_08_phieu_lap_tay_vao_hang_doi_va_ghi_ket_luan():
    token = get_token(TTXD)
    site_id = ma_site("CT-V11-08")
    tao_cong_trinh(site_id)
    try:
        phieu_id = _lap_phieu(token, site_id)
        proc_id = start_process(
            token, "hau-kiem", {"phieu_id": phieu_id, "site_id": site_id, "chi_so": "kiem_tra_dinh_ky"},
            business_key=phieu_id,
        )
        assert _phieu(phieu_id)[0] == proc_id, "Mở quy trình phải gắn process_instance_id vào phiếu"

        task = wait_task(token, proc_id, "taskKiemTraHienTruong")
        bien = {v["name"]: v["value"] for v in task.get("variables", [])}
        assert bien.get("site_id") == site_id, "Việc phải mang mã công trình để hiện trong hàng đợi"

        r = complete_task(token, task["id"], {"ketLuan": "vi_pham", "ghiChu": "Ồn quá giờ"})
        assert r.status_code == 200, r.text
        assert _phieu(phieu_id)[1:] == ["DANG_KIEM_TRA", "Có vi phạm"]
        assert run_sql(f"SELECT ghi_chu FROM app_cap_phep.phieu_kiem_tra WHERE id = '{phieu_id}';") == "Ồn quá giờ"

        task2 = wait_task(token, proc_id, "taskXuLyViPham")
        assert complete_task(token, task2["id"], {}).status_code == 200
        assert _phieu(phieu_id)[1] == "DA_XU_LY"
    finally:
        don_iot(site_id)


def test_V11_08_khong_gan_phieu_phuong_khac():
    token_a = get_token(TTXD)
    site_id = ma_site("CT-V11-08B")
    tao_cong_trinh(site_id)
    try:
        phieu_id = _lap_phieu(token_a, site_id)
        token_b = get_token("mc.phuongb")
        start_process(token_b, "hau-kiem", {"phieu_id": phieu_id}, business_key=phieu_id)
        assert _phieu(phieu_id)[0] == "", "Quy trình mở từ phường khác không được gắn vào phiếu"
    finally:
        don_iot(site_id)

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy cho lỗi Q-02:
- RLS cho phieu_kiem_tra, cong_trinh, giay_phep không được mở rộng cho mọi người trong phường.
- Chủ đầu tư không liên quan (cdtX) đọc các bảng gốc -> 0 dòng khi bảng đã có dữ liệu.
- Chủ công trình đọc được phiếu kiểm tra, công trình và giấy phép của chính mình -> 1 dòng.
- Cán bộ trật tự xây dựng cùng phường thấy phiếu kiểm tra.
- Cán bộ phường khác không thấy dữ liệu (0 dòng).
- Bổ sung view công khai cong_khai_giay_phep không lộ ho_so_id hay signed_doc_id.
"""

import subprocess
import uuid
import httpx
from tests.integration.conftest import GATEWAY_URL, get_token


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def test_Q02_rls_phieu_kiem_tra_cong_trinh_giay_phep():
    # 1. Chuẩn bị dữ liệu mẫu tại phuong-a: 1 hồ sơ, 1 giấy phép, 1 công trình, 1 phiếu kiểm tra
    ho_so_id = str(uuid.uuid4())
    gp_id = str(uuid.uuid4())
    ct_id = str(uuid.uuid4())
    pkt_id = str(uuid.uuid4())
    ma_hs = f"CP-Q02-{uuid.uuid4().hex[:6].upper()}"
    so_gp = f"GP-Q02-{uuid.uuid4().hex[:6].upper()}"
    ma_ct = f"CT-Q02-{uuid.uuid4().hex[:6].upper()}"
    cdt_minh_sub = run_sql("SELECT id::text FROM core.users_directory WHERE username = 'cdt.minh';")

    run_sql(f"""
    INSERT INTO app_cap_phep.ho_so (
        id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
        dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2,
        khu_quan_ly_kien_truc, trang_thai, buoc, han_tong_at
    ) VALUES (
        '{ho_so_id}'::uuid, 'phuong-a', '{ma_hs}', '{cdt_minh_sub}', 'Trần Văn Minh',
        '001099001234', '0901234567', 'Số 10 Phố Q02', 'Thửa 10 Tờ 10', 3, 150.0,
        true, 'DA_CAP', 'hoan_tat', now() + interval '30 days'
    );

    INSERT INTO app_cap_phep.giay_phep (
        id, tenant, ho_so_id, so_giay_phep, signed_doc_id, trang_thai, ngay_cap
    ) VALUES (
        '{gp_id}'::uuid, 'phuong-a', '{ho_so_id}'::uuid, '{so_gp}', gen_random_uuid(), 'hieu_luc', now()
    );

    INSERT INTO app_cap_phep.cong_trinh (
        id, tenant, giay_phep_id, ma_cong_trinh, entity_id, dia_chi, trang_thai_thi_cong
    ) VALUES (
        '{ct_id}'::uuid, 'phuong-a', '{gp_id}'::uuid, '{ma_ct}', 'urn:ngsi-ld:Site:{ma_ct}', 'Số 10 Phố Q02', 'DANG_THI_CONG'
    );

    INSERT INTO app_cap_phep.phieu_kiem_tra (
        id, tenant, cong_trinh_id, nguon, chi_so, gia_tri, nguong, trang_thai, ket_luan
    ) VALUES (
        '{pkt_id}'::uuid, 'phuong-a', '{ct_id}'::uuid, 'cam_bien', 'laeq_dba', 85.0, 70.0, 'CHO_KIEM_TRA', 'Chờ kiểm tra hiện trường'
    );
    """)

    # 2. Ca 1: Chủ đầu tư không có công trình/hồ sơ (cdt.lan ở phuong-a không sở hữu hồ sơ này)
    token_lan = get_token("cdt.lan")
    headers_lan = {"Authorization": f"Bearer {token_lan}"}
    with httpx.Client(base_url=GATEWAY_URL, timeout=5.0) as client:
        # Đọc phiếu kiểm tra
        r_pkt = client.get(f"/api/v1/rest/phieu_kiem_tra?id=eq.{pkt_id}", headers=headers_lan)
        assert r_pkt.status_code == 200
        assert len(r_pkt.json()) == 0, f"cdt.lan không được thấy phiếu kiểm tra của người khác, nhận: {r_pkt.json()}"

        # Đọc công trình
        r_ct = client.get(f"/api/v1/rest/cong_trinh?id=eq.{ct_id}", headers=headers_lan)
        assert r_ct.status_code == 200
        assert len(r_ct.json()) == 0, f"cdt.lan không được thấy công trình của người khác, nhận: {r_ct.json()}"

        # Đọc giấy phép
        r_gp = client.get(f"/api/v1/rest/giay_phep?id=eq.{gp_id}", headers=headers_lan)
        assert r_gp.status_code == 200
        assert len(r_gp.json()) == 0, f"cdt.lan không được thấy giấy phép gốc của người khác, nhận: {r_gp.json()}"

    # 3. Ca 2: Chủ công trình (cdt.minh) đọc được phiếu, công trình, giấy phép của mình
    token_minh = get_token("cdt.minh")
    headers_minh = {"Authorization": f"Bearer {token_minh}"}
    with httpx.Client(base_url=GATEWAY_URL, timeout=5.0) as client:
        r_pkt = client.get(f"/api/v1/rest/phieu_kiem_tra?id=eq.{pkt_id}", headers=headers_minh)
        assert r_pkt.status_code == 200 and len(r_pkt.json()) == 1, "Chủ công trình phải đọc được phiếu kiểm tra của mình"

        r_ct = client.get(f"/api/v1/rest/cong_trinh?id=eq.{ct_id}", headers=headers_minh)
        assert r_ct.status_code == 200 and len(r_ct.json()) == 1, "Chủ công trình phải đọc được công trình của mình"

        r_gp = client.get(f"/api/v1/rest/giay_phep?id=eq.{gp_id}", headers=headers_minh)
        assert r_gp.status_code == 200 and len(r_gp.json()) == 1, "Chủ công trình phải đọc được giấy phép của mình"

    # 4. Ca 3: Cán bộ TTXD cùng phường (tt.khanh) đọc được phiếu kiểm tra
    token_khanh = get_token("tt.khanh")
    headers_khanh = {"Authorization": f"Bearer {token_khanh}"}
    with httpx.Client(base_url=GATEWAY_URL, timeout=5.0) as client:
        r_pkt = client.get(f"/api/v1/rest/phieu_kiem_tra?id=eq.{pkt_id}", headers=headers_khanh)
        assert r_pkt.status_code == 200 and len(r_pkt.json()) == 1, "Cán bộ TTXD cùng phường phải thấy phiếu kiểm tra"

    # 5. Ca 4: Cán bộ phường khác (mc.phuongb) không đọc được dữ liệu phường A
    token_pb = get_token("mc.phuongb")
    headers_pb = {"Authorization": f"Bearer {token_pb}"}
    with httpx.Client(base_url=GATEWAY_URL, timeout=5.0) as client:
        r_pkt = client.get(f"/api/v1/rest/phieu_kiem_tra?id=eq.{pkt_id}", headers=headers_pb)
        assert r_pkt.status_code == 200 and len(r_pkt.json()) == 0, "Cán bộ phường khác không được đọc dữ liệu phường A"

        r_ct = client.get(f"/api/v1/rest/cong_trinh?id=eq.{ct_id}", headers=headers_pb)
        assert r_ct.status_code == 200 and len(r_ct.json()) == 0, "Cán bộ phường khác không được đọc dữ liệu phường A"

    # 6. Ca 5: View công khai cong_khai_giay_phep cho phép tra cứu công khai không lộ ho_so_id, signed_doc_id
    with httpx.Client(base_url=GATEWAY_URL, timeout=5.0) as client:
        r_pub = client.get(f"/api/v1/rest/cong_khai_giay_phep?so_giay_phep=eq.{so_gp}")
        assert r_pub.status_code == 200 and len(r_pub.json()) == 1, "View công khai phải tra cứu được giấy phép"
        item = r_pub.json()[0]
        assert "so_giay_phep" in item
        assert "ho_so_id" not in item, "View công khai không được chứa ho_so_id"
        assert "signed_doc_id" not in item, "View công khai không được chứa signed_doc_id"

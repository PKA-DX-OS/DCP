# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""N-02: cap_giay_phep chỉ chạy ở CHO_KY, gọi lặp hoặc đồng thời chỉ sinh một giấy phép.

Mỗi ca tự chèn một hồ sơ riêng và xóa đúng hồ sơ đó (cùng giấy phép, công trình phát sinh) khi xong.
"""

import concurrent.futures
import json
import uuid

from tests.integration._ho_so import run_psql


def test_N02_cap_giay_phep_requires_cho_ky_status():
    """Gọi cap_giay_phep khi hồ sơ đang CHO_TIEP_NHAN phải bị từ chối với lỗi 55000."""
    proc_id = f"proc-test-n02-status-{uuid.uuid4().hex[:8]}"
    doc_id = str(uuid.uuid4())
    hs_id = str(uuid.uuid4())
    ma_hs = f"HS-TEST-{uuid.uuid4().hex[:6]}"

    # Tạo hồ sơ trạng thái CHO_TIEP_NHAN
    ins_sql = f"""
    INSERT INTO app_cap_phep.ho_so (
        id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
        dia_chi_cong_trinh, thua_dat, trang_thai, buoc, process_instance_id, han_tong_at
    ) VALUES (
        '{hs_id}', 'phuong-a', '{ma_hs}', 'cdt.test', 'Nguyen Van Test', '001200000099', '0901234567',
        'So 1 Pho Test', 'Thua 1 To 1', 'CHO_TIEP_NHAN', 'tiep_nhan', '{proc_id}', now() + interval '15 days'
    );
    """
    res_ins = run_psql(ins_sql)
    assert res_ins.returncode == 0, f"Insert hồ sơ thất bại: {res_ins.stderr}"

    try:
        call_sql = f"SELECT app_cap_phep_private.cap_giay_phep('{proc_id}', '{doc_id}'::uuid, 'PUB-TEST-01');"
        res_call = run_psql(call_sql)
        assert res_call.returncode != 0, f"Hồ sơ CHO_TIEP_NHAN không được phép cấp giấy phép! Output: {res_call.stdout}"
        assert "55000" in res_call.stderr or "CHO_KY" in res_call.stderr, f"Phải báo lỗi 55000 hoặc CHO_KY: {res_call.stderr}"
    finally:
        run_psql(f"DELETE FROM app_cap_phep.cong_trinh WHERE giay_phep_id IN (SELECT id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}');")
        run_psql(f"DELETE FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';")
        run_psql(f"DELETE FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")


def test_N02_cap_giay_phep_idempotent():
    """Gọi cap_giay_phep 2 lần liên tiếp trên cùng process_instance_id phải trả về kết quả giống nhau và idempotent=true."""
    proc_id = f"proc-test-n02-idem-{uuid.uuid4().hex[:8]}"
    doc_id = str(uuid.uuid4())
    hs_id = str(uuid.uuid4())
    ma_hs = f"HS-TEST-{uuid.uuid4().hex[:6]}"

    # Tạo hồ sơ trạng thái CHO_KY
    ins_sql = f"""
    INSERT INTO app_cap_phep.ho_so (
        id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
        dia_chi_cong_trinh, thua_dat, trang_thai, buoc, process_instance_id, han_tong_at
    ) VALUES (
        '{hs_id}', 'phuong-a', '{ma_hs}', 'cdt.test', 'Nguyen Van Test', '001200000099', '0901234567',
        'So 2 Pho Test', 'Thua 2 To 2', 'CHO_KY', 'phe_duyet', '{proc_id}', now() + interval '15 days'
    );
    """
    res_ins = run_psql(ins_sql)
    assert res_ins.returncode == 0, f"Insert hồ sơ thất bại: {res_ins.stderr}"

    try:
        call_sql = f"SELECT app_cap_phep_private.cap_giay_phep('{proc_id}', '{doc_id}'::uuid, 'PUB-TEST-02');"
        res1 = run_psql(call_sql)
        assert res1.returncode == 0, f"Gọi lần 1 thất bại: {res1.stderr}"
        data1 = json.loads(res1.stdout.strip())
        assert data1["status"] == "success"
        gp1_id = data1["giay_phep_id"]
        so_gp1 = data1["so_giay_phep"]

        # Gọi lần 2
        res2 = run_psql(call_sql)
        assert res2.returncode == 0, f"Gọi lần 2 thất bại: {res2.stderr}"
        data2 = json.loads(res2.stdout.strip())
        assert data2["status"] == "success"
        assert data2.get("idempotent") is True, f"Lần gọi 2 phải có idempotent=true: {data2}"
        assert data2["giay_phep_id"] == gp1_id
        assert data2["so_giay_phep"] == so_gp1

        # Đếm số giấy phép tạo ra cho hs_id trong DB
        res_cnt = run_psql(f"SELECT count(*) FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';")
        assert res_cnt.stdout.strip() == "1", f"Chỉ được tạo đúng 1 giấy phép trong DB: {res_cnt.stdout.strip()}"
    finally:
        run_psql(f"DELETE FROM app_cap_phep.cong_trinh WHERE giay_phep_id IN (SELECT id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}');")
        run_psql(f"DELETE FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';")
        run_psql(f"DELETE FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")


def test_N02_cap_giay_phep_concurrency():
    """5 cuộc gọi đồng thời cap_giay_phep trên cùng 1 hồ sơ chỉ sinh đúng 1 giấy phép duy nhất."""
    proc_id = f"proc-test-n02-conc-{uuid.uuid4().hex[:8]}"
    doc_id = str(uuid.uuid4())
    hs_id = str(uuid.uuid4())
    ma_hs = f"HS-TEST-{uuid.uuid4().hex[:6]}"

    # Tạo hồ sơ trạng thái CHO_KY
    ins_sql = f"""
    INSERT INTO app_cap_phep.ho_so (
        id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
        dia_chi_cong_trinh, thua_dat, trang_thai, buoc, process_instance_id, han_tong_at
    ) VALUES (
        '{hs_id}', 'phuong-a', '{ma_hs}', 'cdt.test', 'Nguyen Van Test', '001200000099', '0901234567',
        'So 3 Pho Test', 'Thua 3 To 3', 'CHO_KY', 'phe_duyet', '{proc_id}', now() + interval '15 days'
    );
    """
    res_ins = run_psql(ins_sql)
    assert res_ins.returncode == 0, f"Insert hồ sơ thất bại: {res_ins.stderr}"

    try:
        def call_worker(idx: int):
            call_sql = f"SELECT app_cap_phep_private.cap_giay_phep('{proc_id}', '{doc_id}'::uuid, 'PUB-CONC-{idx}');"
            return run_psql(call_sql)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(call_worker, i) for i in range(5)]
            results = [f.result() for f in futures]

        # Kiểm tra các kết quả trả về
        success_results = []
        for r in results:
            assert r.returncode == 0, f"Worker lỗi: {r.stderr}"
            data = json.loads(r.stdout.strip())
            assert data.get("status") == "success"
            success_results.append(data)

        assert len(success_results) == 5
        gp_ids = {r["giay_phep_id"] for r in success_results}
        so_gps = {r["so_giay_phep"] for r in success_results}
        assert len(gp_ids) == 1, f"Nhiều giay_phep_id được tạo ra: {gp_ids}"
        assert len(so_gps) == 1, f"Nhiều so_giay_phep được tạo ra: {so_gps}"

        # Đếm trong DB
        res_cnt = run_psql(f"SELECT count(*) FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';")
        assert res_cnt.stdout.strip() == "1", f"Đúng 1 giấy phép trong DB, thực tế: {res_cnt.stdout.strip()}"
    finally:
        run_psql(f"DELETE FROM app_cap_phep.cong_trinh WHERE giay_phep_id IN (SELECT id FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}');")
        run_psql(f"DELETE FROM app_cap_phep.giay_phep WHERE ho_so_id = '{hs_id}';")
        run_psql(f"DELETE FROM app_cap_phep.ho_so WHERE id = '{hs_id}';")

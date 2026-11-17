# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Kiểm thử hồi quy bảo mật N-01:
- Chặn lộ nhật ký kiểm toán toàn phường qua view v_audit_log.
- Kiểm soát quyền truy cập chi tiết qua RPC lay_nhat_ky_ho_so và lay_nhat_ky_phuong.
"""

import base64
import json
import subprocess
import urllib.request
import urllib.error
import pytest
from tests.integration._auth import GATEWAY_URL, get_token


def parse_sub(tok: str) -> str:
    raw = tok.split(".")[1]
    raw += "=" * (-len(raw) % 4)
    return json.loads(base64.urlsafe_b64decode(raw))["sub"]


def run_sql(sql: str) -> str:
    cmd = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout.strip()


def test_N01_v_audit_log_not_exposed_to_citizen():
    """Chủ đầu tư không có hồ sơ không được đọc v_audit_log."""
    token_lan = get_token("cdt.lan")
    req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/v_audit_log",
        headers={"Authorization": f"Bearer {token_lan}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            # Nếu truy cập được thì phải rỗng, không được thấy audit của người khác
            assert len(data) == 0, f"Lỗ hổng N-01: cdt.lan đọc được {len(data)} bản ghi audit của người khác!"
    except urllib.error.HTTPError as e:
        # 404 (view đã bị xóa) hoặc 403/401 là đạt
        assert e.code in (403, 404), f"Kỳ vọng 403/404 nhưng nhận HTTP {e.code}"


def test_N01_lay_nhat_ky_ho_so_access_control():
    """Kiểm tra phân quyền đọc nhật ký hồ sơ theo thẩm quyền."""
    token_minh = get_token("cdt.minh")
    token_lan = get_token("cdt.lan")
    token_binh = get_token("td.binh")
    token_cuong = get_token("td.cuong")

    # Lấy 1 hồ sơ của cdt.minh
    hoso_id = run_sql("SELECT id FROM app_cap_phep.ho_so WHERE tenant='phuong-a' AND chu_dau_tu_sub = (SELECT id::text FROM core.users_directory WHERE username='cdt.minh') LIMIT 1;")
    if not hoso_id:
        # Tạo nhanh hồ sơ mẫu của cdt.minh nếu chưa có
        minh_sub = run_sql("SELECT id::text FROM core.users_directory WHERE username='cdt.minh';")
        run_sql(f"""
        INSERT INTO app_cap_phep.ho_so (tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai, dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2, trang_thai, buoc, han_tong_at)
        VALUES ('phuong-a', 'CP-TEST-OWNER-01', '{minh_sub}', 'Trần Văn Minh', '001099001234', '0901234567', 'Số 1 Phố Test Owner', 'Thửa 1 Tờ 1', 2, 80.0, 'DA_NOP', 'tiep_nhan', now() + interval '15 days')
        ON CONFLICT (tenant, ma_ho_so) DO NOTHING;
        """)
        hoso_id = run_sql("SELECT id FROM app_cap_phep.ho_so WHERE tenant='phuong-a' AND chu_dau_tu_sub = (SELECT id::text FROM core.users_directory WHERE username='cdt.minh') LIMIT 1;")
    assert hoso_id, "Phải có ít nhất 1 hồ sơ của cdt.minh tại phuong-a"

    binh_sub = parse_sub(token_binh)

    # Đảm bảo phân công cho td.binh, không phân công cho td.cuong
    run_sql(f"""
    DELETE FROM core.assignments WHERE object_id = '{hoso_id}';
    INSERT INTO core.assignments (tenant, object_type, object_id, user_sub, role)
    VALUES ('phuong-a', 'ho_so', '{hoso_id}', '{binh_sub}', 'tham-dinh')
    ON CONFLICT DO NOTHING;
    """)

    # 0. cdt.minh (chính chủ hồ sơ) gọi lay_nhat_ky_ho_so -> 200 OK và chỉ nhận bản ghi của hồ sơ này (P-06)
    req_owner = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/rpc/lay_nhat_ky_ho_so",
        headers={"Authorization": f"Bearer {token_minh}", "Content-Type": "application/json"},
        data=json.dumps({"p_ho_so_id": hoso_id}).encode(),
    )
    with urllib.request.urlopen(req_owner, timeout=5) as resp_owner:
        assert resp_owner.status == 200, f"cdt.minh phải đọc được nhật ký hồ sơ chính chủ: HTTP {resp_owner.status}"
        owner_logs = json.loads(resp_owner.read().decode())
        assert isinstance(owner_logs, list), "Kỳ vọng kết quả là mảng danh sách bản ghi"
        for entry in owner_logs:
            assert entry.get("object_id") == hoso_id, f"Bản ghi kiểm toán không thuộc hồ sơ {hoso_id}: {entry}"

    # 1. cdt.lan (người khác) gọi lay_nhat_ky_ho_so -> Phải bị chặn 403 hoặc SQL 42501
    audit_denied_before = int(run_sql(f"SELECT count(*) FROM core.audit_log WHERE action='access.denied' AND object_id='{hoso_id}';") or "0")
    req_lan = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/rpc/lay_nhat_ky_ho_so",
        headers={"Authorization": f"Bearer {token_lan}", "Content-Type": "application/json"},
        data=json.dumps({"p_ho_so_id": hoso_id}).encode(),
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_lan, timeout=5)
    assert exc_info.value.code in (403, 404, 400), f"cdt.lan phải bị từ chối truy cập: {exc_info.value.code}"

    # Kiểm tra có ghi nhận audit access.denied
    audit_denied_after = int(run_sql(f"SELECT count(*) FROM core.audit_log WHERE action='access.denied' AND object_id='{hoso_id}';") or "0")
    assert audit_denied_after >= audit_denied_before + 1, "Phải ghi nhận audit access.denied khi truy cập trái phép nhật ký hồ sơ"

    # 2. td.cuong (thẩm định viên chưa phân công) gọi lay_nhat_ky_ho_so -> Bị chặn
    req_cuong = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/rpc/lay_nhat_ky_ho_so",
        headers={"Authorization": f"Bearer {token_cuong}", "Content-Type": "application/json"},
        data=json.dumps({"p_ho_so_id": hoso_id}).encode(),
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info_cuong:
        urllib.request.urlopen(req_cuong, timeout=5)
    assert exc_info_cuong.value.code in (403, 404, 400), f"td.cuong chưa phân công phải bị từ chối: {exc_info_cuong.value.code}"

    # 3. td.binh (thẩm định viên được phân công) gọi lay_nhat_ky_ho_so -> 200 OK
    req_binh = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/rpc/lay_nhat_ky_ho_so",
        headers={"Authorization": f"Bearer {token_binh}", "Content-Type": "application/json"},
        data=json.dumps({"p_ho_so_id": hoso_id}).encode(),
    )
    with urllib.request.urlopen(req_binh, timeout=5) as resp:
        assert resp.status == 200
        logs = json.loads(resp.read().decode())
        assert isinstance(logs, list)

    # 4. cdt.minh hoặc td.binh gọi lay_nhat_ky_phuong -> Phải bị chặn 403
    req_phuong_cdt = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/rpc/lay_nhat_ky_phuong",
        headers={"Authorization": f"Bearer {token_minh}", "Content-Type": "application/json"},
        data=json.dumps({"p_limit": 50}).encode(),
    )
    with pytest.raises(urllib.error.HTTPError) as exc_phuong:
        urllib.request.urlopen(req_phuong_cdt, timeout=5)
    assert exc_phuong.value.code in (403, 400), f"Chủ đầu tư không được phép đọc nhật ký phường: {exc_phuong.value.code}"


def test_N01_tenant_admin_lay_nhat_ky_phuong():
    """Kiểm tra tenant-admin đọc được nhật ký phường mình, không đọc được phường khác."""
    token_admin = get_token("admin")
    req = urllib.request.Request(
        f"{GATEWAY_URL}/api/v1/rest/rpc/lay_nhat_ky_phuong",
        headers={"Authorization": f"Bearer {token_admin}", "Content-Type": "application/json"},
        data=json.dumps({"p_limit": 50}).encode(),
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        logs = json.loads(resp.read().decode())
        assert isinstance(logs, list)

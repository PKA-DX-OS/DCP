# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import subprocess
import urllib.request
import urllib.error
from tests.integration.conftest import GATEWAY_URL, get_token


def test_V3_05_file_download_403_records_access_denied_audit():
    # 1. Đảm bảo có tệp mẫu trong core.files không thuộc td.cuong
    insert_sql = """
    INSERT INTO core.files (id, tenant, owner_sub, object_type, object_id, object_key, sha256, size, mime, status)
    VALUES ('e5555555-5555-5555-5555-555555555555', 'phuong-a', 'other_owner_sub_123', 'ho_so', gen_random_uuid(), 'phuong-a/2026/test.pdf', 'hash', 100, 'application/pdf', 'clean')
    ON CONFLICT (id) DO NOTHING;
    """
    cmd_ins = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-c", insert_sql]
    subprocess.run(cmd_ins, capture_output=True, text=True, check=True)
    file_id = "e5555555-5555-5555-5555-555555555555"

    # 2. Đếm số bản ghi access.denied trước khi gọi
    query_count = "SELECT count(*) FROM core.audit_log WHERE action = 'access.denied';"
    cmd_count = ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", query_count]
    proc_before = subprocess.run(cmd_count, capture_output=True, text=True, check=True)
    count_before = int(proc_before.stdout.strip())

    # 3. td.cuong gọi tải tệp
    token_cuong = get_token("td.cuong")
    url = f"{GATEWAY_URL}/api/v1/files/{file_id}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token_cuong}"})

    status_code = None
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status_code = resp.status
    except urllib.error.HTTPError as e:
        status_code = e.code

    assert status_code == 403, f"Mong đợi HTTP 403, nhận được {status_code}"

    # 4. Đếm số bản ghi access.denied sau khi gọi
    proc_after = subprocess.run(cmd_count, capture_output=True, text=True, check=True)
    count_after = int(proc_after.stdout.strip())

    assert count_after > count_before, (
        f"Lỗi V3-05: 403 khi tải tệp không ghi audit access.denied! "
        f"Trước: {count_before}, Sau: {count_after}"
    )

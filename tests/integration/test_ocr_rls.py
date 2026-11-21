# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""D-OCR: Test tích hợp RLS, quyền và cách ly địa bàn của app_cap_phep.ocr_extractions."""

import subprocess
import uuid
import pytest


def _run_sql(sql: str) -> str:
    res = subprocess.run(
        ["docker", "exec", "dxos-postgres", "psql", "-U", "postgres", "-d", "dxos", "-t", "-A", "-c", sql],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if res.returncode != 0:
        raise RuntimeError(f"psql error: {res.stderr}\nSQL: {sql}")
    lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip() and line.strip() not in ("SET", "RESET")]
    return lines[-1] if lines else ""


def test_ocr_extractions_rls_va_cach_ly_phuong():
    ext_a = str(uuid.uuid4())
    ext_b = str(uuid.uuid4())
    file_a = str(uuid.uuid4())
    file_b = str(uuid.uuid4())
    idem_a = f"idem-test-{uuid.uuid4().hex[:12]}"

    try:
        # 1. Dùng vai svc để tạo 2 bản ghi cho phuong-a và phuong-b
        _run_sql(f"""
            SET ROLE svc;
            INSERT INTO app_cap_phep.ocr_extractions (id, tenant, file_id, doc_type, status, idempotency_key, fields)
            VALUES ('{ext_a}', 'phuong-a', '{file_a}', 'cccd', 'needs_review', '{idem_a}', '[{{"name": "ho_ten", "value": "Nguyen Van A"}}]'::jsonb);

            INSERT INTO app_cap_phep.ocr_extractions (id, tenant, file_id, doc_type, status, fields)
            VALUES ('{ext_b}', 'phuong-b', '{file_b}', 'cccd', 'needs_review', '[{{"name": "ho_ten", "value": "Tran Van B"}}]'::jsonb);
            RESET ROLE;
        """)

        # 2. web_user của phuong-a chỉ SELECT được bản ghi phuong-a
        count_a = _run_sql(f"""
            SET ROLE web_user;
            SET LOCAL "request.jwt.claims" = '{{"tenant": "phuong-a", "sub": "user_a", "roles": ["app:cap-phep:mot-cua"]}}';
            SELECT count(*) FROM app_cap_phep.ocr_extractions WHERE id IN ('{ext_a}', '{ext_b}');
        """)
        assert count_a == "1"

        visible_ids_a = _run_sql(f"""
            SET ROLE web_user;
            SET LOCAL "request.jwt.claims" = '{{"tenant": "phuong-a", "sub": "user_a", "roles": ["app:cap-phep:mot-cua"]}}';
            SELECT id FROM app_cap_phep.ocr_extractions WHERE id IN ('{ext_a}', '{ext_b}');
        """)
        assert visible_ids_a == ext_a

        # 3. web_user của phuong-b chỉ SELECT được bản ghi phuong-b
        visible_ids_b = _run_sql(f"""
            SET ROLE web_user;
            SET LOCAL "request.jwt.claims" = '{{"tenant": "phuong-b", "sub": "user_b", "roles": ["app:cap-phep:mot-cua"]}}';
            SELECT id FROM app_cap_phep.ocr_extractions WHERE id IN ('{ext_a}', '{ext_b}');
        """)
        assert visible_ids_b == ext_b

        # 4. web_user KHÔNG được phép INSERT trực tiếp (chỉ SELECT)
        with pytest.raises(RuntimeError) as exc_insert:
            _run_sql(f"""
                SET ROLE web_user;
                SET LOCAL "request.jwt.claims" = '{{"tenant": "phuong-a", "sub": "user_a"}}';
                INSERT INTO app_cap_phep.ocr_extractions (tenant, file_id, doc_type)
                VALUES ('phuong-a', '{uuid.uuid4()}', 'cccd');
            """)
        assert "permission denied" in str(exc_insert.value).lower()

        # 5. web_user KHÔNG được phép UPDATE trực tiếp
        with pytest.raises(RuntimeError) as exc_update:
            _run_sql(f"""
                SET ROLE web_user;
                SET LOCAL "request.jwt.claims" = '{{"tenant": "phuong-a", "sub": "user_a"}}';
                UPDATE app_cap_phep.ocr_extractions SET status = 'confirmed' WHERE id = '{ext_a}';
            """)
        assert "permission denied" in str(exc_update.value).lower()

        # 6. Kiểm tra ràng buộc unique (tenant, idempotency_key)
        with pytest.raises(RuntimeError) as exc_uq:
            _run_sql(f"""
                SET ROLE svc;
                INSERT INTO app_cap_phep.ocr_extractions (tenant, file_id, doc_type, idempotency_key)
                VALUES ('phuong-a', '{uuid.uuid4()}', 'cccd', '{idem_a}');
                RESET ROLE;
            """)
        assert "duplicate key" in str(exc_uq.value).lower()

        # 7. Kiểm tra hàm DSAR export và erase
        # Lấy 1 dossier_id có sẵn của phuong-a để kiểm tra
        dossier_id = _run_sql("SELECT id FROM app_cap_phep.ho_so WHERE tenant = 'phuong-a' LIMIT 1;")
        _run_sql(f"""
            SET ROLE svc;
            UPDATE app_cap_phep.ocr_extractions SET dossier_id = '{dossier_id}' WHERE id = '{ext_a}';
            RESET ROLE;
        """)

        export_res = _run_sql(f"""
            SELECT app_cap_phep.dsar_ocr_export('phuong-a', ARRAY['{dossier_id}'::uuid]);
        """)
        assert "Nguyen Van A" in export_res

        erase_res = _run_sql(f"""
            SELECT app_cap_phep.dsar_ocr_erase('phuong-a', ARRAY['{dossier_id}'::uuid], 'DSAR test');
        """)
        assert "success" in erase_res

        # Sau khi erase, fields phải thành rỗng '[]'
        fields_after = _run_sql(f"""
            SET ROLE svc;
            SELECT fields::text FROM app_cap_phep.ocr_extractions WHERE id = '{ext_a}';
            RESET ROLE;
        """)
        assert fields_after == "[]"

    finally:
        _run_sql(f"""
            DELETE FROM app_cap_phep.ocr_extractions WHERE id IN ('{ext_a}', '{ext_b}');
        """)

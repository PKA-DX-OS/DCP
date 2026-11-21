-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 22-data-quality.sql — rule chất lượng dữ liệu, lần chạy, kết quả, vấn đề (D-DQ-01, D-DQ-03).
-- Rule chỉ khai báo ở đây (web_user không ghi được bảng rule vì cột SQL là câu lệnh chạy thật).
-- Mỗi rule có hai câu SELECT:
--   sql_total: (tenant, total)                    — số bản ghi được kiểm theo phường
--   sql_fail:  (tenant, entity_id, field, dossier_id) — bản ghi lỗi, không có giá trị trường
-- scripts/data_quality_worker.py chạy rule trong giao dịch chỉ đọc có statement_timeout; rule lỗi
-- (thiếu bảng, sai SQL) chỉ tính vào rule_errors, không làm hỏng lần chạy. Idempotent.

CREATE TABLE IF NOT EXISTS core.data_quality_rules (
    code text PRIMARY KEY,
    domain text NOT NULL REFERENCES core.data_owners(domain),
    dimension text NOT NULL,
    severity text NOT NULL,
    entity_type text NOT NULL,
    description text NOT NULL,
    owner text NOT NULL,
    sql_total text NOT NULL,
    sql_fail text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_dq_rule_code CHECK (code ~ '^DQ-[A-Z]+-[0-9]{2}$'),
    CONSTRAINT chk_dq_rule_dim CHECK (dimension IN ('completeness', 'validity', 'uniqueness', 'consistency',
                                                    'timeliness', 'referential', 'security')),
    CONSTRAINT chk_dq_rule_sev CHECK (severity IN ('info', 'warn', 'critical'))
);

CREATE TABLE IF NOT EXISTS core.data_quality_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    status text NOT NULL DEFAULT 'running',
    triggered_by text,
    rule_errors integer NOT NULL DEFAULT 0,
    CONSTRAINT chk_dq_run_status CHECK (status IN ('running', 'succeeded', 'partial', 'failed'))
);

CREATE TABLE IF NOT EXISTS core.data_quality_results (
    run_id uuid NOT NULL REFERENCES core.data_quality_runs(id) ON DELETE CASCADE,
    tenant text NOT NULL,
    rule_code text NOT NULL REFERENCES core.data_quality_rules(code),
    total integer NOT NULL,
    failed integer NOT NULL,
    score numeric(5, 2),
    sample_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (run_id, tenant, rule_code)
);

CREATE TABLE IF NOT EXISTS core.data_quality_issues (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    rule_code text NOT NULL REFERENCES core.data_quality_rules(code),
    entity_type text NOT NULL,
    entity_id text NOT NULL,
    field text,
    dossier_id uuid,
    severity text NOT NULL,
    status text NOT NULL DEFAULT 'open',
    assigned_to text,
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    last_seen_run uuid,
    UNIQUE (tenant, rule_code, entity_id),
    CONSTRAINT chk_dq_issue_status CHECK (status IN ('open', 'in_progress', 'resolved', 'ignored')),
    CONSTRAINT chk_dq_issue_sev CHECK (severity IN ('info', 'warn', 'critical'))
);

CREATE INDEX IF NOT EXISTS idx_dq_results_tenant ON core.data_quality_results (tenant, run_id);
CREATE INDEX IF NOT EXISTS idx_dq_issues_tenant ON core.data_quality_issues (tenant, status, severity, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dq_issues_entity ON core.data_quality_issues (tenant, entity_id);

-- Rule và lần chạy là cấu hình nền tảng: đọc theo vai; kết quả, vấn đề theo phường
DO $$
DECLARE
    v_bang text;
BEGIN
    FOREACH v_bang IN ARRAY ARRAY['data_quality_rules', 'data_quality_runs', 'data_quality_results', 'data_quality_issues'] LOOP
        EXECUTE format('ALTER TABLE core.%I ENABLE ROW LEVEL SECURITY', v_bang);
        EXECUTE format('ALTER TABLE core.%I FORCE ROW LEVEL SECURITY', v_bang);
        EXECUTE format('DROP POLICY IF EXISTS rls_%s_svc ON core.%I', v_bang, v_bang);
        EXECUTE format(
            'CREATE POLICY rls_%s_svc ON core.%I FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true)',
            v_bang, v_bang);
        EXECUTE format('GRANT ALL ON core.%I TO svc, dxos_svc, dxos_owner', v_bang);
    END LOOP;
END $$;

DROP POLICY IF EXISTS rls_dq_rules_read ON core.data_quality_rules;
CREATE POLICY rls_dq_rules_read ON core.data_quality_rules FOR SELECT TO web_user USING (true);
DROP POLICY IF EXISTS rls_dq_runs_read ON core.data_quality_runs;
CREATE POLICY rls_dq_runs_read ON core.data_quality_runs FOR SELECT TO web_user USING (true);
DROP POLICY IF EXISTS rls_dq_results_read ON core.data_quality_results;
CREATE POLICY rls_dq_results_read ON core.data_quality_results FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant());
DROP POLICY IF EXISTS rls_dq_issues_read ON core.data_quality_issues;
CREATE POLICY rls_dq_issues_read ON core.data_quality_issues FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant());
-- Giao, đóng vấn đề: trong phường; API kiểm vai và người được giao
DROP POLICY IF EXISTS rls_dq_issues_update ON core.data_quality_issues;
CREATE POLICY rls_dq_issues_update ON core.data_quality_issues FOR UPDATE TO web_user
    USING (tenant = core.jwt_tenant()) WITH CHECK (tenant = core.jwt_tenant());

-- Chỉ cột sql_* bị ẩn với web_user: đọc rule qua cột mô tả
GRANT SELECT (code, domain, dimension, severity, entity_type, description, owner, enabled, created_at)
    ON core.data_quality_rules TO web_user;
GRANT SELECT ON core.data_quality_runs, core.data_quality_results TO web_user;
GRANT SELECT ON core.data_quality_issues TO web_user;
GRANT UPDATE (status, assigned_to, note, resolved_at) ON core.data_quality_issues TO web_user;

-- Danh mục rule (D-DQ-01)
INSERT INTO core.data_quality_rules (code, domain, dimension, severity, entity_type, description, owner, sql_total, sql_fail) VALUES
('DQ-CD-01', 'cong_dan', 'validity', 'critical', 'ho_so', 'CCCD của người nộp phải đủ 12 chữ số', 'Bộ phận một cửa',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'cccd', id FROM app_cap_phep.ho_so WHERE coalesce(cccd, '') !~ '^[0-9]{12}$'$q$),
('DQ-CD-02', 'cong_dan', 'validity', 'warn', 'ho_so', 'Số điện thoại đúng dạng 0xxxxxxxxx hoặc +84xxxxxxxxx', 'Bộ phận một cửa',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'dien_thoai', id FROM app_cap_phep.ho_so
    WHERE regexp_replace(coalesce(dien_thoai, ''), '[ .-]', '', 'g') !~ '^(0|\+84)[0-9]{9}$'$q$),
('DQ-CD-03', 'cong_dan', 'completeness', 'critical', 'ho_so', 'Hồ sơ phải có họ tên người nộp', 'Bộ phận một cửa',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'ho_ten', id FROM app_cap_phep.ho_so WHERE btrim(coalesce(ho_ten, '')) = ''$q$),
('DQ-CD-04', 'cong_dan', 'consistency', 'warn', 'ho_so', 'Một CCCD không gắn với nhiều họ tên khác nhau', 'Bộ phận một cửa',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT h.tenant, h.id::text, 'ho_ten', h.id FROM app_cap_phep.ho_so h
    JOIN (SELECT tenant, cccd FROM app_cap_phep.ho_so GROUP BY tenant, cccd
          HAVING count(DISTINCT lower(btrim(ho_ten))) > 1) x ON x.tenant = h.tenant AND x.cccd = h.cccd$q$),
('DQ-TD-01', 'thua_dat', 'completeness', 'warn', 'ho_so', 'Hồ sơ phải ghi thửa đất', 'Bộ phận thẩm định',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'thua_dat', id FROM app_cap_phep.ho_so WHERE btrim(coalesce(thua_dat, '')) = ''$q$),
('DQ-TD-02', 'thua_dat', 'completeness', 'info', 'ho_so', 'Hồ sơ nên gắn mã định danh địa điểm', 'Bộ phận thẩm định',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'ma_dinh_danh_dia_diem', id FROM app_cap_phep.ho_so WHERE ma_dinh_danh_dia_diem IS NULL$q$),
('DQ-TD-03', 'thua_dat', 'validity', 'warn', 'ho_so', 'Mã định danh địa điểm đủ 12 chữ số', 'Bộ phận thẩm định',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so WHERE ma_dinh_danh_dia_diem IS NOT NULL GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'ma_dinh_danh_dia_diem', id FROM app_cap_phep.ho_so
    WHERE ma_dinh_danh_dia_diem IS NOT NULL AND ma_dinh_danh_dia_diem !~ '^[0-9]{12}$'$q$),
('DQ-HS-01', 'ho_so', 'validity', 'critical', 'ho_so', 'Số tầng phải lớn hơn 0', 'Bộ phận một cửa',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'so_tang', id FROM app_cap_phep.ho_so WHERE coalesce(so_tang, 0) <= 0$q$),
('DQ-HS-02', 'ho_so', 'validity', 'critical', 'ho_so', 'Diện tích sàn phải lớn hơn 0', 'Bộ phận một cửa',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'dien_tich_san_m2', id FROM app_cap_phep.ho_so WHERE coalesce(dien_tich_san_m2, 0) <= 0$q$),
('DQ-HS-03', 'ho_so', 'uniqueness', 'critical', 'ho_so', 'Mã hồ sơ không trùng trong phường', 'Bộ phận một cửa',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT h.tenant, h.id::text, 'ma_ho_so', h.id FROM app_cap_phep.ho_so h
    JOIN (SELECT tenant, ma_ho_so FROM app_cap_phep.ho_so GROUP BY tenant, ma_ho_so HAVING count(*) > 1) x
      ON x.tenant = h.tenant AND x.ma_ho_so = h.ma_ho_so$q$),
('DQ-HS-04', 'ho_so', 'completeness', 'warn', 'ho_so', 'Hồ sơ phải có địa chỉ công trình', 'Bộ phận một cửa',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'dia_chi_cong_trinh', id FROM app_cap_phep.ho_so WHERE btrim(coalesce(dia_chi_cong_trinh, '')) = ''$q$),
('DQ-HS-05', 'ho_so', 'timeliness', 'warn', 'ho_so', 'Hồ sơ đang xử lý chưa quá hạn tổng', 'Lãnh đạo phường',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so WHERE trang_thai NOT IN ('DA_CAP', 'TU_CHOI') GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'han_tong_at', id FROM app_cap_phep.ho_so
    WHERE trang_thai NOT IN ('DA_CAP', 'TU_CHOI') AND han_tong_at < now()$q$),
('DQ-HS-06', 'ho_so', 'uniqueness', 'warn', 'ho_so', 'Không nộp trùng cùng CCCD và thửa đất', 'Bộ phận một cửa',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so GROUP BY tenant$q$,
 $q$SELECT h.tenant, h.id::text, 'thua_dat', h.id FROM app_cap_phep.ho_so h
    JOIN (SELECT tenant, cccd, lower(btrim(thua_dat)) AS td FROM app_cap_phep.ho_so
          WHERE btrim(coalesce(thua_dat, '')) <> '' GROUP BY 1, 2, 3 HAVING count(*) > 1) x
      ON x.tenant = h.tenant AND x.cccd = h.cccd AND x.td = lower(btrim(h.thua_dat))$q$),
('DQ-GP-01', 'giay_phep', 'consistency', 'critical', 'giay_phep', 'Giấy phép phải có văn bản ký số', 'Lãnh đạo phường',
 $q$SELECT tenant, count(*) FROM app_cap_phep.giay_phep GROUP BY tenant$q$,
 $q$SELECT g.tenant, g.id::text, 'signed_doc_id', g.ho_so_id FROM app_cap_phep.giay_phep g
    LEFT JOIN core.signed_docs d ON d.id = g.signed_doc_id WHERE d.id IS NULL$q$),
('DQ-GP-02', 'giay_phep', 'consistency', 'critical', 'ho_so', 'Hồ sơ đã cấp phải có giấy phép', 'Lãnh đạo phường',
 $q$SELECT tenant, count(*) FROM app_cap_phep.ho_so WHERE trang_thai = 'DA_CAP' GROUP BY tenant$q$,
 $q$SELECT h.tenant, h.id::text, 'trang_thai', h.id FROM app_cap_phep.ho_so h
    WHERE h.trang_thai = 'DA_CAP' AND NOT EXISTS (SELECT 1 FROM app_cap_phep.giay_phep g WHERE g.ho_so_id = h.id)$q$),
('DQ-GP-03', 'giay_phep', 'uniqueness', 'critical', 'giay_phep', 'Số giấy phép không trùng', 'Lãnh đạo phường',
 $q$SELECT tenant, count(*) FROM app_cap_phep.giay_phep GROUP BY tenant$q$,
 $q$SELECT g.tenant, g.id::text, 'so_giay_phep', g.ho_so_id FROM app_cap_phep.giay_phep g
    JOIN (SELECT tenant, so_giay_phep FROM app_cap_phep.giay_phep GROUP BY 1, 2 HAVING count(*) > 1) x
      ON x.tenant = g.tenant AND x.so_giay_phep = g.so_giay_phep$q$),
('DQ-CT-01', 'cong_trinh', 'referential', 'warn', 'giay_phep', 'Giấy phép hiệu lực phải có công trình', 'Bộ phận trật tự xây dựng',
 $q$SELECT tenant, count(*) FROM app_cap_phep.giay_phep WHERE trang_thai = 'hieu_luc' GROUP BY tenant$q$,
 $q$SELECT g.tenant, g.id::text, 'cong_trinh', g.ho_so_id FROM app_cap_phep.giay_phep g
    WHERE g.trang_thai = 'hieu_luc' AND NOT EXISTS (SELECT 1 FROM app_cap_phep.cong_trinh c WHERE c.giay_phep_id = g.id)$q$),
('DQ-CT-02', 'cong_trinh', 'uniqueness', 'critical', 'cong_trinh', 'Mã công trình không trùng', 'Bộ phận trật tự xây dựng',
 $q$SELECT tenant, count(*) FROM app_cap_phep.cong_trinh GROUP BY tenant$q$,
 $q$SELECT c.tenant, c.id::text, 'ma_cong_trinh', g.ho_so_id FROM app_cap_phep.cong_trinh c
    LEFT JOIN app_cap_phep.giay_phep g ON g.id = c.giay_phep_id
    JOIN (SELECT tenant, ma_cong_trinh FROM app_cap_phep.cong_trinh GROUP BY 1, 2 HAVING count(*) > 1) x
      ON x.tenant = c.tenant AND x.ma_cong_trinh = c.ma_cong_trinh$q$),
('DQ-GT-01', 'giay_to', 'security', 'critical', 'tep', 'Tệp không bị nhiễm mã độc hoặc quét lỗi', 'Bộ phận một cửa',
 $q$SELECT tenant, count(*) FROM core.files GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'status',
           CASE WHEN object_type = 'ho_so' AND object_id ~ '^[0-9a-f-]{36}$' THEN object_id::uuid END
    FROM core.files WHERE status <> 'clean'$q$),
('DQ-KT-01', 'kiem_tra', 'referential', 'critical', 'moc_nghiem_thu', 'Mốc nghiệm thu phải thuộc một hồ sơ có thật', 'Bộ phận thẩm định',
 $q$SELECT tenant, count(*) FROM app_construction.moc_nghiem_thu GROUP BY tenant$q$,
 $q$SELECT m.tenant, m.id::text, 'ho_so_id', NULL::uuid FROM app_construction.moc_nghiem_thu m
    WHERE NOT EXISTS (SELECT 1 FROM app_cap_phep.ho_so h WHERE h.id = m.ho_so_id)$q$),
('DQ-KT-02', 'kiem_tra', 'timeliness', 'warn', 'phieu_kiem_tra', 'Phiếu kiểm tra đang mở chưa quá hạn xử lý', 'Bộ phận trật tự xây dựng',
 $q$SELECT tenant, count(*) FROM app_cap_phep.phieu_kiem_tra WHERE trang_thai <> 'DA_XU_LY' GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'han_xu_ly_at', NULL::uuid FROM app_cap_phep.phieu_kiem_tra
    WHERE trang_thai <> 'DA_XU_LY' AND han_xu_ly_at < now()$q$),
('DQ-AU-01', 'audit', 'completeness', 'info', 'audit_log', 'Sự kiện do người dùng phải có người thực hiện', 'Quản trị nền tảng',
 $q$SELECT tenant, count(*) FROM core.audit_log WHERE actor_type = 'user' GROUP BY tenant$q$,
 $q$SELECT tenant, id::text, 'actor_sub', NULL::uuid FROM core.audit_log
    WHERE actor_type = 'user' AND btrim(coalesce(actor_sub, '')) = ''$q$)
ON CONFLICT (code) DO UPDATE
SET domain = EXCLUDED.domain, dimension = EXCLUDED.dimension, severity = EXCLUDED.severity,
    entity_type = EXCLUDED.entity_type, description = EXCLUDED.description, owner = EXCLUDED.owner,
    sql_total = EXCLUDED.sql_total, sql_fail = EXCLUDED.sql_fail;

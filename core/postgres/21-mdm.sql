-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 21-mdm.sql — dữ liệu chủ (MDM nhẹ): chủ thể, thửa đất, công trình, tổ chức và liên kết với hồ sơ
-- (D-MDM-01). MDM là lớp liên kết: không ghi đè bảng nguồn của ứng dụng; họ tên, điện thoại đọc từ
-- nguồn, CCCD chỉ lưu HMAC (khóa ở secrets/mdm-hmac.key, không lưu trong DB).
-- Kèm bảng khóa idempotency dùng chung cho các API ghi của Track D. Idempotent.

CREATE TABLE IF NOT EXISTS core.mdm_subject (
    subject_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    cccd_hmac text,
    source text NOT NULL DEFAULT 'ho_so',
    source_ref text,
    confidence numeric(4, 3) NOT NULL DEFAULT 1,
    merged_into uuid REFERENCES core.mdm_subject(subject_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_mdm_subject_source CHECK (source IN ('ho_so', 'ocr', 'import', 'thu_cong')),
    CONSTRAINT chk_mdm_subject_conf CHECK (confidence BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS core.mdm_parcel (
    parcel_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ma_dinh_danh_dia_diem text,
    so_thua text,
    to_ban_do text,
    dien_tich_m2 numeric,
    geom jsonb,
    source text NOT NULL DEFAULT 'ho_so',
    source_ref text,
    confidence numeric(4, 3) NOT NULL DEFAULT 1,
    merged_into uuid REFERENCES core.mdm_parcel(parcel_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_mdm_parcel_source CHECK (source IN ('ho_so', 'ocr', 'import', 'thu_cong')),
    CONSTRAINT chk_mdm_parcel_conf CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT chk_mdm_parcel_ma CHECK (ma_dinh_danh_dia_diem IS NULL OR ma_dinh_danh_dia_diem ~ '^[0-9]{12}$')
);

CREATE TABLE IF NOT EXISTS core.mdm_construction (
    construction_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ma_cong_trinh text,
    parcel_id uuid REFERENCES core.mdm_parcel(parcel_id),
    dia_chi_chuan text,
    source text NOT NULL DEFAULT 'ho_so',
    source_ref text,
    confidence numeric(4, 3) NOT NULL DEFAULT 1,
    merged_into uuid REFERENCES core.mdm_construction(construction_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_mdm_construction_source CHECK (source IN ('ho_so', 'ocr', 'import', 'thu_cong')),
    CONSTRAINT chk_mdm_construction_conf CHECK (confidence BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS core.mdm_organization (
    org_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ten text NOT NULL,
    mst text,
    loai text,
    source text NOT NULL DEFAULT 'import',
    confidence numeric(4, 3) NOT NULL DEFAULT 1,
    merged_into uuid REFERENCES core.mdm_organization(org_id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_mdm_org_source CHECK (source IN ('ho_so', 'ocr', 'import', 'thu_cong')),
    CONSTRAINT chk_mdm_org_conf CHECK (confidence BETWEEN 0 AND 1)
);

-- Một dòng cho mỗi hồ sơ: thực thể chưa liên kết là null
CREATE TABLE IF NOT EXISTS core.mdm_dossier_link (
    tenant text NOT NULL,
    dossier_id uuid NOT NULL,
    subject_id uuid REFERENCES core.mdm_subject(subject_id),
    parcel_id uuid REFERENCES core.mdm_parcel(parcel_id),
    construction_id uuid REFERENCES core.mdm_construction(construction_id),
    permit_id uuid,
    confidence numeric(4, 3) NOT NULL DEFAULT 1,
    source text NOT NULL DEFAULT 'ho_so',
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by text,
    PRIMARY KEY (tenant, dossier_id),
    CONSTRAINT chk_mdm_link_source CHECK (source IN ('ho_so', 'ocr', 'import', 'thu_cong'))
);

-- Ứng viên trùng dưới ngưỡng tự liên kết, chờ người xét (D-MDM-02)
CREATE TABLE IF NOT EXISTS core.mdm_link_candidate (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    candidate_id uuid NOT NULL,
    confidence numeric(4, 3) NOT NULL,
    ly_do text[] NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'open',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant, entity_type, entity_id, candidate_id),
    CONSTRAINT chk_mdm_cand_type CHECK (entity_type IN ('subject', 'parcel', 'construction', 'organization')),
    CONSTRAINT chk_mdm_cand_status CHECK (status IN ('open', 'merged', 'dismissed')),
    CONSTRAINT chk_mdm_cand_conf CHECK (confidence BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS core.mdm_merge_log (
    merge_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    entity_type text NOT NULL,
    giu_id uuid NOT NULL,
    gop_ids uuid[] NOT NULL,
    ly_do text NOT NULL,
    trang_thai text NOT NULL DEFAULT 'da_gop',
    thuc_hien_luc timestamptz NOT NULL DEFAULT now(),
    thuc_hien_boi text,
    hoan_tac_luc timestamptz,
    hoan_tac_boi text,
    CONSTRAINT chk_mdm_merge_type CHECK (entity_type IN ('subject', 'parcel', 'construction', 'organization')),
    CONSTRAINT chk_mdm_merge_tt CHECK (trang_thai IN ('da_gop', 'da_hoan_tac'))
);

-- Khóa Idempotency-Key của API ghi Track D: gọi lại cùng khóa trả kết quả cũ
CREATE TABLE IF NOT EXISTS core.dh_idempotency (
    tenant text NOT NULL,
    scope text NOT NULL,
    key text NOT NULL,
    status_code integer NOT NULL,
    response jsonb NOT NULL,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant, scope, key)
);

-- Khớp đúng (D-MDM-02): mỗi phường một bản ghi vàng cho mỗi CCCD, mã định danh địa điểm, mã công trình
CREATE UNIQUE INDEX IF NOT EXISTS uq_mdm_subject_cccd ON core.mdm_subject (tenant, cccd_hmac)
    WHERE merged_into IS NULL AND cccd_hmac IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_mdm_parcel_ma ON core.mdm_parcel (tenant, ma_dinh_danh_dia_diem)
    WHERE merged_into IS NULL AND ma_dinh_danh_dia_diem IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mdm_parcel_thua ON core.mdm_parcel (tenant, so_thua, to_ban_do) WHERE merged_into IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_mdm_construction_ma ON core.mdm_construction (tenant, ma_cong_trinh)
    WHERE merged_into IS NULL AND ma_cong_trinh IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mdm_link_subject ON core.mdm_dossier_link (tenant, subject_id);
CREATE INDEX IF NOT EXISTS idx_mdm_link_parcel ON core.mdm_dossier_link (tenant, parcel_id);
CREATE INDEX IF NOT EXISTS idx_mdm_link_construction ON core.mdm_dossier_link (tenant, construction_id);
CREATE INDEX IF NOT EXISTS idx_mdm_link_permit ON core.mdm_dossier_link (tenant, permit_id);
CREATE INDEX IF NOT EXISTS idx_mdm_cand_entity ON core.mdm_link_candidate (tenant, entity_type, entity_id, status);

-- RLS: đọc trong phường mình; ghi trong phường mình với vai được tạo liên kết/gộp.
-- API kiểm vai chi tiết hơn (đọc: cán bộ, kiểm toán; gộp: quản trị phường, quản lý dữ liệu).
DO $$
DECLARE
    v_bang text;
BEGIN
    FOREACH v_bang IN ARRAY ARRAY['mdm_subject', 'mdm_parcel', 'mdm_construction', 'mdm_organization',
                                  'mdm_dossier_link', 'mdm_link_candidate', 'mdm_merge_log'] LOOP
        EXECUTE format('ALTER TABLE core.%I ENABLE ROW LEVEL SECURITY', v_bang);
        EXECUTE format('ALTER TABLE core.%I FORCE ROW LEVEL SECURITY', v_bang);
        EXECUTE format('DROP POLICY IF EXISTS rls_%s_read ON core.%I', v_bang, v_bang);
        EXECUTE format(
            'CREATE POLICY rls_%s_read ON core.%I FOR SELECT TO web_user USING (tenant = core.jwt_tenant())',
            v_bang, v_bang);
        EXECUTE format('DROP POLICY IF EXISTS rls_%s_write ON core.%I', v_bang, v_bang);
        EXECUTE format(
            'CREATE POLICY rls_%s_write ON core.%I FOR ALL TO web_user '
            'USING (tenant = core.jwt_tenant() AND core.dh_co_vai(ARRAY[''app:cap-phep:mot-cua'', '
            '''app:cap-phep:tham-dinh'', ''dx:tenant-admin'', ''dx:data-steward''])) '
            'WITH CHECK (tenant = core.jwt_tenant() AND core.dh_co_vai(ARRAY[''app:cap-phep:mot-cua'', '
            '''app:cap-phep:tham-dinh'', ''dx:tenant-admin'', ''dx:data-steward'']))',
            v_bang, v_bang);
        EXECUTE format('DROP POLICY IF EXISTS rls_%s_svc ON core.%I', v_bang, v_bang);
        EXECUTE format(
            'CREATE POLICY rls_%s_svc ON core.%I FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true)',
            v_bang, v_bang);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON core.%I TO web_user', v_bang);
        EXECUTE format('GRANT ALL ON core.%I TO svc, dxos_svc, dxos_owner', v_bang);
    END LOOP;
END $$;

ALTER TABLE core.dh_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.dh_idempotency FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_dh_idempotency_own ON core.dh_idempotency;
CREATE POLICY rls_dh_idempotency_own ON core.dh_idempotency
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant())
    WITH CHECK (tenant = core.jwt_tenant() AND created_by = core.jwt_sub());
DROP POLICY IF EXISTS rls_dh_idempotency_svc ON core.dh_idempotency;
CREATE POLICY rls_dh_idempotency_svc ON core.dh_idempotency
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
GRANT SELECT, INSERT ON core.dh_idempotency TO web_user;
GRANT ALL ON core.dh_idempotency TO svc, dxos_svc, dxos_owner;

-- Bản ghi vàng: chưa bị gộp vào bản khác (D-MDM-03)
CREATE OR REPLACE VIEW core.v_mdm_subject_golden WITH (security_invoker = true) AS
    SELECT * FROM core.mdm_subject WHERE merged_into IS NULL;
CREATE OR REPLACE VIEW core.v_mdm_parcel_golden WITH (security_invoker = true) AS
    SELECT * FROM core.mdm_parcel WHERE merged_into IS NULL;
CREATE OR REPLACE VIEW core.v_mdm_construction_golden WITH (security_invoker = true) AS
    SELECT * FROM core.mdm_construction WHERE merged_into IS NULL;
GRANT SELECT ON core.v_mdm_subject_golden, core.v_mdm_parcel_golden, core.v_mdm_construction_golden
    TO web_user, svc, dxos_svc;

-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 10-planning-schema.sql — Track A: pháp lý, quy hoạch và chỉ tiêu xây dựng.
-- Idempotent: chạy lại nhiều lần không mất dữ liệu.
-- Chạy bằng scripts/migrate.py hoặc khi khởi tạo volume PostgreSQL trống.

CREATE SCHEMA IF NOT EXISTS app_construction AUTHORIZATION dxos_owner;
CREATE SCHEMA IF NOT EXISTS app_construction_private AUTHORIZATION dxos_owner;

REVOKE ALL ON SCHEMA app_construction FROM PUBLIC;
GRANT USAGE ON SCHEMA app_construction TO anon, web_user, svc, dxos_svc, dxos_owner;
REVOKE ALL ON SCHEMA app_construction_private FROM PUBLIC, web_user, anon;
GRANT USAGE ON SCHEMA app_construction_private TO svc, dxos_svc, dxos_owner;

--------------------------------------------------------------------------------
-- 0. Hàm dùng chung
--------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_construction_private.la_can_bo()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = core, public, pg_temp
AS $$
    SELECT core.has_role('app:cap-phep:mot-cua')
        OR core.has_role('app:cap-phep:tham-dinh')
        OR core.has_role('app:cap-phep:lanh-dao')
        OR core.has_role('app:cap-phep:trat-tu-xd')
        OR core.has_role('dx:auditor')
        OR core.has_role('dx:platform-admin');
$$;

CREATE OR REPLACE FUNCTION app_construction_private.la_nguoi_kiem_tra()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = core, public, pg_temp
AS $$
    SELECT core.has_role('app:cap-phep:mot-cua')
        OR core.has_role('app:cap-phep:tham-dinh')
        OR core.has_role('app:cap-phep:lanh-dao')
        OR core.has_role('dx:platform-admin');
$$;

CREATE OR REPLACE FUNCTION app_construction_private.la_nguoi_cap_nhat()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = core, public, pg_temp
AS $$
    SELECT app_construction_private.la_nguoi_kiem_tra()
        OR core.has_role('app:cap-phep:trat-tu-xd')
        OR core.has_role('dx:auditor');
$$;

-- Kiểm tra hồ sơ thuộc chủ đầu tư hiện tại mà không phụ thuộc cứng vào schema app_cap_phep
-- (volume trống có thể chạy migration lõi trước khi cài gói ứng dụng).
CREATE OR REPLACE FUNCTION app_construction_private.la_chu_ho_so(p_ho_so_id uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = core, public, pg_temp
AS $$
DECLARE
    v_ok boolean := false;
BEGIN
    IF p_ho_so_id IS NULL THEN
        RETURN false;
    END IF;
    BEGIN
        EXECUTE
            'SELECT EXISTS (SELECT 1 FROM app_cap_phep.ho_so '
            'WHERE id = $1 AND tenant = core.jwt_tenant() AND chu_dau_tu_sub = core.jwt_sub())'
        INTO v_ok
        USING p_ho_so_id;
    EXCEPTION WHEN undefined_table THEN
        RETURN false;
    END;
    RETURN coalesce(v_ok, false);
END;
$$;

-- Trigger audit chung: mọi thay đổi đều vào chuỗi băm core.audit_log.
CREATE OR REPLACE FUNCTION app_construction_private.trg_audit()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, public, pg_temp
AS $$
DECLARE
    v_row jsonb;
    v_tenant text;
    v_id text;
    v_actor text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_row := to_jsonb(OLD);
    ELSE
        v_row := to_jsonb(NEW);
    END IF;

    v_tenant := COALESCE(v_row->>'tenant', core.jwt_tenant());
    v_id := COALESCE(v_row->>'id', v_row->>'document_id', v_row->>'citation_key');
    v_actor := COALESCE(NULLIF(core.jwt_sub(), ''), 'service');

    PERFORM core.record_audit(
        v_tenant,
        v_actor,
        CASE WHEN core.jwt_sub() = '' THEN 'service' ELSE 'user' END,
        TG_TABLE_NAME || '.' || lower(TG_OP),
        TG_TABLE_NAME,
        v_id,
        jsonb_build_object(
            'schema', TG_TABLE_SCHEMA,
            'operation', TG_OP,
            'row', v_row
        )
    );
    RETURN COALESCE(NEW, OLD);
END;
$$;

--------------------------------------------------------------------------------
-- 1. Kho văn bản pháp luật và trích dẫn (A-LEGAL-01)
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_construction.legal_refs (
    document_id text PRIMARY KEY,
    code text NOT NULL,
    title text NOT NULL,
    doc_type text,
    issuer text,
    issued_date date,
    effective_date date,
    status text NOT NULL DEFAULT 'can_doi_chieu',
    status_detail text,
    group_name text,
    source_url text,
    sha256 text,
    file_name text,
    notes text,
    tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_legal_refs_code ON app_construction.legal_refs (code);
CREATE INDEX IF NOT EXISTS idx_legal_refs_status ON app_construction.legal_refs (status);

CREATE TABLE IF NOT EXISTS app_construction.legal_citations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    citation_key text NOT NULL UNIQUE,
    document_id text NOT NULL REFERENCES app_construction.legal_refs(document_id) ON DELETE CASCADE,
    article text NOT NULL,
    clause text,
    point text,
    topic text NOT NULL,
    summary text NOT NULL,
    effective_date date,
    status text NOT NULL DEFAULT 'can_doi_chieu',
    source_url text,
    sha256 text,
    can_doi_chieu boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, article, clause, point, topic)
);

CREATE INDEX IF NOT EXISTS idx_legal_citations_topic ON app_construction.legal_citations (topic);
CREATE INDEX IF NOT EXISTS idx_legal_citations_document ON app_construction.legal_citations (document_id);

--------------------------------------------------------------------------------
-- 2. Dữ liệu quy hoạch (A-PLAN-01)
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_construction.thua_dat (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ma_thua_dat text NOT NULL,
    so_thua text NOT NULL,
    to_ban_do text,
    dia_chi text NOT NULL,
    dien_tich_m2 double precision NOT NULL DEFAULT 0,
    loai_dat text NOT NULL DEFAULT 'dat_o',
    ma_dinh_danh_dia_diem text,
    geom jsonb,
    status text NOT NULL DEFAULT 'hieu_luc',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by text,
    UNIQUE (tenant, ma_thua_dat),
    CONSTRAINT chk_thua_dat_ma_dinh_danh
        CHECK (ma_dinh_danh_dia_diem IS NULL OR ma_dinh_danh_dia_diem ~ '^[0-9]{12}$')
);

CREATE INDEX IF NOT EXISTS idx_thua_dat_tenant ON app_construction.thua_dat (tenant, status);

CREATE TABLE IF NOT EXISTS app_construction.quy_hoach_zone (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ma_zone text NOT NULL,
    ten text NOT NULL,
    loai_zone text NOT NULL DEFAULT 'o_do_thi',
    mo_ta text,
    dien_tich_ha double precision,
    geom jsonb NOT NULL,
    status text NOT NULL DEFAULT 'hieu_luc',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by text,
    UNIQUE (tenant, ma_zone),
    CONSTRAINT chk_quy_hoach_zone_loai CHECK (
        loai_zone IN ('o_do_thi', 'dan_cu', 'cong_vien', 'hanh_lang_giao_thong', 'cam_xay_dung', 'khac')
    )
);

CREATE INDEX IF NOT EXISTS idx_quy_hoach_zone_tenant ON app_construction.quy_hoach_zone (tenant, loai_zone);

CREATE TABLE IF NOT EXISTS app_construction.chi_tieu_quy_hoach (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    zone_id uuid NOT NULL REFERENCES app_construction.quy_hoach_zone(id) ON DELETE CASCADE,
    chi_tieu text NOT NULL,
    ten text NOT NULL,
    gia_tri_min double precision,
    gia_tri_max double precision,
    don_vi text,
    bat_buoc boolean NOT NULL DEFAULT true,
    legal_citation_key text,
    status text NOT NULL DEFAULT 'hieu_luc',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by text,
    UNIQUE (tenant, zone_id, chi_tieu),
    CONSTRAINT chk_chi_tieu_gia_tri CHECK (
        gia_tri_min IS NULL OR gia_tri_max IS NULL OR gia_tri_min <= gia_tri_max
    )
);

CREATE INDEX IF NOT EXISTS idx_chi_tieu_quy_hoach_zone ON app_construction.chi_tieu_quy_hoach (zone_id);

CREATE TABLE IF NOT EXISTS app_construction.quy_hoach_van_ban (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ma_van_ban text NOT NULL,
    ten text NOT NULL,
    co_quan_ban_hanh text,
    ngay_ban_hanh date,
    ngay_hieu_luc date,
    file_url text,
    legal_document_id text REFERENCES app_construction.legal_refs(document_id),
    status text NOT NULL DEFAULT 'hieu_luc',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by text,
    UNIQUE (tenant, ma_van_ban)
);

CREATE INDEX IF NOT EXISTS idx_quy_hoach_van_ban_tenant ON app_construction.quy_hoach_van_ban (tenant);

CREATE TABLE IF NOT EXISTS app_construction.ket_qua_kiem_tra_quy_hoach (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ho_so_id uuid,
    thua_dat_id uuid REFERENCES app_construction.thua_dat(id),
    zone_id uuid REFERENCES app_construction.quy_hoach_zone(id),
    proposal jsonb NOT NULL DEFAULT '{}'::jsonb,
    ket_qua jsonb NOT NULL DEFAULT '[]'::jsonb,
    pass boolean NOT NULL DEFAULT false,
    so_loi integer NOT NULL DEFAULT 0,
    so_canh_bao integer NOT NULL DEFAULT 0,
    nguoi_kiem_tra text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ket_qua_quy_hoach_ho_so
    ON app_construction.ket_qua_kiem_tra_quy_hoach (tenant, ho_so_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ket_qua_quy_hoach_thua_dat
    ON app_construction.ket_qua_kiem_tra_quy_hoach (tenant, thua_dat_id, created_at DESC);

-- Danh mục địa điểm định danh 12 chữ số (A-LEGAL-05).
-- Nguồn dữ liệu tổng hợp cho demo, không phải CSDL định danh địa điểm thật.
CREATE TABLE IF NOT EXISTS app_construction.dia_diem_dinh_danh (
    ma_dinh_danh_dia_diem text PRIMARY KEY,
    tenant text NOT NULL,
    dia_chi text NOT NULL,
    so_thua text,
    to_ban_do text,
    dien_tich_m2 double precision,
    loai_dat text,
    nguon text NOT NULL DEFAULT 'demo_tong_hop',
    da_kiem_chung boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_dia_diem_ma_12 CHECK (ma_dinh_danh_dia_diem ~ '^[0-9]{12}$')
);

CREATE INDEX IF NOT EXISTS idx_dia_diem_tenant ON app_construction.dia_diem_dinh_danh (tenant);

-- Nhật ký khai thác/chia sẻ dữ liệu (A-LEGAL-05, A-LEGAL-06).
CREATE TABLE IF NOT EXISTS app_construction.chia_se_du_lieu_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    loai_du_lieu text NOT NULL,
    ma_dinh_danh_dia_diem text,
    ho_so_id uuid,
    ben_nhan text NOT NULL,
    can_cu_phap_ly text NOT NULL DEFAULT 'ND-49/2025/ND-CP',
    trang_thai text NOT NULL DEFAULT 'da_ghi_nhan',
    chi_tiet jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chia_se_tenant ON app_construction.chia_se_du_lieu_log (tenant, created_at DESC);

--------------------------------------------------------------------------------
-- 3. RLS + quyền
--------------------------------------------------------------------------------
ALTER TABLE app_construction.legal_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.legal_refs FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.legal_citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.legal_citations FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.thua_dat ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.thua_dat FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.quy_hoach_zone ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.quy_hoach_zone FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.chi_tieu_quy_hoach ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.chi_tieu_quy_hoach FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.quy_hoach_van_ban ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.quy_hoach_van_ban FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.ket_qua_kiem_tra_quy_hoach ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.ket_qua_kiem_tra_quy_hoach FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.dia_diem_dinh_danh ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.dia_diem_dinh_danh FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.chia_se_du_lieu_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.chia_se_du_lieu_log FORCE ROW LEVEL SECURITY;

-- Văn bản pháp luật và trích dẫn là dữ liệu tham chiếu dùng chung: mọi người dùng đọc được.
DROP POLICY IF EXISTS rls_legal_refs_read ON app_construction.legal_refs;
CREATE POLICY rls_legal_refs_read ON app_construction.legal_refs
    FOR SELECT TO web_user, anon USING (true);
DROP POLICY IF EXISTS rls_legal_refs_svc ON app_construction.legal_refs;
CREATE POLICY rls_legal_refs_svc ON app_construction.legal_refs
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_legal_citations_read ON app_construction.legal_citations;
CREATE POLICY rls_legal_citations_read ON app_construction.legal_citations
    FOR SELECT TO web_user, anon USING (true);
DROP POLICY IF EXISTS rls_legal_citations_svc ON app_construction.legal_citations;
CREATE POLICY rls_legal_citations_svc ON app_construction.legal_citations
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_thua_dat_read ON app_construction.thua_dat;
CREATE POLICY rls_thua_dat_read ON app_construction.thua_dat
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_can_bo());
DROP POLICY IF EXISTS rls_thua_dat_write ON app_construction.thua_dat;
CREATE POLICY rls_thua_dat_write ON app_construction.thua_dat
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_cap_nhat())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_cap_nhat());
DROP POLICY IF EXISTS rls_thua_dat_svc ON app_construction.thua_dat;
CREATE POLICY rls_thua_dat_svc ON app_construction.thua_dat
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_zone_read ON app_construction.quy_hoach_zone;
CREATE POLICY rls_zone_read ON app_construction.quy_hoach_zone
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_can_bo());
DROP POLICY IF EXISTS rls_zone_write ON app_construction.quy_hoach_zone;
CREATE POLICY rls_zone_write ON app_construction.quy_hoach_zone
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_cap_nhat())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_cap_nhat());
DROP POLICY IF EXISTS rls_zone_svc ON app_construction.quy_hoach_zone;
CREATE POLICY rls_zone_svc ON app_construction.quy_hoach_zone
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_chi_tieu_read ON app_construction.chi_tieu_quy_hoach;
CREATE POLICY rls_chi_tieu_read ON app_construction.chi_tieu_quy_hoach
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_can_bo());
DROP POLICY IF EXISTS rls_chi_tieu_write ON app_construction.chi_tieu_quy_hoach;
CREATE POLICY rls_chi_tieu_write ON app_construction.chi_tieu_quy_hoach
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_cap_nhat())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_cap_nhat());
DROP POLICY IF EXISTS rls_chi_tieu_svc ON app_construction.chi_tieu_quy_hoach;
CREATE POLICY rls_chi_tieu_svc ON app_construction.chi_tieu_quy_hoach
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_qh_van_ban_read ON app_construction.quy_hoach_van_ban;
CREATE POLICY rls_qh_van_ban_read ON app_construction.quy_hoach_van_ban
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_can_bo());
DROP POLICY IF EXISTS rls_qh_van_ban_write ON app_construction.quy_hoach_van_ban;
CREATE POLICY rls_qh_van_ban_write ON app_construction.quy_hoach_van_ban
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_cap_nhat())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_cap_nhat());
DROP POLICY IF EXISTS rls_qh_van_ban_svc ON app_construction.quy_hoach_van_ban;
CREATE POLICY rls_qh_van_ban_svc ON app_construction.quy_hoach_van_ban
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_ket_qua_read ON app_construction.ket_qua_kiem_tra_quy_hoach;
CREATE POLICY rls_ket_qua_read ON app_construction.ket_qua_kiem_tra_quy_hoach
    FOR SELECT TO web_user
    USING (
        tenant = core.jwt_tenant()
        AND (
            app_construction_private.la_can_bo()
            OR ho_so_id IS NULL
            OR app_construction_private.la_chu_ho_so(ho_so_id)
        )
    );
DROP POLICY IF EXISTS rls_ket_qua_insert ON app_construction.ket_qua_kiem_tra_quy_hoach;
CREATE POLICY rls_ket_qua_insert ON app_construction.ket_qua_kiem_tra_quy_hoach
    FOR INSERT TO web_user
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra());
DROP POLICY IF EXISTS rls_ket_qua_svc ON app_construction.ket_qua_kiem_tra_quy_hoach;
CREATE POLICY rls_ket_qua_svc ON app_construction.ket_qua_kiem_tra_quy_hoach
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_dia_diem_read ON app_construction.dia_diem_dinh_danh;
CREATE POLICY rls_dia_diem_read ON app_construction.dia_diem_dinh_danh
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant());
DROP POLICY IF EXISTS rls_dia_diem_svc ON app_construction.dia_diem_dinh_danh;
CREATE POLICY rls_dia_diem_svc ON app_construction.dia_diem_dinh_danh
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_chia_se_read ON app_construction.chia_se_du_lieu_log;
CREATE POLICY rls_chia_se_read ON app_construction.chia_se_du_lieu_log
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra());
DROP POLICY IF EXISTS rls_chia_se_insert ON app_construction.chia_se_du_lieu_log;
CREATE POLICY rls_chia_se_insert ON app_construction.chia_se_du_lieu_log
    FOR INSERT TO web_user
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra());
DROP POLICY IF EXISTS rls_chia_se_svc ON app_construction.chia_se_du_lieu_log;
CREATE POLICY rls_chia_se_svc ON app_construction.chia_se_du_lieu_log
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

GRANT SELECT ON app_construction.legal_refs, app_construction.legal_citations TO web_user, anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    app_construction.thua_dat,
    app_construction.quy_hoach_zone,
    app_construction.chi_tieu_quy_hoach,
    app_construction.quy_hoach_van_ban,
    app_construction.ket_qua_kiem_tra_quy_hoach,
    app_construction.dia_diem_dinh_danh,
    app_construction.chia_se_du_lieu_log
TO web_user;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    app_construction.legal_refs,
    app_construction.legal_citations,
    app_construction.thua_dat,
    app_construction.quy_hoach_zone,
    app_construction.chi_tieu_quy_hoach,
    app_construction.quy_hoach_van_ban,
    app_construction.ket_qua_kiem_tra_quy_hoach,
    app_construction.dia_diem_dinh_danh,
    app_construction.chia_se_du_lieu_log
TO svc, dxos_svc, dxos_owner;

GRANT EXECUTE ON FUNCTION app_construction_private.la_can_bo() TO web_user, svc, dxos_svc;
GRANT EXECUTE ON FUNCTION app_construction_private.la_nguoi_kiem_tra() TO web_user, svc, dxos_svc;
GRANT EXECUTE ON FUNCTION app_construction_private.la_nguoi_cap_nhat() TO web_user, svc, dxos_svc;
GRANT EXECUTE ON FUNCTION app_construction_private.la_chu_ho_so(uuid) TO web_user, svc, dxos_svc;

--------------------------------------------------------------------------------
-- 4. Trigger audit (sau khi bảng đã tồn tại)
--------------------------------------------------------------------------------
DO $$
DECLARE
    v_table text;
BEGIN
    FOREACH v_table IN ARRAY ARRAY[
        'thua_dat', 'quy_hoach_zone', 'chi_tieu_quy_hoach', 'quy_hoach_van_ban',
        'ket_qua_kiem_tra_quy_hoach', 'dia_diem_dinh_danh', 'chia_se_du_lieu_log'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_audit_%I ON app_construction.%I', v_table, v_table);
        EXECUTE format(
            'CREATE TRIGGER trg_audit_%I AFTER INSERT OR UPDATE OR DELETE ON app_construction.%I '
            'FOR EACH ROW EXECUTE FUNCTION app_construction_private.trg_audit()',
            v_table, v_table
        );
    END LOOP;
END $$;

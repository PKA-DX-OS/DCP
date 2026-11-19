-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 12-legal-backend-schema.sql — Track A: thẩm quyền, phí/lệ phí, lưu trữ.
-- Idempotent: chạy lại nhiều lần không mất dữ liệu.

CREATE SCHEMA IF NOT EXISTS app_construction AUTHORIZATION dxos_owner;
CREATE SCHEMA IF NOT EXISTS app_construction_private AUTHORIZATION dxos_owner;

--------------------------------------------------------------------------------
-- 1. Ma trận thẩm quyền theo Điều 53 NĐ 217/2026 (A-LEGAL-04)
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_construction.tham_quyen_cap_phep (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    loai_cong_trinh text NOT NULL,
    cap_cong_trinh text,
    doi_tuong text,
    trong_kcn boolean NOT NULL DEFAULT false,
    cap_hanh_chinh text,
    co_quan_cap text NOT NULL,
    nguoi_ky text,
    legal_citation_key text,
    uu_tien integer NOT NULL DEFAULT 100,
    status text NOT NULL DEFAULT 'hieu_luc',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (loai_cong_trinh, cap_cong_trinh, doi_tuong, trong_kcn, cap_hanh_chinh)
);

CREATE INDEX IF NOT EXISTS idx_tham_quyen_lookup
    ON app_construction.tham_quyen_cap_phep (loai_cong_trinh, doi_tuong, trong_kcn, status);

-- Hàm xác định thẩm quyền thuần logic, dùng được cho test và API.
CREATE OR REPLACE FUNCTION app_construction_private.xac_dinh_tham_quyen(
    p_loai_cong_trinh text,
    p_cap_cong_trinh text DEFAULT NULL,
    p_doi_tuong text DEFAULT 'ho_gia_dinh_ca_nhan',
    p_trong_kcn boolean DEFAULT false,
    p_cap_hanh_chinh text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SET search_path = app_construction, app_construction_private, pg_catalog
AS $$
DECLARE
    v_row app_construction.tham_quyen_cap_phep%ROWTYPE;
    v_doi_tuong text := COALESCE(NULLIF(p_doi_tuong, ''), 'ho_gia_dinh_ca_nhan');
    v_cap text := NULLIF(p_cap_cong_trinh, '');
    v_cap_hanh_chinh text := NULLIF(p_cap_hanh_chinh, '');
BEGIN
    IF v_doi_tuong = 'ho_gia_dinh_ca_nhan' THEN
        SELECT * INTO v_row
        FROM app_construction.tham_quyen_cap_phep
        WHERE status = 'hieu_luc'
          AND doi_tuong = v_doi_tuong
          AND trong_kcn = p_trong_kcn
          AND (cap_hanh_chinh IS NULL OR cap_hanh_chinh = v_cap_hanh_chinh)
        ORDER BY uu_tien ASC, cap_cong_trinh NULLS FIRST
        LIMIT 1;
    ELSE
        SELECT * INTO v_row
        FROM app_construction.tham_quyen_cap_phep
        WHERE status = 'hieu_luc'
          AND doi_tuong IN ('tat_ca', v_doi_tuong)
          AND trong_kcn = p_trong_kcn
          AND (v_cap IS NULL OR cap_cong_trinh IS NULL OR cap_cong_trinh = v_cap)
          AND (cap_hanh_chinh IS NULL OR cap_hanh_chinh = v_cap_hanh_chinh)
        ORDER BY uu_tien ASC, cap_cong_trinh NULLS LAST
        LIMIT 1;
    END IF;

    IF v_row.id IS NULL THEN
        RETURN jsonb_build_object(
            'xac_dinh_duoc', false,
            'ly_do', 'Chưa có quy tắc thẩm quyền phù hợp; cần đối chiếu quyết định công bố TTHC của địa phương.',
            'doi_tuong', v_doi_tuong,
            'cap_cong_trinh', v_cap,
            'trong_kcn', p_trong_kcn
        );
    END IF;

    RETURN jsonb_build_object(
        'xac_dinh_duoc', true,
        'co_quan_cap', v_row.co_quan_cap,
        'nguoi_ky', v_row.nguoi_ky,
        'legal_citation_key', v_row.legal_citation_key,
        'doi_tuong', v_doi_tuong,
        'cap_cong_trinh', v_cap,
        'trong_kcn', p_trong_kcn
    );
END;
$$;

GRANT EXECUTE ON FUNCTION app_construction_private.xac_dinh_tham_quyen(text, text, text, boolean, text)
    TO web_user, svc, dxos_svc;

--------------------------------------------------------------------------------
-- 2. Phí, lệ phí (A-LEGAL-07, backend; UI do Track B)
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_construction.bieu_phi_dia_phuong (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ten_thu_tuc text NOT NULL,
    don_vi_tinh text NOT NULL DEFAULT 'hồ sơ',
    muc_phi numeric(14, 2) NOT NULL,
    don_vi_tien text NOT NULL DEFAULT 'VND',
    can_cu text,
    hieu_luc_tu date,
    hieu_luc_den date,
    status text NOT NULL DEFAULT 'cho_van_ban_dia_phuong',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant, ten_thu_tuc, hieu_luc_tu)
);

CREATE INDEX IF NOT EXISTS idx_bieu_phi_tenant ON app_construction.bieu_phi_dia_phuong (tenant, status);

CREATE TABLE IF NOT EXISTS app_construction.bien_lai_phi (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ho_so_id uuid,
    so_bien_lai text,
    so_tien numeric(14, 2) NOT NULL DEFAULT 0,
    don_vi_tien text NOT NULL DEFAULT 'VND',
    trang_thai text NOT NULL DEFAULT 'cho_doi_soat',
    ngay_thu timestamptz,
    nguoi_thu text,
    ma_tham_chieu text,
    ghi_chu text,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text,
    UNIQUE (tenant, so_bien_lai),
    CONSTRAINT chk_bien_lai_trang_thai CHECK (trang_thai IN ('cho_doi_soat', 'da_doi_soat', 'hoan_phi', 'huy'))
);

CREATE INDEX IF NOT EXISTS idx_bien_lai_ho_so ON app_construction.bien_lai_phi (tenant, ho_so_id);

--------------------------------------------------------------------------------
-- 3. Lưu trữ hồ sơ theo Luật Lưu trữ 33/2024 (A-LEGAL-07)
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_construction.chinh_sach_luu_tru (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    nhom_ho_so text NOT NULL,
    thoi_han_nam integer,
    hinh_thuc_luu_tru text NOT NULL DEFAULT 'dien_tu',
    can_cu text NOT NULL DEFAULT 'Luật Lưu trữ 33/2024/QH15',
    status text NOT NULL DEFAULT 'cho_van_ban_dia_phuong',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant, nhom_ho_so)
);

CREATE TABLE IF NOT EXISTS app_construction.luu_tru_ho_so (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ho_so_id uuid NOT NULL,
    nhom_ho_so text NOT NULL DEFAULT 'cap_phep_xay_dung',
    thoi_han_den date,
    trang_thai text NOT NULL DEFAULT 'dang_luu_tru',
    file_id uuid,
    ghi_chu text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant, ho_so_id, nhom_ho_so),
    CONSTRAINT chk_luu_tru_trang_thai CHECK (trang_thai IN ('dang_luu_tru', 'chuyen_giao', 'tieu_huy', 'het_han'))
);

CREATE INDEX IF NOT EXISTS idx_luu_tru_ho_so ON app_construction.luu_tru_ho_so (tenant, ho_so_id);

--------------------------------------------------------------------------------
-- 4. RLS + quyền
--------------------------------------------------------------------------------
ALTER TABLE app_construction.tham_quyen_cap_phep ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.tham_quyen_cap_phep FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.bieu_phi_dia_phuong ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.bieu_phi_dia_phuong FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.bien_lai_phi ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.bien_lai_phi FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.chinh_sach_luu_tru ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.chinh_sach_luu_tru FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.luu_tru_ho_so ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.luu_tru_ho_so FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_tham_quyen_read ON app_construction.tham_quyen_cap_phep;
CREATE POLICY rls_tham_quyen_read ON app_construction.tham_quyen_cap_phep
    FOR SELECT TO web_user USING (true);
DROP POLICY IF EXISTS rls_tham_quyen_svc ON app_construction.tham_quyen_cap_phep;
CREATE POLICY rls_tham_quyen_svc ON app_construction.tham_quyen_cap_phep
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_bieu_phi_read ON app_construction.bieu_phi_dia_phuong;
CREATE POLICY rls_bieu_phi_read ON app_construction.bieu_phi_dia_phuong
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_can_bo());
DROP POLICY IF EXISTS rls_bieu_phi_write ON app_construction.bieu_phi_dia_phuong;
CREATE POLICY rls_bieu_phi_write ON app_construction.bieu_phi_dia_phuong
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra());
DROP POLICY IF EXISTS rls_bieu_phi_svc ON app_construction.bieu_phi_dia_phuong;
CREATE POLICY rls_bieu_phi_svc ON app_construction.bieu_phi_dia_phuong
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_bien_lai_read ON app_construction.bien_lai_phi;
CREATE POLICY rls_bien_lai_read ON app_construction.bien_lai_phi
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_can_bo());
DROP POLICY IF EXISTS rls_bien_lai_write ON app_construction.bien_lai_phi;
CREATE POLICY rls_bien_lai_write ON app_construction.bien_lai_phi
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra());
DROP POLICY IF EXISTS rls_bien_lai_svc ON app_construction.bien_lai_phi;
CREATE POLICY rls_bien_lai_svc ON app_construction.bien_lai_phi
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_chinh_sach_read ON app_construction.chinh_sach_luu_tru;
CREATE POLICY rls_chinh_sach_read ON app_construction.chinh_sach_luu_tru
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_can_bo());
DROP POLICY IF EXISTS rls_chinh_sach_write ON app_construction.chinh_sach_luu_tru;
CREATE POLICY rls_chinh_sach_write ON app_construction.chinh_sach_luu_tru
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra());
DROP POLICY IF EXISTS rls_chinh_sach_svc ON app_construction.chinh_sach_luu_tru;
CREATE POLICY rls_chinh_sach_svc ON app_construction.chinh_sach_luu_tru
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_luu_tru_read ON app_construction.luu_tru_ho_so;
CREATE POLICY rls_luu_tru_read ON app_construction.luu_tru_ho_so
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_can_bo());
DROP POLICY IF EXISTS rls_luu_tru_write ON app_construction.luu_tru_ho_so;
CREATE POLICY rls_luu_tru_write ON app_construction.luu_tru_ho_so
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra());
DROP POLICY IF EXISTS rls_luu_tru_svc ON app_construction.luu_tru_ho_so;
CREATE POLICY rls_luu_tru_svc ON app_construction.luu_tru_ho_so
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

GRANT SELECT ON app_construction.tham_quyen_cap_phep TO web_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    app_construction.bieu_phi_dia_phuong,
    app_construction.bien_lai_phi,
    app_construction.chinh_sach_luu_tru,
    app_construction.luu_tru_ho_so
TO web_user;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    app_construction.tham_quyen_cap_phep,
    app_construction.bieu_phi_dia_phuong,
    app_construction.bien_lai_phi,
    app_construction.chinh_sach_luu_tru,
    app_construction.luu_tru_ho_so
TO svc, dxos_svc, dxos_owner;

DO $$
DECLARE
    v_table text;
BEGIN
    FOREACH v_table IN ARRAY ARRAY[
        'tham_quyen_cap_phep', 'bieu_phi_dia_phuong', 'bien_lai_phi',
        'chinh_sach_luu_tru', 'luu_tru_ho_so'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_audit_%I ON app_construction.%I', v_table, v_table);
        EXECUTE format(
            'CREATE TRIGGER trg_audit_%I AFTER INSERT OR UPDATE OR DELETE ON app_construction.%I '
            'FOR EACH ROW EXECUTE FUNCTION app_construction_private.trg_audit()',
            v_table, v_table
        );
    END LOOP;
END $$;

-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 11-acceptance-schema.sql — Track A: nghiệm thu, hoàn công (5.5).
-- Idempotent: chạy lại nhiều lần không mất dữ liệu.

CREATE SCHEMA IF NOT EXISTS app_construction AUTHORIZATION dxos_owner;
CREATE SCHEMA IF NOT EXISTS app_construction_private AUTHORIZATION dxos_owner;

CREATE TABLE IF NOT EXISTS app_construction.moc_nghiem_thu (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ho_so_id uuid NOT NULL,
    loai_moc text NOT NULL,
    version integer NOT NULL DEFAULT 1,
    ngay_nghiem_thu date,
    ket_qua text NOT NULL DEFAULT 'cho_nghiem_thu',
    nguoi_thuc_hien text,
    ghi_chu text,
    file_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by text,
    UNIQUE (tenant, ho_so_id, loai_moc, version),
    CONSTRAINT chk_moc_loai CHECK (loai_moc IN ('mong', 'ket_cau', 'hoan_thien', 'hoan_cong')),
    CONSTRAINT chk_moc_ket_qua CHECK (ket_qua IN ('cho_nghiem_thu', 'dat', 'khong_dat'))
);

CREATE INDEX IF NOT EXISTS idx_moc_nghiem_thu_ho_so
    ON app_construction.moc_nghiem_thu (tenant, ho_so_id, created_at);

CREATE TABLE IF NOT EXISTS app_construction.bien_ban_nghiem_thu (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    moc_id uuid NOT NULL REFERENCES app_construction.moc_nghiem_thu(id) ON DELETE CASCADE,
    so_bien_ban text NOT NULL,
    ket_luan text NOT NULL,
    file_id uuid,
    chu_ky text,
    ngay_ky timestamptz,
    nguoi_ky text,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text,
    UNIQUE (tenant, so_bien_ban)
);

CREATE INDEX IF NOT EXISTS idx_bien_ban_moc ON app_construction.bien_ban_nghiem_thu (moc_id);

CREATE TABLE IF NOT EXISTS app_construction.ban_ve_hoan_cong (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ho_so_id uuid NOT NULL,
    file_id uuid NOT NULL,
    version integer NOT NULL DEFAULT 1,
    ngay_nop timestamptz NOT NULL DEFAULT now(),
    nguoi_nop text,
    trang_thai text NOT NULL DEFAULT 'cho_kiem_tra',
    ghi_chu text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant, ho_so_id, version),
    CONSTRAINT chk_ban_ve_trang_thai CHECK (trang_thai IN ('cho_kiem_tra', 'dat', 'khong_dat'))
);

CREATE INDEX IF NOT EXISTS idx_ban_ve_hoan_cong_ho_so
    ON app_construction.ban_ve_hoan_cong (tenant, ho_so_id, version DESC);

ALTER TABLE app_construction.moc_nghiem_thu ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.moc_nghiem_thu FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.bien_ban_nghiem_thu ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.bien_ban_nghiem_thu FORCE ROW LEVEL SECURITY;
ALTER TABLE app_construction.ban_ve_hoan_cong ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_construction.ban_ve_hoan_cong FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_moc_read ON app_construction.moc_nghiem_thu;
CREATE POLICY rls_moc_read ON app_construction.moc_nghiem_thu
    FOR SELECT TO web_user
    USING (
        tenant = core.jwt_tenant()
        AND (
            app_construction_private.la_can_bo()
            OR app_construction_private.la_chu_ho_so(ho_so_id)
        )
    );
DROP POLICY IF EXISTS rls_moc_write ON app_construction.moc_nghiem_thu;
CREATE POLICY rls_moc_write ON app_construction.moc_nghiem_thu
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra());
DROP POLICY IF EXISTS rls_moc_svc ON app_construction.moc_nghiem_thu;
CREATE POLICY rls_moc_svc ON app_construction.moc_nghiem_thu
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_bien_ban_read ON app_construction.bien_ban_nghiem_thu;
CREATE POLICY rls_bien_ban_read ON app_construction.bien_ban_nghiem_thu
    FOR SELECT TO web_user
    USING (
        tenant = core.jwt_tenant()
        AND (
            app_construction_private.la_can_bo()
            OR EXISTS (
                SELECT 1 FROM app_construction.moc_nghiem_thu m
                WHERE m.id = moc_id
                  AND m.tenant = core.jwt_tenant()
                  AND app_construction_private.la_chu_ho_so(m.ho_so_id)
            )
        )
    );
DROP POLICY IF EXISTS rls_bien_ban_write ON app_construction.bien_ban_nghiem_thu;
CREATE POLICY rls_bien_ban_write ON app_construction.bien_ban_nghiem_thu
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra());
DROP POLICY IF EXISTS rls_bien_ban_svc ON app_construction.bien_ban_nghiem_thu;
CREATE POLICY rls_bien_ban_svc ON app_construction.bien_ban_nghiem_thu
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_ban_ve_read ON app_construction.ban_ve_hoan_cong;
CREATE POLICY rls_ban_ve_read ON app_construction.ban_ve_hoan_cong
    FOR SELECT TO web_user
    USING (
        tenant = core.jwt_tenant()
        AND (
            app_construction_private.la_can_bo()
            OR app_construction_private.la_chu_ho_so(ho_so_id)
        )
    );
DROP POLICY IF EXISTS rls_ban_ve_write ON app_construction.ban_ve_hoan_cong;
CREATE POLICY rls_ban_ve_write ON app_construction.ban_ve_hoan_cong
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_kiem_tra());
DROP POLICY IF EXISTS rls_ban_ve_svc ON app_construction.ban_ve_hoan_cong;
CREATE POLICY rls_ban_ve_svc ON app_construction.ban_ve_hoan_cong
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    app_construction.moc_nghiem_thu,
    app_construction.bien_ban_nghiem_thu,
    app_construction.ban_ve_hoan_cong
TO web_user;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    app_construction.moc_nghiem_thu,
    app_construction.bien_ban_nghiem_thu,
    app_construction.ban_ve_hoan_cong
TO svc, dxos_svc, dxos_owner;

DO $$
DECLARE
    v_table text;
BEGIN
    FOREACH v_table IN ARRAY ARRAY['moc_nghiem_thu', 'bien_ban_nghiem_thu', 'ban_ve_hoan_cong'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_audit_%I ON app_construction.%I', v_table, v_table);
        EXECUTE format(
            'CREATE TRIGGER trg_audit_%I AFTER INSERT OR UPDATE OR DELETE ON app_construction.%I '
            'FOR EACH ROW EXECUTE FUNCTION app_construction_private.trg_audit()',
            v_table, v_table
        );
    END LOOP;
END $$;

-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 17-nghiem-thu-trat-tu.sql — cán bộ trật tự xây dựng được ghi mốc nghiệm thu,
-- biên bản và bản vẽ hoàn công (BPMN giao việc nghiệm thu cho nhóm trat-tu-xd).
-- Idempotent.

CREATE OR REPLACE FUNCTION app_construction_private.la_nguoi_nghiem_thu()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = core, public, pg_temp
AS $$
    SELECT app_construction_private.la_nguoi_kiem_tra()
        OR core.has_role('app:cap-phep:trat-tu-xd');
$$;

REVOKE ALL ON FUNCTION app_construction_private.la_nguoi_nghiem_thu() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_construction_private.la_nguoi_nghiem_thu() TO web_user, svc, dxos_svc;

DROP POLICY IF EXISTS rls_moc_write ON app_construction.moc_nghiem_thu;
CREATE POLICY rls_moc_write ON app_construction.moc_nghiem_thu
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_nghiem_thu())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_nghiem_thu());

DROP POLICY IF EXISTS rls_bien_ban_write ON app_construction.bien_ban_nghiem_thu;
CREATE POLICY rls_bien_ban_write ON app_construction.bien_ban_nghiem_thu
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_nghiem_thu())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_nghiem_thu());

DROP POLICY IF EXISTS rls_ban_ve_write ON app_construction.ban_ve_hoan_cong;
CREATE POLICY rls_ban_ve_write ON app_construction.ban_ve_hoan_cong
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_nghiem_thu())
    WITH CHECK (tenant = core.jwt_tenant() AND app_construction_private.la_nguoi_nghiem_thu());

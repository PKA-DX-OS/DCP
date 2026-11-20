-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 16-tenant-directory.sql — danh mục phường/địa bàn cho quản trị nền tảng.
-- Idempotent. Chạy sau 15-fix-share-citation.sql.

CREATE TABLE IF NOT EXISTS core.tenants (
    tenant text PRIMARY KEY,
    ten text NOT NULL,
    ma_dvhc text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text
);

-- Tên hiển thị do lớp ứng dụng cập nhật trong migration riêng;
-- lõi chỉ tạo danh mục từ các tenant đã có trong danh bạ người dùng.
INSERT INTO core.tenants (tenant, ten, ma_dvhc)
SELECT DISTINCT tenant, tenant, NULL
FROM core.users_directory
ON CONFLICT (tenant) DO NOTHING;

ALTER TABLE core.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.tenants FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_tenants_read ON core.tenants;
CREATE POLICY rls_tenants_read ON core.tenants
    FOR SELECT TO web_user
    USING (
        tenant = core.jwt_tenant()
        OR core.has_role('dx:platform-admin')
    );

DROP POLICY IF EXISTS rls_tenants_write ON core.tenants;
CREATE POLICY rls_tenants_write ON core.tenants
    FOR ALL TO web_user
    USING (
        core.has_role('dx:platform-admin')
        OR (core.has_role('dx:tenant-admin') AND tenant = core.jwt_tenant())
    )
    WITH CHECK (
        core.has_role('dx:platform-admin')
        OR (core.has_role('dx:tenant-admin') AND tenant = core.jwt_tenant())
    );

DROP POLICY IF EXISTS rls_tenants_svc ON core.tenants;
CREATE POLICY rls_tenants_svc ON core.tenants
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON core.tenants TO web_user;
GRANT ALL ON core.tenants TO svc, dxos_svc, dxos_owner;

NOTIFY pgrst, 'reload schema';

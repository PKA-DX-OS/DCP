-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 24-external-refs.sql — mã của thực thể dữ liệu chủ ở hệ thống ngoài (CSDL đất đai, dân cư...)
-- (D-MDM-01). Chỉ lưu mã đối chiếu, không lưu dữ liệu của hệ thống ngoài. Idempotent.

CREATE TABLE IF NOT EXISTS core.external_refs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    system text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    external_id text NOT NULL,
    confidence numeric(4, 3) NOT NULL DEFAULT 1,
    last_synced_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant, system, entity_type, external_id),
    CONSTRAINT chk_external_refs_type CHECK (entity_type IN ('subject', 'parcel', 'construction', 'permit', 'organization')),
    CONSTRAINT chk_external_refs_conf CHECK (confidence BETWEEN 0 AND 1)
);

CREATE INDEX IF NOT EXISTS idx_external_refs_entity ON core.external_refs (tenant, entity_type, entity_id);

ALTER TABLE core.external_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.external_refs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_external_refs_read ON core.external_refs;
CREATE POLICY rls_external_refs_read ON core.external_refs FOR SELECT TO web_user USING (tenant = core.jwt_tenant());
DROP POLICY IF EXISTS rls_external_refs_svc ON core.external_refs;
CREATE POLICY rls_external_refs_svc ON core.external_refs FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
GRANT SELECT ON core.external_refs TO web_user;
GRANT ALL ON core.external_refs TO svc, dxos_svc, dxos_owner;

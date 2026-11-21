-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 23-catalog-lineage.sql — hợp đồng dữ liệu theo phiên bản (D-CAT-01), tra phả hệ theo thực thể
-- (D-CAT-02) và mốc chỉ số H đo trên v1.1 (D-MART). Idempotent.

CREATE TABLE IF NOT EXISTS core.data_contracts (
    asset text NOT NULL REFERENCES core.data_assets(asset) ON DELETE CASCADE,
    version text NOT NULL,
    json_schema jsonb NOT NULL,
    sla jsonb NOT NULL DEFAULT '{}'::jsonb,
    consumers text[] NOT NULL DEFAULT '{}',
    effective_from timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (asset, version)
);

ALTER TABLE core.data_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.data_contracts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_data_contracts_read ON core.data_contracts;
CREATE POLICY rls_data_contracts_read ON core.data_contracts FOR SELECT TO web_user
    USING (core.dh_co_vai(ARRAY['dx:auditor', 'dx:tenant-admin', 'dx:data-steward']));
DROP POLICY IF EXISTS rls_data_contracts_svc ON core.data_contracts;
CREATE POLICY rls_data_contracts_svc ON core.data_contracts
    FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
GRANT SELECT ON core.data_contracts TO web_user;
GRANT ALL ON core.data_contracts TO svc, dxos_svc, dxos_owner;

-- Sự kiện phả hệ của một thực thể tìm theo facets.entity = {"type": ..., "id": ...}
CREATE INDEX IF NOT EXISTS idx_lineage_entity
    ON core.lineage_events ((facets -> 'entity' ->> 'type'), (facets -> 'entity' ->> 'id'), event_time DESC);
CREATE INDEX IF NOT EXISTS idx_lineage_tenant ON core.lineage_events ((facets ->> 'tenant'), event_time DESC);

-- Mốc chỉ số H theo phường (scripts/dh_baseline.py --save); API so số hiện tại với mốc mới nhất
CREATE TABLE IF NOT EXISTS core.h_baseline (
    tenant text NOT NULL,
    label text NOT NULL,
    metrics jsonb NOT NULL,
    measured_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant, label)
);
ALTER TABLE core.h_baseline ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.h_baseline FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_h_baseline_read ON core.h_baseline;
CREATE POLICY rls_h_baseline_read ON core.h_baseline FOR SELECT TO web_user USING (tenant = core.jwt_tenant());
DROP POLICY IF EXISTS rls_h_baseline_svc ON core.h_baseline;
CREATE POLICY rls_h_baseline_svc ON core.h_baseline FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
GRANT SELECT ON core.h_baseline TO web_user;
GRANT ALL ON core.h_baseline TO svc, dxos_svc, dxos_owner;

-- Hợp đồng của tài sản lõi
INSERT INTO core.data_contracts (asset, version, json_schema, sla, consumers) VALUES
('core.audit_log', '1',
 '{"type": "object", "required": ["id", "tenant", "at", "actor_type", "action", "hash"],
   "properties": {"id": {"type": "integer"}, "tenant": {"type": "string"}, "at": {"type": "string", "format": "date-time"},
                  "actor_sub": {"type": ["string", "null"]}, "actor_type": {"type": "string"}, "action": {"type": "string"},
                  "object_type": {"type": ["string", "null"]}, "object_id": {"type": ["string", "null"]},
                  "prev_hash": {"type": ["string", "null"]}, "hash": {"type": "string"}}}'::jsonb,
 '{"freshness": "realtime", "availability_pct": 99.5}'::jsonb,
 ARRAY['bang-dieu-hanh', 'metrics-api', 'scripts/dh_baseline.py']),
('core.signed_docs', '1',
 '{"type": "object", "required": ["id", "tenant", "doc_type", "public_code", "sha256", "status"],
   "properties": {"id": {"type": "string", "format": "uuid"}, "tenant": {"type": "string"}, "doc_type": {"type": "string"},
                  "public_code": {"type": "string"}, "sha256": {"type": "string"}, "status": {"type": "string", "enum": ["valid", "revoked"]}}}'::jsonb,
 '{"freshness": "realtime", "availability_pct": 99.5}'::jsonb,
 ARRAY['doc-sign /kiem-tra', 'construction /api/v1/search'])
ON CONFLICT (asset, version) DO UPDATE
SET json_schema = EXCLUDED.json_schema, sla = EXCLUDED.sla, consumers = EXCLUDED.consumers;

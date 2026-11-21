-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 26-ocr-extractions.sql — bảng lưu kết quả trích xuất OCR và hàng chờ duyệt (D-OCR, Gate 3)
-- RLS theo tenant: web_user chỉ SELECT; mọi thao tác ghi qua svc sau khi kiểm vai.
-- Khai báo PII trong core.data_assets và tích hợp quyền riêng tư DSAR. Idempotent.

CREATE TABLE IF NOT EXISTS app_cap_phep.ocr_extractions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL REFERENCES core.tenants(tenant),
    file_id uuid NOT NULL,
    dossier_id uuid REFERENCES app_cap_phep.ho_so(id) ON DELETE SET NULL,
    doc_type text NOT NULL CHECK (doc_type IN ('cccd', 'giay_chung_nhan_qsdd', 'don_de_nghi_cap_phep')),
    fields jsonb NOT NULL DEFAULT '[]'::jsonb,
    confidence numeric(4,3),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'needs_review', 'confirmed', 'rejected', 'failed')),
    reviewed_by text,
    reviewed_at timestamptz,
    reject_reason text,
    error text,
    idempotency_key text,
    retry_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_ocr_tenant_idempotency UNIQUE (tenant, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_ocr_extractions_tenant_status ON app_cap_phep.ocr_extractions(tenant, status);
CREATE INDEX IF NOT EXISTS idx_ocr_extractions_queue ON app_cap_phep.ocr_extractions(status, created_at);
CREATE INDEX IF NOT EXISTS idx_ocr_extractions_file ON app_cap_phep.ocr_extractions(file_id);
CREATE INDEX IF NOT EXISTS idx_ocr_extractions_dossier ON app_cap_phep.ocr_extractions(dossier_id);

-- RLS: Phân quyền bảo vệ dữ liệu theo phường
ALTER TABLE app_cap_phep.ocr_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.ocr_extractions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ocr_extractions_select_policy ON app_cap_phep.ocr_extractions;
CREATE POLICY ocr_extractions_select_policy ON app_cap_phep.ocr_extractions
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant());

DROP POLICY IF EXISTS rls_ocr_extractions_svc ON app_cap_phep.ocr_extractions;
CREATE POLICY rls_ocr_extractions_svc ON app_cap_phep.ocr_extractions
    FOR ALL TO svc, dxos_svc, dxos_owner
    USING (true) WITH CHECK (true);

-- Quyền truy cập: web_user CHỈ SELECT, không INSERT/UPDATE/DELETE trực tiếp
REVOKE ALL ON app_cap_phep.ocr_extractions FROM PUBLIC, anon;
GRANT SELECT ON app_cap_phep.ocr_extractions TO web_user;
GRANT ALL ON app_cap_phep.ocr_extractions TO svc, dxos_svc, dxos_owner;

-- Khai báo tài sản dữ liệu PII và retention (D-GOV-01, D-GOV-02, D-CAT-01)
DO $$
BEGIN
    IF to_regclass('core.data_assets') IS NOT NULL THEN
        INSERT INTO core.data_assets (asset, domain, description, owner, steward, classification, retention, freshness_sla)
        VALUES ('app_cap_phep.ocr_extractions', 'giay_to', 'Bản trích xuất OCR từ giấy tờ đính kèm hồ sơ, có cán bộ duyệt', 'Bộ phận một cửa', 'dx:data-steward', 'pii', '10_nam', 'realtime')
        ON CONFLICT (asset) DO UPDATE
        SET domain = EXCLUDED.domain, description = EXCLUDED.description, owner = EXCLUDED.owner,
            steward = EXCLUDED.steward, classification = EXCLUDED.classification, retention = EXCLUDED.retention,
            freshness_sla = EXCLUDED.freshness_sla, updated_at = now();

        INSERT INTO core.data_asset_columns (asset, name, classification, description, masked_in_api)
        VALUES ('app_cap_phep.ocr_extractions', 'fields', 'pii', 'Dữ liệu cá nhân trích xuất từ tài liệu (CCCD, đất đai), chỉ trả ở màn chi tiết có quyền', false)
        ON CONFLICT (asset, name) DO UPDATE
        SET classification = EXCLUDED.classification, description = EXCLUDED.description, masked_in_api = EXCLUDED.masked_in_api;
    END IF;
END $$;

-- Hàm xuất DSAR cho OCR theo dossier_id
CREATE OR REPLACE FUNCTION app_cap_phep.dsar_ocr_export(
    p_tenant text,
    p_dossier_ids uuid[]
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_result jsonb;
BEGIN
    IF coalesce(p_tenant, '') = '' OR p_dossier_ids IS NULL OR cardinality(p_dossier_ids) = 0 THEN
        RETURN '[]'::jsonb;
    END IF;

    SELECT coalesce(jsonb_agg(
        jsonb_build_object(
            'id', id,
            'file_id', file_id,
            'dossier_id', dossier_id,
            'doc_type', doc_type,
            'status', status,
            'confidence', confidence,
            'fields', fields,
            'created_at', created_at
        )
    ), '[]'::jsonb) INTO v_result
    FROM app_cap_phep.ocr_extractions
    WHERE tenant = p_tenant AND dossier_id = ANY(p_dossier_ids);

    RETURN v_result;
END;
$$;
GRANT EXECUTE ON FUNCTION app_cap_phep.dsar_ocr_export(text, uuid[]) TO web_user, svc, dxos_svc;

-- Hàm xóa/ẩn danh dữ liệu OCR theo yêu cầu DSAR (xóa nội dung trường fields chứa PII)
CREATE OR REPLACE FUNCTION app_cap_phep.dsar_ocr_erase(
    p_tenant text,
    p_dossier_ids uuid[],
    p_reason text DEFAULT 'Yêu cầu xóa dữ liệu cá nhân DSAR'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_count int := 0;
BEGIN
    IF coalesce(p_tenant, '') = '' OR p_dossier_ids IS NULL OR cardinality(p_dossier_ids) = 0 THEN
        RETURN jsonb_build_object('status', 'not_found', 'updated_count', 0);
    END IF;

    UPDATE app_cap_phep.ocr_extractions
    SET fields = '[]'::jsonb,
        updated_at = now()
    WHERE tenant = p_tenant AND dossier_id = ANY(p_dossier_ids);
    GET DIAGNOSTICS v_count = ROW_COUNT;

    RETURN jsonb_build_object('status', 'success', 'updated_count', v_count, 'reason', p_reason);
END;
$$;
GRANT EXECUTE ON FUNCTION app_cap_phep.dsar_ocr_erase(text, uuid[], text) TO web_user, svc, dxos_svc;

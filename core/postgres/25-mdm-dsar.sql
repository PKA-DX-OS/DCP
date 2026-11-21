-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 25-mdm-dsar.sql — danh mục tài sản MDM và xử lý DSAR cho dữ liệu chủ (D-GOV-02).
-- Bổ sung tài sản dữ liệu chủ vào core.data_assets và cột cá nhân vào core.data_asset_columns;
-- hàm xuất và xóa/ẩn danh dữ liệu MDM theo chính sách lưu trữ (retention). Idempotent.

DO $$
BEGIN
    IF to_regclass('core.data_assets') IS NULL THEN
        RAISE NOTICE 'Chưa có core.data_assets, bỏ qua khai báo tài sản MDM';
        RETURN;
    END IF;

    -- Khai báo tài sản MDM trong danh mục dữ liệu lõi
    INSERT INTO core.data_assets (asset, domain, description, owner, steward, classification, retention, freshness_sla) VALUES
        ('core.mdm_subject', 'cong_dan', 'Dữ liệu chủ: chủ thể công dân nộp hồ sơ, CCCD dạng HMAC', 'Bộ phận một cửa', 'dx:data-steward', 'pii', '10_nam', 'realtime'),
        ('core.mdm_parcel', 'thua_dat', 'Dữ liệu chủ: thửa đất, địa điểm công trình', 'Bộ phận thẩm định', 'dx:data-steward', 'internal', 'vinh_vien', 'realtime'),
        ('core.mdm_construction', 'cong_trinh', 'Dữ liệu chủ: công trình xây dựng', 'Bộ phận trật tự xây dựng', 'dx:data-steward', 'internal', 'vinh_vien', 'realtime'),
        ('core.mdm_organization', 'cong_dan', 'Dữ liệu chủ: tổ chức, doanh nghiệp', 'Bộ phận một cửa', 'dx:data-steward', 'internal', 'vinh_vien', 'realtime'),
        ('core.mdm_dossier_link', 'ho_so', 'Dữ liệu chủ: liên kết hồ sơ với chủ thể, thửa đất, công trình, giấy phép', 'Bộ phận một cửa', 'dx:data-steward', 'internal', 'vinh_vien', 'realtime'),
        ('core.external_refs', 'ho_so', 'Mã đối chiếu thực thể dữ liệu chủ với hệ thống ngoài', 'Bộ phận một cửa', 'dx:data-steward', 'internal', '10_nam', 'realtime')
    ON CONFLICT (asset) DO UPDATE
    SET domain = EXCLUDED.domain, description = EXCLUDED.description, owner = EXCLUDED.owner,
        steward = EXCLUDED.steward, classification = EXCLUDED.classification, retention = EXCLUDED.retention,
        freshness_sla = EXCLUDED.freshness_sla, updated_at = now();

    -- Cột dữ liệu cá nhân trong các bảng MDM
    INSERT INTO core.data_asset_columns (asset, name, classification, description, masked_in_api) VALUES
        ('core.mdm_subject', 'cccd_hmac', 'sensitive', 'Mã HMAC của CCCD; API không bao giờ trả thô', true),
        ('core.mdm_subject', 'source_ref', 'internal', 'Khóa tham chiếu hồ sơ nguồn', false),
        ('core.mdm_dossier_link', 'subject_id', 'pii', 'Khóa định danh chủ thể liên kết', false),
        ('core.external_refs', 'external_id', 'internal', 'Mã định danh tại hệ thống đối tác bên ngoài', false)
    ON CONFLICT (asset, name) DO UPDATE
    SET classification = EXCLUDED.classification, description = EXCLUDED.description, masked_in_api = EXCLUDED.masked_in_api;
END $$;

-- Hàm xuất dữ liệu MDM phục vụ quyền truy cập dữ liệu cá nhân (DSAR Access)
CREATE OR REPLACE FUNCTION core_api.dsar_mdm_export(
    p_tenant text,
    p_cccd_hmac text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, core_api, pg_catalog
AS $$
DECLARE
    v_subject core.mdm_subject%ROWTYPE;
    v_links jsonb;
    v_ext jsonb;
BEGIN
    IF coalesce(p_tenant, '') = '' OR coalesce(p_cccd_hmac, '') = '' THEN
        RETURN NULL;
    END IF;

    SELECT * INTO v_subject
    FROM core.mdm_subject
    WHERE tenant = p_tenant AND cccd_hmac = p_cccd_hmac AND merged_into IS NULL
    ORDER BY created_at DESC LIMIT 1;

    IF v_subject.subject_id IS NULL THEN
        RETURN NULL;
    END IF;

    -- Danh sách liên kết hồ sơ và thực thể liên quan (không trả HMAC)
    SELECT coalesce(jsonb_agg(
        jsonb_build_object(
            'dossier_id', l.dossier_id,
            'confidence', l.confidence,
            'source', l.source,
            'parcel', CASE WHEN p.parcel_id IS NOT NULL THEN jsonb_build_object(
                'parcel_id', p.parcel_id,
                'so_thua', p.so_thua,
                'to_ban_do', p.to_ban_do,
                'ma_dinh_danh_dia_diem', p.ma_dinh_danh_dia_diem,
                'dien_tich_m2', p.dien_tich_m2
            ) ELSE NULL END,
            'construction', CASE WHEN c.construction_id IS NOT NULL THEN jsonb_build_object(
                'construction_id', c.construction_id,
                'ma_cong_trinh', c.ma_cong_trinh,
                'dia_chi_chuan', c.dia_chi_chuan
            ) ELSE NULL END,
            'permit_id', l.permit_id
        )
    ), '[]'::jsonb) INTO v_links
    FROM core.mdm_dossier_link l
    LEFT JOIN core.mdm_parcel p ON p.parcel_id = l.parcel_id
    LEFT JOIN core.mdm_construction c ON c.construction_id = l.construction_id
    WHERE l.tenant = p_tenant AND l.subject_id = v_subject.subject_id;

    -- Danh sách tham chiếu hệ thống ngoài
    SELECT coalesce(jsonb_agg(
        jsonb_build_object(
            'system', e.system,
            'entity_type', e.entity_type,
            'external_id', e.external_id,
            'confidence', e.confidence,
            'last_synced_at', e.last_synced_at
        )
    ), '[]'::jsonb) INTO v_ext
    FROM core.external_refs e
    WHERE e.tenant = p_tenant AND e.entity_type = 'subject' AND e.entity_id = v_subject.subject_id;

    -- Trả thông tin chủ thể: tuyệt đối KHÔNG trả cccd_hmac thô
    RETURN jsonb_build_object(
        'tenant', p_tenant,
        'subject', jsonb_build_object(
            'subject_id', v_subject.subject_id,
            'source', v_subject.source,
            'confidence', v_subject.confidence,
            'created_at', v_subject.created_at
        ),
        'dossier_links', v_links,
        'external_refs', v_ext
    );
END;
$$;
GRANT EXECUTE ON FUNCTION core_api.dsar_mdm_export(text, text) TO web_user, svc, dxos_svc;

-- Hàm xóa hoặc ẩn danh dữ liệu MDM theo chính sách retention (DSAR Erase)
CREATE OR REPLACE FUNCTION core_api.dsar_mdm_erase(
    p_tenant text,
    p_cccd_hmac text,
    p_reason text DEFAULT 'Yêu cầu xóa dữ liệu cá nhân DSAR',
    p_actor_sub text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, core_api, pg_catalog
AS $$
DECLARE
    v_subject core.mdm_subject%ROWTYPE;
    v_actor text := coalesce(p_actor_sub, core.jwt_sub(), 'system');
    v_ext_count int := 0;
BEGIN
    IF coalesce(p_tenant, '') = '' OR coalesce(p_cccd_hmac, '') = '' THEN
        RETURN jsonb_build_object('status', 'not_found', 'message', 'Thiếu thông tin tra cứu');
    END IF;

    SELECT * INTO v_subject
    FROM core.mdm_subject
    WHERE tenant = p_tenant AND cccd_hmac = p_cccd_hmac AND merged_into IS NULL
    ORDER BY created_at DESC LIMIT 1;

    IF v_subject.subject_id IS NULL THEN
        RETURN jsonb_build_object('status', 'not_found', 'message', 'Không tìm thấy bản ghi MDM của chủ thể');
    END IF;

    -- 1. Xóa các mã đối chiếu hệ thống ngoài (external_refs, retention 10_nam)
    DELETE FROM core.external_refs
    WHERE tenant = p_tenant AND entity_type = 'subject' AND entity_id = v_subject.subject_id;
    GET DIAGNOSTICS v_ext_count = ROW_COUNT;

    -- 2. Ẩn danh hóa chủ thể MDM: loại bỏ cccd_hmac và source_ref
    -- Liên kết hồ sơ mdm_dossier_link được giữ nguyên theo chính sách lưu trữ vĩnh viễn
    -- của hồ sơ hành chính công vụ (app_cap_phep.ho_so retention vinh_vien)
    UPDATE core.mdm_subject
    SET cccd_hmac = NULL, source_ref = NULL
    WHERE subject_id = v_subject.subject_id;

    -- 3. Ghi audit log
    PERFORM core.record_audit(
        p_tenant, v_actor, 'user', 'dsar.mdm.erased', 'mdm_subject', v_subject.subject_id::text,
        jsonb_build_object(
            'reason', p_reason,
            'anonymized', true,
            'external_refs_deleted', v_ext_count,
            'retention_policy', 'core.data_assets'
        )
    );

    RETURN jsonb_build_object(
        'status', 'success',
        'subject_id', v_subject.subject_id,
        'anonymized', true,
        'deleted_external_refs', v_ext_count,
        'external_refs_deleted', v_ext_count,
        'retained_dossier_links', (SELECT count(*) FROM core.mdm_dossier_link WHERE tenant = p_tenant AND subject_id = v_subject.subject_id),
        'reason', p_reason,
        'erased_at', now(),
        'message', 'Đã xử lý xóa/ẩn danh dữ liệu MDM theo chính sách lưu trữ'
    );
END;
$$;
GRANT EXECUTE ON FUNCTION core_api.dsar_mdm_erase(text, text, text, text) TO web_user, svc, dxos_svc;

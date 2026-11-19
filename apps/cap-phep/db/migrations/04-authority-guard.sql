-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 04-authority-guard.sql — Track A: kiểm tra thẩm quyền trước khi ký.
-- Idempotent. Chạy sau 03-legal-alignment.sql.

CREATE OR REPLACE FUNCTION app_cap_phep_private.kiem_tra_hook_ky(p_process_id text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, app_construction_private, core, pg_catalog
AS $$
DECLARE
    v_hs app_cap_phep.ho_so%ROWTYPE;
    v_quyen jsonb;
BEGIN
    SELECT * INTO v_hs
    FROM app_cap_phep.ho_so
    WHERE process_instance_id = p_process_id
    LIMIT 1;

    IF v_hs.id IS NULL THEN
        RETURN jsonb_build_object(
            'found', false,
            'tenant', NULL,
            'trang_thai', NULL,
            'ho_so_id', NULL,
            'tham_quyen_ok', false
        );
    END IF;

    v_quyen := app_construction_private.xac_dinh_tham_quyen(
        v_hs.loai_cong_trinh,
        v_hs.cap_cong_trinh,
        v_hs.doi_tuong,
        v_hs.trong_kcn,
        v_hs.cap_hanh_chinh
    );

    PERFORM core.record_audit(
        v_hs.tenant,
        core.jwt_sub(),
        'service',
        'ho_so.authority_guard_checked',
        'ho_so',
        v_hs.id::text,
        jsonb_build_object(
            'process_instance_id', p_process_id,
            'xac_dinh_duoc', COALESCE((v_quyen->>'xac_dinh_duoc')::boolean, false),
            'co_quan_cap', v_quyen->>'co_quan_cap',
            'nguoi_ky', v_quyen->>'nguoi_ky',
            'legal_citation_key', v_quyen->>'legal_citation_key'
        )
    );

    RETURN jsonb_build_object(
        'found', true,
        'tenant', v_hs.tenant,
        'trang_thai', v_hs.trang_thai,
        'ho_so_id', v_hs.id,
        'tham_quyen_ok', COALESCE((v_quyen->>'xac_dinh_duoc')::boolean, false),
        'co_quan_cap', v_quyen->>'co_quan_cap',
        'nguoi_ky', v_quyen->>'nguoi_ky',
        'legal_citation_key', v_quyen->>'legal_citation_key',
        'ly_do_tham_quyen', v_quyen->>'ly_do'
    );
END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep_private.kiem_tra_hook_ky(text) TO svc, dxos_svc, dxos_owner;

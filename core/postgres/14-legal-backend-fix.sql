-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 14-legal-backend-fix.sql — wrapper công khai cho hàm thẩm quyền.
-- Idempotent. Chạy sau 12-legal-backend-schema.sql.

CREATE OR REPLACE FUNCTION app_construction.xac_dinh_tham_quyen(
    p_loai_cong_trinh text,
    p_cap_cong_trinh text DEFAULT NULL,
    p_doi_tuong text DEFAULT 'ho_gia_dinh_ca_nhan',
    p_trong_kcn boolean DEFAULT false,
    p_cap_hanh_chinh text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = app_construction_private, app_construction, pg_catalog
AS $$
    SELECT app_construction_private.xac_dinh_tham_quyen(
        $1, $2, $3, $4, $5
    );
$$;

GRANT EXECUTE ON FUNCTION app_construction.xac_dinh_tham_quyen(text, text, text, boolean, text)
    TO web_user, svc, dxos_svc;

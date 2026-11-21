-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 26-mdm-360-views.sql — các view 360 cho hồ sơ, giấy phép, công trình (D-MDM-03).
-- Tổng hợp thông tin từ dữ liệu chủ (golden records) và dữ liệu ứng dụng; che CCCD/điện thoại;
-- dùng security_invoker = true để tuân thủ RLS của người dùng gọi. Idempotent.

-- 1. Hàm che dữ liệu PII trong SQL
CREATE OR REPLACE FUNCTION core.che_cccd(p_cccd text)
RETURNS text AS $$
DECLARE
    v text := regexp_replace(coalesce(p_cccd, ''), '\D', '', 'g');
BEGIN
    IF length(v) = 12 THEN
        RETURN substring(v from 1 for 4) || '******' || substring(v from 11 for 2);
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION core.che_dien_thoai(p_dt text)
RETURNS text AS $$
DECLARE
    v text := regexp_replace(coalesce(p_dt, ''), '\D', '', 'g');
BEGIN
    IF v LIKE '84%' AND length(v) = 11 THEN
        v := '0' || substring(v from 3);
    END IF;
    IF length(v) >= 9 THEN
        RETURN substring(v from 1 for 3) || repeat('*', length(v) - 6) || substring(v from length(v) - 2 for 3);
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

GRANT EXECUTE ON FUNCTION core.che_cccd(text) TO web_user, svc, dxos_svc;
GRANT EXECUTE ON FUNCTION core.che_dien_thoai(text) TO web_user, svc, dxos_svc;

-- 2. View 360 hồ sơ (v_dossier_360)
CREATE OR REPLACE VIEW core.v_dossier_360 WITH (security_invoker = true) AS
SELECT
    h.tenant,
    h.id AS dossier_id,
    jsonb_build_object(
        'id', h.id,
        'ma_ho_so', h.ma_ho_so,
        'trang_thai', h.trang_thai,
        'buoc', h.buoc,
        'created_at', h.created_at,
        'han_tong_at', h.han_tong_at,
        'qua_han', coalesce(h.qua_han, false)
    ) AS ho_so,
    CASE WHEN s.subject_id IS NOT NULL AND core.che_cccd(h.cccd) IS NOT NULL THEN
        jsonb_build_object(
            'subject_id', s.subject_id,
            'ho_ten', coalesce(h.ho_ten, ''),
            'cccd_mask', core.che_cccd(h.cccd),
            'dien_thoai_mask', core.che_dien_thoai(h.dien_thoai),
            'so_ho_so_khac', (
                SELECT count(*)::int
                FROM core.mdm_dossier_link l2
                WHERE l2.tenant = h.tenant
                  AND l2.subject_id = s.subject_id
                  AND l2.dossier_id <> h.id
            )
        )
    ELSE NULL END AS chu_dau_tu,
    CASE WHEN p.parcel_id IS NOT NULL THEN
        jsonb_build_object(
            'parcel_id', p.parcel_id,
            'so_thua', p.so_thua,
            'to_ban_do', p.to_ban_do,
            'ma_dinh_danh_dia_diem', p.ma_dinh_danh_dia_diem,
            'dien_tich_m2', p.dien_tich_m2
        )
    ELSE NULL END AS thua_dat,
    CASE WHEN c.construction_id IS NOT NULL AND gp.ma_cong_trinh IS NOT NULL THEN
        jsonb_build_object(
            'construction_id', c.construction_id,
            'ma_cong_trinh', gp.ma_cong_trinh,
            'dia_chi', coalesce(gp.dia_chi, c.dia_chi_chuan)
        )
    ELSE NULL END AS cong_trinh,
    CASE WHEN gp.id IS NOT NULL THEN
        jsonb_build_object(
            'permit_id', gp.id,
            'so_giay_phep', gp.so_giay_phep,
            'public_code', gp.public_code,
            'trang_thai', gp.trang_thai,
            'ngay_cap', gp.ngay_cap
        )
    ELSE NULL END AS giay_phep
FROM app_cap_phep.ho_so h
LEFT JOIN core.mdm_dossier_link l ON l.tenant = h.tenant AND l.dossier_id = h.id
LEFT JOIN core.v_mdm_subject_golden s ON s.tenant = h.tenant AND s.subject_id = l.subject_id
LEFT JOIN core.v_mdm_parcel_golden p ON p.tenant = h.tenant AND p.parcel_id = l.parcel_id
LEFT JOIN core.v_mdm_construction_golden c ON c.tenant = h.tenant AND c.construction_id = l.construction_id
LEFT JOIN LATERAL (
    SELECT g.id, g.so_giay_phep, g.trang_thai, g.ngay_cap, d.public_code,
           ct.ma_cong_trinh, ct.dia_chi
    FROM app_cap_phep.giay_phep g
    LEFT JOIN core.signed_docs d ON d.id = g.signed_doc_id
    LEFT JOIN app_cap_phep.cong_trinh ct ON ct.giay_phep_id = g.id
    WHERE g.ho_so_id = h.id AND g.tenant = h.tenant
    ORDER BY (g.trang_thai = 'hieu_luc') DESC, g.ngay_cap DESC
    LIMIT 1
) gp ON true;

-- 3. View 360 giấy phép (v_permit_360)
CREATE OR REPLACE VIEW core.v_permit_360 WITH (security_invoker = true) AS
SELECT
    g.tenant,
    g.id AS permit_id,
    g.so_giay_phep,
    g.trang_thai,
    g.ngay_cap,
    d.public_code,
    h.id AS dossier_id,
    h.ma_ho_so,
    CASE WHEN s.subject_id IS NOT NULL AND core.che_cccd(h.cccd) IS NOT NULL THEN
        jsonb_build_object(
            'subject_id', s.subject_id,
            'ho_ten', coalesce(h.ho_ten, ''),
            'cccd_mask', core.che_cccd(h.cccd),
            'dien_thoai_mask', core.che_dien_thoai(h.dien_thoai)
        )
    ELSE NULL END AS chu_dau_tu,
    CASE WHEN p.parcel_id IS NOT NULL THEN
        jsonb_build_object(
            'parcel_id', p.parcel_id,
            'so_thua', p.so_thua,
            'to_ban_do', p.to_ban_do,
            'ma_dinh_danh_dia_diem', p.ma_dinh_danh_dia_diem
        )
    ELSE NULL END AS thua_dat,
    CASE WHEN c.construction_id IS NOT NULL THEN
        jsonb_build_object(
            'construction_id', c.construction_id,
            'ma_cong_trinh', ct.ma_cong_trinh,
            'dia_chi', ct.dia_chi
        )
    ELSE NULL END AS cong_trinh
FROM app_cap_phep.giay_phep g
LEFT JOIN core.signed_docs d ON d.id = g.signed_doc_id
LEFT JOIN app_cap_phep.ho_so h ON h.id = g.ho_so_id AND h.tenant = g.tenant
LEFT JOIN app_cap_phep.cong_trinh ct ON ct.giay_phep_id = g.id
LEFT JOIN core.mdm_dossier_link l ON l.tenant = g.tenant AND l.dossier_id = h.id
LEFT JOIN core.v_mdm_subject_golden s ON s.tenant = g.tenant AND s.subject_id = l.subject_id
LEFT JOIN core.v_mdm_parcel_golden p ON p.tenant = g.tenant AND p.parcel_id = l.parcel_id
LEFT JOIN core.v_mdm_construction_golden c ON c.tenant = g.tenant AND c.construction_id = l.construction_id;

-- 4. View 360 công trình (v_construction_360)
CREATE OR REPLACE VIEW core.v_construction_360 WITH (security_invoker = true) AS
SELECT
    c.tenant,
    c.construction_id,
    c.ma_cong_trinh,
    c.dia_chi_chuan AS dia_chi,
    c.parcel_id,
    CASE WHEN p.parcel_id IS NOT NULL THEN
        jsonb_build_object(
            'parcel_id', p.parcel_id,
            'so_thua', p.so_thua,
            'to_ban_do', p.to_ban_do,
            'ma_dinh_danh_dia_diem', p.ma_dinh_danh_dia_diem
        )
    ELSE NULL END AS thua_dat,
    coalesce((
        SELECT jsonb_agg(
            jsonb_build_object(
                'dossier_id', l.dossier_id,
                'ma_ho_so', h.ma_ho_so,
                'trang_thai', h.trang_thai,
                'created_at', h.created_at
            ) ORDER BY h.created_at DESC
        )
        FROM core.mdm_dossier_link l
        JOIN app_cap_phep.ho_so h ON h.id = l.dossier_id AND h.tenant = l.tenant
        WHERE l.tenant = c.tenant AND l.construction_id = c.construction_id
    ), '[]'::jsonb) AS dossiers
FROM core.v_mdm_construction_golden c
LEFT JOIN core.v_mdm_parcel_golden p ON p.tenant = c.tenant AND p.parcel_id = c.parcel_id;

GRANT SELECT ON core.v_dossier_360, core.v_permit_360, core.v_construction_360 TO web_user, svc, dxos_svc;

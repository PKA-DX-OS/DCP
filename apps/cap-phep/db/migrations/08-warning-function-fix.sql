-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 08-warning-function-fix.sql — sửa kiểu dữ liệu giay_to_con_thieu (TABLE → jsonb).
-- Idempotent.

CREATE OR REPLACE FUNCTION app_cap_phep.danh_sach_canh_bao_ho_so(p_ho_so_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, app_cap_phep_private, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_hs app_cap_phep.ho_so%ROWTYPE;
    v_items jsonb := '[]'::jsonb;
    v_missing jsonb := '[]'::jsonb;
BEGIN
    SELECT * INTO v_hs FROM app_cap_phep.ho_so
    WHERE id = p_ho_so_id AND tenant = cur_tenant;
    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ trong địa bàn' USING ERRCODE = '42501';
    END IF;
    IF v_hs.chu_dau_tu_sub <> cur_sub
       AND NOT (core.has_role('app:cap-phep:mot-cua') OR core.has_role('app:cap-phep:tham-dinh') OR core.has_role('app:cap-phep:lanh-dao')) THEN
        RAISE EXCEPTION 'Bạn không có quyền xem cảnh báo hồ sơ này' USING ERRCODE = '42501';
    END IF;

    IF v_hs.so_tang > 5 THEN
        v_items := v_items || jsonb_build_object(
            'ma', 'so_tang_nguong', 'loai', 'business', 'severity', 'warning',
            'reason', 'Số tầng lớn hơn ngưỡng cấu hình 5; không tự động từ chối, cán bộ cần kiểm tra thêm.',
            'legal_citation_key', 'LXD135-TOANVAN'
        );
    END IF;
    IF v_hs.dien_tich_san_m2 > 500 THEN
        v_items := v_items || jsonb_build_object(
            'ma', 'dien_tich_nguong', 'loai', 'business', 'severity', 'warning',
            'reason', 'Diện tích sàn lớn hơn ngưỡng cấu hình 500 m²; không tự động từ chối, cán bộ cần kiểm tra thêm.',
            'legal_citation_key', 'LXD135-TOANVAN'
        );
    END IF;
    IF v_hs.ma_dinh_danh_dia_diem IS NULL THEN
        v_items := v_items || jsonb_build_object(
            'ma', 'thieu_ma_dinh_danh', 'loai', 'warning', 'severity', 'warning',
            'reason', 'Hồ sơ chưa gắn mã định danh địa điểm 12 chữ số; cần tra CSDL định danh địa điểm.',
            'legal_citation_key', 'ND326-TOANVAN'
        );
    END IF;

    SELECT COALESCE(jsonb_agg(to_jsonb(x)), '[]'::jsonb) INTO v_missing
    FROM app_cap_phep.giay_to_con_thieu(p_ho_so_id) x;

    IF jsonb_array_length(v_missing) > 0 THEN
        v_items := v_items || jsonb_build_object(
            'ma', 'thieu_giay_to', 'loai', 'legal', 'severity', 'error',
            'reason', 'Còn thiếu giấy tờ bắt buộc theo manifest.',
            'chi_tiet', v_missing
        );
    END IF;

    RETURN jsonb_build_object(
        'ho_so_id', p_ho_so_id,
        'items', v_items,
        'so_canh_bao', (SELECT count(*) FROM jsonb_array_elements(v_items) e WHERE e->>'severity' = 'warning'),
        'so_loi', (SELECT count(*) FROM jsonb_array_elements(v_items) e WHERE e->>'severity' = 'error'),
        'xac_nhan_at', v_hs.canh_bao_xac_nhan_at,
        'xac_nhan_by', v_hs.canh_bao_xac_nhan_by,
        'ghi_chu', v_hs.canh_bao_ghi_chu
    );
END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep.danh_sach_canh_bao_ho_so(uuid) TO web_user;

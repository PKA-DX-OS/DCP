-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 06-subject-authority.sql — A-LEGAL-02/A-LEGAL-04: phân biệt hộ gia đình/cá nhân
-- với tổ chức và ghi nhận địa bàn/KCN phục vụ xác định thẩm quyền.
-- Idempotent. Chạy sau 05-track-a-workflows.sql.

CREATE OR REPLACE FUNCTION app_cap_phep.cap_nhat_thong_tin_tham_quyen(
    p_ho_so_id uuid,
    p_doi_tuong text DEFAULT NULL,
    p_loai_cong_trinh text DEFAULT NULL,
    p_cap_cong_trinh text DEFAULT NULL,
    p_trong_kcn boolean DEFAULT NULL,
    p_cap_hanh_chinh text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_hs app_cap_phep.ho_so%ROWTYPE;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO v_hs FROM app_cap_phep.ho_so
    WHERE id = p_ho_so_id AND tenant = cur_tenant;
    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ trong địa bàn' USING ERRCODE = '42501';
    END IF;

    IF v_hs.chu_dau_tu_sub <> cur_sub
       AND NOT (core.has_role('app:cap-phep:mot-cua') OR core.has_role('app:cap-phep:tham-dinh') OR core.has_role('app:cap-phep:lanh-dao')) THEN
        RAISE EXCEPTION 'Bạn không có quyền cập nhật hồ sơ này' USING ERRCODE = '42501';
    END IF;

    IF p_doi_tuong IS NOT NULL AND p_doi_tuong NOT IN ('ho_gia_dinh_ca_nhan', 'to_chuc') THEN
        RAISE EXCEPTION 'Đối tượng không hợp lệ' USING ERRCODE = 'PT422';
    END IF;
    IF p_cap_hanh_chinh IS NOT NULL AND p_cap_hanh_chinh NOT IN ('xa', 'tinh') THEN
        RAISE EXCEPTION 'Cấp hành chính không hợp lệ' USING ERRCODE = 'PT422';
    END IF;

    UPDATE app_cap_phep.ho_so
    SET doi_tuong = COALESCE(p_doi_tuong, doi_tuong),
        loai_cong_trinh = COALESCE(p_loai_cong_trinh, loai_cong_trinh),
        cap_cong_trinh = COALESCE(p_cap_cong_trinh, cap_cong_trinh),
        trong_kcn = COALESCE(p_trong_kcn, trong_kcn),
        cap_hanh_chinh = COALESCE(p_cap_hanh_chinh, cap_hanh_chinh),
        updated_at = now()
    WHERE id = p_ho_so_id;

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'ho_so.tham_quyen_updated', 'ho_so', p_ho_so_id::text,
        jsonb_build_object(
            'doi_tuong', COALESCE(p_doi_tuong, v_hs.doi_tuong),
            'loai_cong_trinh', COALESCE(p_loai_cong_trinh, v_hs.loai_cong_trinh),
            'cap_cong_trinh', COALESCE(p_cap_cong_trinh, v_hs.cap_cong_trinh),
            'trong_kcn', COALESCE(p_trong_kcn, v_hs.trong_kcn),
            'cap_hanh_chinh', COALESCE(p_cap_hanh_chinh, v_hs.cap_hanh_chinh)
        )
    );

    RETURN app_cap_phep.kiem_tra_tham_quyen_ho_so(p_ho_so_id);
END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep.cap_nhat_thong_tin_tham_quyen(uuid, text, text, text, boolean, text)
    TO web_user;

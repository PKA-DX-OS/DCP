-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

-- FIX-V11-12: cán bộ trật tự xây dựng nghiệm thu và hậu kiểm công trình đã cấp phép nhưng
-- mo_ho_so chỉ cho chủ đầu tư, lãnh đạo, một cửa và người được phân công, nên khi tt.khanh
-- mở việc nghiệm thu móng thì bị từ chối ("Bạn không được phân công xử lý hồ sơ này").
-- Cho vai trat-tu-xd mở hồ sơ cùng phường khi hồ sơ đã cấp phép (giai đoạn thi công).
-- Phần còn lại giữ nguyên bản 01. Idempotent.

CREATE OR REPLACE FUNCTION app_cap_phep.mo_ho_so(p_id uuid)
RETURNS jsonb AS $$
DECLARE
    v_rec record;
    v_tenant text := core.jwt_tenant();
    v_sub text := core.jwt_sub();
    v_has_access boolean := false;
BEGIN
    SELECT * INTO v_rec FROM app_cap_phep.ho_so WHERE id = p_id;

    IF NOT FOUND THEN
        PERFORM set_config('response.status', '404', true);
        RETURN jsonb_build_object('loi', 'Không tìm thấy hồ sơ', 'ma_loi', 'NOT_FOUND');
    END IF;

    -- Kiểm tra đa thuê ước
    IF v_rec.tenant <> v_tenant AND NOT core.has_role('dx:platform-admin') THEN
        PERFORM core.record_audit(
            v_tenant, v_sub, 'user', 'access.denied', 'ho_so', p_id::text,
            jsonb_build_object('ly_do', 'Vi pham ranh gioi da thue uoc tenant', 'target_tenant', v_rec.tenant)
        );
        PERFORM set_config('response.status', '403', true);
        RETURN jsonb_build_object('loi', 'Bạn không có quyền truy cập hồ sơ của đơn vị khác', 'ma_loi', 'FORBIDDEN_TENANT');
    END IF;

    -- Kiểm tra quyền phân công và vai trò
    IF v_rec.chu_dau_tu_sub = v_sub
       OR core.has_role('app:cap-phep:lanh-dao')
       OR core.has_role('app:cap-phep:mot-cua')
       OR core.can_access('ho_so', p_id)
       -- Trật tự xây dựng giám sát thi công: được xem hồ sơ đã cấp phép
       OR (core.has_role('app:cap-phep:trat-tu-xd') AND v_rec.trang_thai = 'DA_CAP') THEN
        v_has_access := true;
    END IF;

    IF NOT v_has_access THEN
        -- Ghi audit từ chối và KHÔNG rollback
        PERFORM core.record_audit(
            v_tenant, v_sub, 'user', 'access.denied', 'ho_so', p_id::text,
            jsonb_build_object('ly_do', 'Tu choi truy cap: can bo khong duoc phan cong ho so')
        );
        PERFORM set_config('response.status', '403', true);
        RETURN jsonb_build_object(
            'loi', 'Bạn không được phân công xử lý hồ sơ này',
            'ma_loi', 'ACCESS_DENIED',
            'ho_so_id', p_id,
            'ma_ho_so', v_rec.ma_ho_so,
            'can_xin_truy_cap_khan', true
        );
    END IF;

    -- Có quyền: ghi nhận nhật ký truy cập thành công
    PERFORM core.record_audit(
        v_tenant, v_sub, 'user', 'access.granted', 'ho_so', p_id::text,
        jsonb_build_object('ma_ho_so', v_rec.ma_ho_so)
    );

    RETURN (SELECT to_jsonb(v) FROM app_cap_phep.v_ho_so v WHERE v.id = p_id);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app_cap_phep, core;

GRANT EXECUTE ON FUNCTION app_cap_phep.mo_ho_so(uuid) TO web_user;

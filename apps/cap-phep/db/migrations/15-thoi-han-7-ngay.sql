-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

-- Thời hạn giải quyết cấp phép xây dựng nhà ở riêng lẻ: 07 ngày làm việc (Điều 54 NĐ 217/2026/NĐ-CP).
-- Trước đây nop_ho_so đặt 15 ngày làm việc trong khi tài liệu, trợ lý và chỉ số tác động dùng 7 ngày.
-- Con số nằm ở một chỗ: app_cap_phep.so_ngay_giai_quyet().
-- Hồ sơ chưa đóng mà hạn do nop_ho_so cũ đặt (đúng created_at + 15 ngày làm việc) được tính lại;
-- hồ sơ mẫu có hạn đặt tay giữ nguyên.
-- Idempotent: chạy lại thay hàm, lần cập nhật thứ hai không còn dòng nào khớp.

CREATE OR REPLACE FUNCTION app_cap_phep.so_ngay_giai_quyet()
RETURNS integer
LANGUAGE sql
IMMUTABLE
AS $$ SELECT 7 $$;

COMMENT ON FUNCTION app_cap_phep.so_ngay_giai_quyet() IS
    'Thời hạn giải quyết cấp GPXD nhà ở riêng lẻ, ngày làm việc (Điều 54 NĐ 217/2026/NĐ-CP)';

GRANT EXECUTE ON FUNCTION app_cap_phep.so_ngay_giai_quyet() TO web_user, svc, dxos_svc;

CREATE OR REPLACE FUNCTION app_cap_phep.nop_ho_so(
    ho_ten text,
    cccd text,
    dien_thoai text,
    dia_chi_cong_trinh text,
    thua_dat text,
    so_tang integer DEFAULT 1,
    dien_tich_san_m2 double precision DEFAULT 100.0,
    khu_quan_ly_kien_truc boolean DEFAULT true,
    p_ho_so_id uuid DEFAULT NULL,
    p_tep jsonb DEFAULT '[]'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_new_id uuid := COALESCE(p_ho_so_id, gen_random_uuid());
    v_ma text;
    v_han_tong timestamptz;
    v_check jsonb;
    v_tep jsonb := COALESCE(p_tep, '[]'::jsonb);
    v_item jsonb;
    v_file core.files%ROWTYPE;
    v_count integer := 0;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    -- Chỉ vai chu-dau-tu mới có quyền nộp hồ sơ (V4-02)
    IF NOT core.has_role('app:cap-phep:chu-dau-tu') AND NOT core.has_role('dx:platform-admin') THEN
        RAISE EXCEPTION 'Chỉ chủ đầu tư mới có quyền nộp hồ sơ' USING ERRCODE = '42501';
    END IF;

    IF EXISTS (SELECT 1 FROM app_cap_phep.ho_so WHERE id = v_new_id) THEN
        RAISE EXCEPTION 'Mã hồ sơ đã tồn tại' USING ERRCODE = '23505';
    END IF;

    -- P1: kiểm tra 7 lớp trước khi ghi bất kỳ dữ liệu nào
    v_check := app_cap_phep.kiem_tra_giay_to_nop(
        v_new_id, v_tep, ho_ten, cccd, thua_dat, so_tang, dien_tich_san_m2
    );

    IF NOT COALESCE((v_check->>'ok')::boolean, false) THEN
        RAISE EXCEPTION 'Hồ sơ chưa đủ điều kiện nộp'
            USING ERRCODE = 'PT422',
                  DETAIL = (v_check->'errors')::text;
    END IF;

    v_ma := 'CP-' || to_char(now(), 'YYYY') || '-' || lpad((floor(random() * 900000) + 100000)::text, 6, '0');
    v_han_tong := core.add_business_days(now(), app_cap_phep.so_ngay_giai_quyet());

    INSERT INTO app_cap_phep.ho_so (
        id, tenant, ma_ho_so, chu_dau_tu_sub, ho_ten, cccd, dien_thoai,
        dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2,
        khu_quan_ly_kien_truc, trang_thai, buoc, han_tong_at, created_at, updated_at
    )
    VALUES (
        v_new_id, cur_tenant, v_ma, cur_sub, ho_ten, cccd, dien_thoai,
        dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2,
        khu_quan_ly_kien_truc, 'DA_NOP', 'tiep_nhan', v_han_tong, now(), now()
    );

    -- Ghi metadata tệp đã kiểm tra (version 1)
    FOR v_item IN SELECT * FROM jsonb_array_elements(v_tep)
    LOOP
        SELECT * INTO v_file
        FROM core.files
        WHERE id = (v_item->>'file_id')::uuid
          AND tenant = cur_tenant;

        INSERT INTO app_cap_phep.ho_so_tep (
            ho_so_id, file_id, loai, sha256, size, mime,
            nguoi_tai, tai_luc, trang_thai_kiem_tra,
            ngay_cap, ngay_het_han, version, thong_tin
        ) VALUES (
            v_new_id,
            v_file.id,
            v_item->>'loai',
            v_file.sha256,
            v_file.size,
            v_file.mime,
            cur_sub,
            now(),
            'cho_kiem_tra',
            NULLIF(v_item->>'ngay_cap', '')::date,
            NULLIF(v_item->>'ngay_het_han', '')::date,
            1,
            COALESCE(v_item->'thong_tin', '{}'::jsonb)
        );
        v_count := v_count + 1;
    END LOOP;

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'ho_so.nop', 'ho_so', v_new_id::text,
        jsonb_build_object('ma_ho_so', v_ma, 'dia_chi', dia_chi_cong_trinh, 'so_tep', v_count)
    );

    PERFORM app_cap_phep.gui_thong_bao(
        cur_tenant,
        ARRAY['app:cap-phep:mot-cua'],
        NULL,
        'Hồ sơ mới ' || v_ma,
        'Hồ sơ cấp phép mới ' || v_ma || ' vừa được nộp bởi ' || ho_ten || ', đang chờ một cửa tiếp nhận.',
        v_new_id::text
    );

    RETURN jsonb_build_object(
        'status', 'success',
        'id', v_new_id,
        'ma_ho_so', v_ma,
        'so_tep', v_count,
        'message', 'Đã nộp hồ sơ xin cấp phép xây dựng thành công'
    );
END;
$$;

UPDATE app_cap_phep.ho_so
SET han_tong_at = core.add_business_days(created_at, app_cap_phep.so_ngay_giai_quyet())
WHERE trang_thai NOT IN ('DA_CAP', 'TU_CHOI')
  AND han_tong_at = core.add_business_days(created_at, 15);

-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 03-legal-alignment.sql — Track A: căn cứ Điều 60, validation phân loại,
-- thẩm quyền hai cấp, định danh địa điểm.
--
-- Idempotent. Chạy sau 02-document-manifest.sql.

--------------------------------------------------------------------------------
-- 1. Cột bổ sung trên hồ sơ
--------------------------------------------------------------------------------
ALTER TABLE app_cap_phep.ho_so
    ADD COLUMN IF NOT EXISTS cap_hanh_chinh text,
    ADD COLUMN IF NOT EXISTS doi_tuong text NOT NULL DEFAULT 'ho_gia_dinh_ca_nhan',
    ADD COLUMN IF NOT EXISTS loai_cong_trinh text NOT NULL DEFAULT 'nha_o_rieng_le',
    ADD COLUMN IF NOT EXISTS cap_cong_trinh text,
    ADD COLUMN IF NOT EXISTS trong_kcn boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS ma_dinh_danh_dia_diem text,
    ADD COLUMN IF NOT EXISTS loai_dat text NOT NULL DEFAULT 'dat_o',
    ADD COLUMN IF NOT EXISTS quy_hoach_pass boolean,
    ADD COLUMN IF NOT EXISTS quy_hoach_checked_at timestamptz;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_ho_so_ma_dinh_danh'
    ) THEN
        ALTER TABLE app_cap_phep.ho_so
            ADD CONSTRAINT chk_ho_so_ma_dinh_danh
            CHECK (ma_dinh_danh_dia_diem IS NULL OR ma_dinh_danh_dia_diem ~ '^[0-9]{12}$');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_ho_so_doi_tuong'
    ) THEN
        ALTER TABLE app_cap_phep.ho_so
            ADD CONSTRAINT chk_ho_so_doi_tuong
            CHECK (doi_tuong IN ('ho_gia_dinh_ca_nhan', 'to_chuc'));
    END IF;
END $$;

--------------------------------------------------------------------------------
-- 2. Manifest: bổ sung căn cứ pháp lý và mẫu biểu
--------------------------------------------------------------------------------
ALTER TABLE app_cap_phep.document_requirements
    ADD COLUMN IF NOT EXISTS legal_citation_key text,
    ADD COLUMN IF NOT EXISTS mau_bieu text,
    ADD COLUMN IF NOT EXISTS doi_tuong text NOT NULL DEFAULT 'tat_ca';

UPDATE app_cap_phep.document_requirements
SET legal_citation_key = CASE loai
        WHEN 'don' THEN 'ND217-D60-K3'
        WHEN 'giay_to_dat' THEN 'ND217-D55'
        WHEN 'ban_ve_mat_bang' THEN 'ND217-D60-K3'
        WHEN 'ban_ve_tang' THEN 'ND217-D60-K3'
        WHEN 'ban_ve_mong' THEN 'ND217-D60-K3'
        WHEN 'cam_ket_an_toan' THEN 'ND217-D60-K3'
        ELSE legal_citation_key
    END,
    mau_bieu = CASE WHEN loai = 'don' THEN 'Mẫu số 01 Phụ lục II NĐ 217/2026/NĐ-CP' ELSE mau_bieu END,
    doi_tuong = 'tat_ca'
WHERE legal_citation_key IS NULL;

--------------------------------------------------------------------------------
-- 3. Validation 4 loại, có severity; không chặn hồ sơ hợp pháp vì ngưỡng nội bộ
--------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_cap_phep.kiem_tra_giay_to_nop(
    p_ho_so_id uuid,
    p_tep jsonb,
    p_ho_ten text,
    p_cccd text,
    p_thua_dat text,
    p_so_tang integer,
    p_dien_tich double precision
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_items jsonb := '[]'::jsonb;
    v_req RECORD;
    v_item jsonb;
    v_file core.files%ROWTYPE;
    v_loai text;
    v_ngay_het date;
    v_thong_tin jsonb;
    v_count integer;
    v_seen_sha text[] := ARRAY[]::text[];
    v_sha text;
    v_tep jsonb := COALESCE(p_tep, '[]'::jsonb);
    v_so_loi integer := 0;
    v_so_canh_bao integer := 0;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    IF jsonb_typeof(v_tep) <> 'array' THEN
        RETURN jsonb_build_object(
            'ok', false,
            'errors', jsonb_build_array(jsonb_build_object(
                'field', 'tep', 'loai_giay', NULL, 'loai', 'technical', 'severity', 'error',
                'reason', 'Danh sách tệp không hợp lệ', 'action', 'fix_payload'
            )),
            'so_loi', 1, 'so_canh_bao', 0
        );
    END IF;

    -- L1: hiện diện đủ giấy tờ bắt buộc (LEGAL_VALIDATION, chặn)
    FOR v_req IN
        SELECT * FROM app_cap_phep.document_requirements
        WHERE bat_buoc = true
        ORDER BY thu_tu, loai
    LOOP
        SELECT count(*) INTO v_count
        FROM jsonb_array_elements(v_tep) AS e
        WHERE e->>'loai' = v_req.loai;

        IF v_count = 0 THEN
            v_items := v_items || jsonb_build_object(
                'field', 'tep.' || v_req.loai,
                'loai_giay', v_req.loai,
                'loai', 'legal',
                'severity', 'error',
                'reason', 'Thiếu ' || v_req.ten,
                'legal_citation_key', v_req.legal_citation_key,
                'action', 'upload'
            );
        END IF;
    END LOOP;

    -- Kiểm tra từng tệp
    FOR v_item IN SELECT * FROM jsonb_array_elements(v_tep)
    LOOP
        v_loai := NULLIF(btrim(COALESCE(v_item->>'loai', '')), '');

        IF v_loai IS NULL THEN
            v_items := v_items || jsonb_build_object(
                'field', 'tep', 'loai_giay', NULL, 'loai', 'technical', 'severity', 'error',
                'reason', 'Tệp thiếu loại giấy', 'action', 'choose_type'
            );
            CONTINUE;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM app_cap_phep.document_requirements WHERE loai = v_loai) THEN
            v_items := v_items || jsonb_build_object(
                'field', 'tep.' || v_loai, 'loai_giay', v_loai, 'loai', 'technical', 'severity', 'error',
                'reason', 'Loại giấy không hợp lệ: ' || v_loai, 'action', 'choose_type'
            );
            CONTINUE;
        END IF;

        IF (v_item->>'file_id') IS NULL OR (v_item->>'file_id') !~* '^[0-9a-f-]{36}$' THEN
            v_items := v_items || jsonb_build_object(
                'field', 'tep.' || v_loai, 'loai_giay', v_loai, 'loai', 'technical', 'severity', 'error',
                'reason', 'Tệp chưa được tải lên hợp lệ', 'action', 'upload'
            );
            CONTINUE;
        END IF;

        SELECT * INTO v_file
        FROM core.files
        WHERE id = (v_item->>'file_id')::uuid
          AND tenant = cur_tenant;

        IF v_file.id IS NULL THEN
            v_items := v_items || jsonb_build_object(
                'field', 'tep.' || v_loai, 'loai_giay', v_loai, 'loai', 'legal', 'severity', 'error',
                'reason', 'Tệp không tồn tại hoặc không thuộc địa bàn', 'action', 'upload'
            );
            CONTINUE;
        END IF;

        IF v_file.owner_sub <> cur_sub THEN
            v_items := v_items || jsonb_build_object(
                'field', 'tep.' || v_loai, 'loai_giay', v_loai, 'loai', 'legal', 'severity', 'error',
                'reason', 'Tệp không thuộc người nộp', 'action', 'upload'
            );
            CONTINUE;
        END IF;

        IF v_file.status <> 'clean' THEN
            v_items := v_items || jsonb_build_object(
                'field', 'tep.' || v_loai, 'loai_giay', v_loai, 'loai', 'technical', 'severity', 'error',
                'reason', 'Tệp chưa vượt qua kiểm dịch ClamAV', 'action', 'upload'
            );
            CONTINUE;
        END IF;

        -- L6: trùng SHA-256 trong cùng hồ sơ (TECHNICAL_VALIDATION, chặn)
        v_sha := v_file.sha256;
        IF v_sha IS NOT NULL THEN
            IF v_sha = ANY (v_seen_sha) THEN
                v_items := v_items || jsonb_build_object(
                    'field', 'tep.' || v_loai, 'loai_giay', v_loai, 'loai', 'technical', 'severity', 'error',
                    'reason', 'Tệp đã tồn tại trong hồ sơ (trùng SHA-256)', 'action', 'replace'
                );
            END IF;
            v_seen_sha := array_append(v_seen_sha, v_sha);
        END IF;

        -- L4: hiệu lực giấy tờ (LEGAL_VALIDATION, chặn nếu đã hết hạn)
        IF NULLIF(v_item->>'ngay_het_han', '') IS NOT NULL THEN
            v_ngay_het := (v_item->>'ngay_het_han')::date;
            IF v_ngay_het < CURRENT_DATE THEN
                v_items := v_items || jsonb_build_object(
                    'field', 'ngay_het_han.' || v_loai, 'loai_giay', v_loai, 'loai', 'legal', 'severity', 'error',
                    'reason', 'Giấy tờ đã hết hạn vào ' || to_char(v_ngay_het, 'DD/MM/YYYY'), 'action', 'replace'
                );
            END IF;
        ELSIF (SELECT yeu_cau_hieu_luc FROM app_cap_phep.document_requirements WHERE loai = v_loai) THEN
            v_items := v_items || jsonb_build_object(
                'field', 'ngay_het_han.' || v_loai, 'loai_giay', v_loai, 'loai', 'legal', 'severity', 'error',
                'reason', 'Thiếu ngày hết hạn của giấy tờ bắt buộc còn hiệu lực', 'action', 'declare_expiry'
            );
        END IF;

        -- L5: nhất quán chéo
        v_thong_tin := COALESCE(v_item->'thong_tin', '{}'::jsonb);
        IF v_loai = 'don' THEN
            IF NULLIF(v_thong_tin->>'ho_ten', '') IS NOT NULL
               AND p_ho_ten IS NOT NULL
               AND lower(btrim(v_thong_tin->>'ho_ten')) <> lower(btrim(p_ho_ten)) THEN
                v_items := v_items || jsonb_build_object(
                    'field', 'ho_ten', 'loai_giay', v_loai, 'loai', 'legal', 'severity', 'error',
                    'reason', 'Họ tên trên đơn khác hồ sơ', 'action', 'fix_form'
                );
            END IF;
            IF NULLIF(v_thong_tin->>'cccd', '') IS NOT NULL
               AND p_cccd IS NOT NULL
               AND btrim(v_thong_tin->>'cccd') <> btrim(p_cccd) THEN
                v_items := v_items || jsonb_build_object(
                    'field', 'cccd', 'loai_giay', v_loai, 'loai', 'legal', 'severity', 'error',
                    'reason', 'CCCD trên đơn khác hồ sơ', 'action', 'fix_form'
                );
            END IF;
        ELSIF v_loai = 'giay_to_dat' THEN
            IF NULLIF(v_thong_tin->>'so_thua', '') IS NOT NULL
               AND p_thua_dat IS NOT NULL
               AND lower(btrim(v_thong_tin->>'so_thua')) <> lower(btrim(p_thua_dat)) THEN
                v_items := v_items || jsonb_build_object(
                    'field', 'thua_dat', 'loai_giay', v_loai, 'loai', 'legal', 'severity', 'error',
                    'reason', 'Số thửa trên giấy đất khác hồ sơ', 'action', 'fix_form'
                );
            END IF;
            IF NULLIF(v_thong_tin->>'dien_tich', '') IS NOT NULL
               AND p_dien_tich IS NOT NULL
               AND abs((v_thong_tin->>'dien_tich')::numeric - p_dien_tich) > 0.5 THEN
                v_items := v_items || jsonb_build_object(
                    'field', 'dien_tich_san_m2', 'loai_giay', v_loai, 'loai', 'warning', 'severity', 'warning',
                    'reason', 'Diện tích trên giấy đất khác hồ sơ; cán bộ cần kiểm tra thêm', 'action', 'can_kiem_tra_them'
                );
            END IF;
        ELSIF v_loai = 'ban_ve_tang' THEN
            IF NULLIF(v_thong_tin->>'so_tang', '') IS NOT NULL
               AND p_so_tang IS NOT NULL
               AND (v_thong_tin->>'so_tang')::int <> p_so_tang THEN
                v_items := v_items || jsonb_build_object(
                    'field', 'so_tang', 'loai_giay', v_loai, 'loai', 'legal', 'severity', 'error',
                    'reason', 'Số tầng trên bản vẽ khác hồ sơ', 'action', 'fix_form'
                );
            END IF;
        END IF;
    END LOOP;

    -- L7: quy tắc nghiệp vụ (LEGAL chặn; BUSINESS/WARNING không chặn)
    IF p_ho_ten IS NULL OR length(btrim(p_ho_ten)) < 3 THEN
        v_items := v_items || jsonb_build_object(
            'field', 'ho_ten', 'loai_giay', NULL, 'loai', 'legal', 'severity', 'error',
            'reason', 'Họ tên không hợp lệ', 'action', 'fix_form'
        );
    END IF;
    IF p_cccd IS NULL OR p_cccd !~ '^[0-9]{12}$' THEN
        v_items := v_items || jsonb_build_object(
            'field', 'cccd', 'loai_giay', NULL, 'loai', 'legal', 'severity', 'error',
            'reason', 'CCCD phải gồm đúng 12 chữ số', 'action', 'fix_form'
        );
    END IF;
    IF p_so_tang IS NULL OR p_so_tang < 1 THEN
        v_items := v_items || jsonb_build_object(
            'field', 'so_tang', 'loai_giay', NULL, 'loai', 'business', 'severity', 'error',
            'reason', 'Số tầng phải là số nguyên dương', 'action', 'fix_form'
        );
    ELSIF p_so_tang > 5 THEN
        v_items := v_items || jsonb_build_object(
            'field', 'so_tang', 'loai_giay', NULL, 'loai', 'business', 'severity', 'warning',
            'reason', 'Số tầng lớn hơn ngưỡng cấu hình 5; không tự động từ chối, cán bộ cần kiểm tra thêm', 'action', 'can_kiem_tra_them'
        );
    END IF;
    IF p_dien_tich IS NULL OR p_dien_tich <= 0 THEN
        v_items := v_items || jsonb_build_object(
            'field', 'dien_tich_san_m2', 'loai_giay', NULL, 'loai', 'technical', 'severity', 'error',
            'reason', 'Diện tích sàn phải lớn hơn 0', 'action', 'fix_form'
        );
    ELSIF p_dien_tich > 500 THEN
        v_items := v_items || jsonb_build_object(
            'field', 'dien_tich_san_m2', 'loai_giay', NULL, 'loai', 'business', 'severity', 'warning',
            'reason', 'Diện tích sàn lớn hơn ngưỡng cấu hình 500 m²; không tự động từ chối, cán bộ cần kiểm tra thêm', 'action', 'can_kiem_tra_them'
        );
    END IF;

    SELECT count(*) FILTER (WHERE e->>'severity' = 'error'),
           count(*) FILTER (WHERE e->>'severity' = 'warning')
    INTO v_so_loi, v_so_canh_bao
    FROM jsonb_array_elements(v_items) e;

    RETURN jsonb_build_object(
        'ok', v_so_loi = 0,
        'errors', v_items,
        'items', v_items,
        'so_loi', v_so_loi,
        'so_canh_bao', v_so_canh_bao
    );
END;
$$;

--------------------------------------------------------------------------------
-- 4. RPC cập nhật định danh địa điểm và thẩm quyền (A-LEGAL-04, A-LEGAL-05)
--------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_cap_phep.cap_nhat_dinh_danh_dia_diem(
    p_ho_so_id uuid,
    p_ma_dinh_danh text
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
    IF p_ma_dinh_danh IS NOT NULL AND p_ma_dinh_danh !~ '^[0-9]{12}$' THEN
        RAISE EXCEPTION 'Mã định danh địa điểm phải gồm đúng 12 chữ số' USING ERRCODE = 'PT422';
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

    UPDATE app_cap_phep.ho_so
    SET ma_dinh_danh_dia_diem = p_ma_dinh_danh,
        updated_at = now()
    WHERE id = p_ho_so_id;

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'ho_so.dinh_danh_dia_diem', 'ho_so', p_ho_so_id::text,
        jsonb_build_object('ma_dinh_danh_dia_diem', p_ma_dinh_danh)
    );
    RETURN jsonb_build_object('status', 'success', 'ma_dinh_danh_dia_diem', p_ma_dinh_danh);
END;
$$;
GRANT EXECUTE ON FUNCTION app_cap_phep.cap_nhat_dinh_danh_dia_diem(uuid, text) TO web_user;

CREATE OR REPLACE FUNCTION app_cap_phep.kiem_tra_tham_quyen_ho_so(p_ho_so_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, app_construction_private, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    v_hs app_cap_phep.ho_so%ROWTYPE;
    v_result jsonb;
BEGIN
    IF coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO v_hs FROM app_cap_phep.ho_so
    WHERE id = p_ho_so_id AND tenant = cur_tenant;
    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ trong địa bàn' USING ERRCODE = '42501';
    END IF;

    v_result := app_construction_private.xac_dinh_tham_quyen(
        v_hs.loai_cong_trinh, v_hs.cap_cong_trinh, v_hs.doi_tuong, v_hs.trong_kcn, v_hs.cap_hanh_chinh
    );
    PERFORM core.record_audit(
        cur_tenant, core.jwt_sub(), 'user', 'ho_so.kiem_tra_tham_quyen', 'ho_so', p_ho_so_id::text,
        jsonb_build_object('ket_qua', v_result)
    );
    RETURN v_result;
END;
$$;
GRANT EXECUTE ON FUNCTION app_cap_phep.kiem_tra_tham_quyen_ho_so(uuid) TO web_user;

--------------------------------------------------------------------------------
-- 5. View bổ sung cho UI quy hoạch
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS app_cap_phep.v_ho_so_quy_hoach CASCADE;
CREATE VIEW app_cap_phep.v_ho_so_quy_hoach WITH (security_invoker = true) AS
SELECT h.id, h.tenant, h.ma_ho_so, h.thua_dat, h.loai_dat, h.ma_dinh_danh_dia_diem,
       h.so_tang, h.dien_tich_san_m2, h.doi_tuong, h.loai_cong_trinh, h.cap_cong_trinh,
       h.trong_kcn, h.cap_hanh_chinh, h.quy_hoach_pass, h.quy_hoach_checked_at,
       k.id AS ket_qua_id, k.pass AS ket_qua_pass, k.so_loi, k.so_canh_bao, k.created_at AS ket_qua_luc
FROM app_cap_phep.ho_so h
LEFT JOIN LATERAL (
    SELECT id, pass, so_loi, so_canh_bao, created_at
    FROM app_construction.ket_qua_kiem_tra_quy_hoach q
    WHERE q.ho_so_id = h.id AND q.tenant = h.tenant
    ORDER BY created_at DESC
    LIMIT 1
) k ON true;

ALTER VIEW app_cap_phep.v_ho_so_quy_hoach OWNER TO dxos_owner;
GRANT SELECT ON app_cap_phep.v_ho_so_quy_hoach TO web_user, dxos_svc, svc;

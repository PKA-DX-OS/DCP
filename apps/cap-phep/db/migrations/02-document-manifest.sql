-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 02-document-manifest.sql
-- P1: Manifest giấy tờ bắt buộc + 7 lớp kiểm tra trước khi nộp.
-- Bổ sung metadata/version/review cho ho_so_tep và RPC nộp hồ sơ có kiểm tra.
--
-- Chạy sau 01-app-cap-phep.sql; chạy lại an toàn (IF NOT EXISTS / OR REPLACE).
-- Chỉ thêm cột vào ho_so_tep, không xóa cột hay dữ liệu của migration 01.
--
-- Rollback / vô hiệu hóa an toàn:
--   * Tắt kiểm tra manifest mà không mất dữ liệu: đặt bat_buoc = false
--     trong app_cap_phep.document_requirements (hoặc bỏ loại khỏi app.yaml rồi cài lại).
--   * Gỡ hẳn phần bổ sung (chỉ khi chấp nhận mất metadata tệp):
--       DROP FUNCTION IF EXISTS app_cap_phep.giay_to_con_thieu(uuid);
--       DROP VIEW IF EXISTS app_cap_phep.document_manifest;
--       DROP FUNCTION IF EXISTS app_cap_phep.danh_gia_tep(uuid, text, text);
--       DROP FUNCTION IF EXISTS app_cap_phep.kiem_tra_giay_to_nop(uuid, jsonb, text, text, text, integer, double precision);
--       DROP TABLE IF EXISTS app_cap_phep.document_requirements;
--     rồi chạy lại 01-app-cap-phep.sql để khôi phục nop_ho_so, dinh_kem_tep, v_ho_so_tep bản gốc.
--     Các cột thêm vào ho_so_tep có giá trị mặc định nên để lại không ảnh hưởng.

--------------------------------------------------------------------------------
-- 1. Bảng yêu cầu giấy tờ (seed từ app.yaml document_manifest)
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_cap_phep.document_requirements (
    loai text PRIMARY KEY,
    ten text NOT NULL,
    bat_buoc boolean NOT NULL DEFAULT true,
    yeu_cau_hieu_luc boolean NOT NULL DEFAULT false,
    thong_tin jsonb NOT NULL DEFAULT '[]'::jsonb,
    mo_ta text,
    thu_tu integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE app_cap_phep.document_requirements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_document_requirements_read ON app_cap_phep.document_requirements;
CREATE POLICY rls_document_requirements_read ON app_cap_phep.document_requirements
    FOR SELECT TO web_user USING (true);
GRANT SELECT ON app_cap_phep.document_requirements TO web_user, dxos_owner, dxos_svc, svc;

--------------------------------------------------------------------------------
-- 2. Nâng cấp ho_so_tep: metadata, trạng thái review, versioning
--------------------------------------------------------------------------------
ALTER TABLE app_cap_phep.ho_so_tep
    ADD COLUMN IF NOT EXISTS sha256 text,
    ADD COLUMN IF NOT EXISTS size bigint,
    ADD COLUMN IF NOT EXISTS mime text,
    ADD COLUMN IF NOT EXISTS nguoi_tai text,
    ADD COLUMN IF NOT EXISTS tai_luc timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS trang_thai_kiem_tra text NOT NULL DEFAULT 'cho_kiem_tra',
    ADD COLUMN IF NOT EXISTS ly_do text,
    ADD COLUMN IF NOT EXISTS ngay_cap date,
    ADD COLUMN IF NOT EXISTS ngay_het_han date,
    ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS tep_goc_id uuid,
    ADD COLUMN IF NOT EXISTS thong_tin jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS nguoi_kiem_tra text,
    ADD COLUMN IF NOT EXISTS kiem_tra_luc timestamptz;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_ho_so_tep_trang_thai'
          AND conrelid = 'app_cap_phep.ho_so_tep'::regclass
    ) THEN
        ALTER TABLE app_cap_phep.ho_so_tep
            ADD CONSTRAINT chk_ho_so_tep_trang_thai
            CHECK (trang_thai_kiem_tra IN ('cho_kiem_tra', 'dat', 'khong_dat', 'cach_ly'));
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ho_so_tep_sha256
    ON app_cap_phep.ho_so_tep (ho_so_id, sha256)
    WHERE sha256 IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ho_so_tep_ho_so
    ON app_cap_phep.ho_so_tep (ho_so_id, loai, version DESC);

--------------------------------------------------------------------------------
-- 3. Cập nhật view chi tiết tệp (thêm metadata/review)
--------------------------------------------------------------------------------
DROP VIEW IF EXISTS app_cap_phep.v_ho_so_tep CASCADE;
CREATE VIEW app_cap_phep.v_ho_so_tep WITH (security_invoker = true) AS
SELECT
    t.id,
    t.ho_so_id,
    t.file_id,
    t.loai,
    t.created_at,
    t.sha256,
    t.size,
    t.mime,
    t.nguoi_tai,
    t.tai_luc,
    t.trang_thai_kiem_tra,
    t.ly_do,
    t.ngay_cap,
    t.ngay_het_han,
    t.version,
    t.tep_goc_id,
    t.thong_tin,
    t.nguoi_kiem_tra,
    t.kiem_tra_luc,
    f.object_key,
    f.status,
    f.status AS file_status,
    r.ten AS ten_loai,
    r.bat_buoc
FROM app_cap_phep.ho_so_tep t
LEFT JOIN core.files f ON t.file_id = f.id
LEFT JOIN app_cap_phep.document_requirements r ON r.loai = t.loai;

ALTER VIEW app_cap_phep.v_ho_so_tep OWNER TO dxos_owner;
GRANT SELECT ON app_cap_phep.v_ho_so_tep TO web_user, dxos_owner, dxos_svc, svc;

--------------------------------------------------------------------------------
-- 4. Hàm kiểm tra 7 lớp trước khi nộp
--    L1 hiện diện, L2/L3 do service files đảm bảo, L4 hiệu lực,
--    L5 nhất quán chéo, L6 trùng SHA-256, L7 nghiệp vụ.
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
    v_errors jsonb := '[]'::jsonb;
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
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    IF jsonb_typeof(v_tep) <> 'array' THEN
        RETURN jsonb_build_object(
            'ok', false,
            'errors', jsonb_build_array(jsonb_build_object(
                'field', 'tep',
                'loai_giay', NULL,
                'reason', 'Danh sách tệp không hợp lệ',
                'action', 'fix_payload'
            ))
        );
    END IF;

    -- L1: đủ loại giấy bắt buộc
    FOR v_req IN
        SELECT * FROM app_cap_phep.document_requirements
        WHERE bat_buoc = true
        ORDER BY thu_tu, loai
    LOOP
        SELECT count(*) INTO v_count
        FROM jsonb_array_elements(v_tep) AS e
        WHERE e->>'loai' = v_req.loai;

        IF v_count = 0 THEN
            v_errors := v_errors || jsonb_build_object(
                'field', 'tep.' || v_req.loai,
                'loai_giay', v_req.loai,
                'reason', 'Thiếu ' || v_req.ten,
                'action', 'upload'
            );
        END IF;
    END LOOP;

    -- Kiểm tra từng tệp
    FOR v_item IN SELECT * FROM jsonb_array_elements(v_tep)
    LOOP
        v_loai := NULLIF(btrim(COALESCE(v_item->>'loai', '')), '');

        IF v_loai IS NULL THEN
            v_errors := v_errors || jsonb_build_object(
                'field', 'tep',
                'loai_giay', NULL,
                'reason', 'Tệp thiếu loại giấy',
                'action', 'choose_type'
            );
            CONTINUE;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM app_cap_phep.document_requirements WHERE loai = v_loai) THEN
            v_errors := v_errors || jsonb_build_object(
                'field', 'tep.' || v_loai,
                'loai_giay', v_loai,
                'reason', 'Loại giấy không hợp lệ: ' || v_loai,
                'action', 'choose_type'
            );
            CONTINUE;
        END IF;

        IF (v_item->>'file_id') IS NULL OR (v_item->>'file_id') !~* '^[0-9a-f-]{36}$' THEN
            v_errors := v_errors || jsonb_build_object(
                'field', 'tep.' || v_loai,
                'loai_giay', v_loai,
                'reason', 'Tệp chưa được tải lên hợp lệ',
                'action', 'upload'
            );
            CONTINUE;
        END IF;

        SELECT * INTO v_file
        FROM core.files
        WHERE id = (v_item->>'file_id')::uuid
          AND tenant = cur_tenant;

        IF v_file.id IS NULL THEN
            v_errors := v_errors || jsonb_build_object(
                'field', 'tep.' || v_loai,
                'loai_giay', v_loai,
                'reason', 'Tệp không tồn tại hoặc không thuộc địa bàn',
                'action', 'upload'
            );
            CONTINUE;
        END IF;

        IF v_file.owner_sub <> cur_sub THEN
            v_errors := v_errors || jsonb_build_object(
                'field', 'tep.' || v_loai,
                'loai_giay', v_loai,
                'reason', 'Tệp không thuộc người nộp',
                'action', 'upload'
            );
            CONTINUE;
        END IF;

        -- L2/L3: service files đã kiểm magic bytes, size và ClamAV
        IF v_file.status <> 'clean' THEN
            v_errors := v_errors || jsonb_build_object(
                'field', 'tep.' || v_loai,
                'loai_giay', v_loai,
                'reason', 'Tệp chưa vượt qua kiểm dịch ClamAV',
                'action', 'upload'
            );
            CONTINUE;
        END IF;

        -- L6: trùng SHA-256 trong cùng hồ sơ
        v_sha := v_file.sha256;
        IF v_sha IS NOT NULL THEN
            IF v_sha = ANY (v_seen_sha) THEN
                v_errors := v_errors || jsonb_build_object(
                    'field', 'tep.' || v_loai,
                    'loai_giay', v_loai,
                    'reason', 'Tệp đã tồn tại trong hồ sơ (trùng SHA-256)',
                    'action', 'replace'
                );
            END IF;
            v_seen_sha := array_append(v_seen_sha, v_sha);
        END IF;

        -- L4: hiệu lực
        IF NULLIF(v_item->>'ngay_het_han', '') IS NOT NULL THEN
            v_ngay_het := (v_item->>'ngay_het_han')::date;
            IF v_ngay_het < CURRENT_DATE THEN
                v_errors := v_errors || jsonb_build_object(
                    'field', 'ngay_het_han.' || v_loai,
                    'loai_giay', v_loai,
                    'reason', 'Giấy tờ đã hết hạn vào ' || to_char(v_ngay_het, 'DD/MM/YYYY'),
                    'action', 'replace'
                );
            END IF;
        ELSIF (SELECT yeu_cau_hieu_luc FROM app_cap_phep.document_requirements WHERE loai = v_loai) THEN
            v_errors := v_errors || jsonb_build_object(
                'field', 'ngay_het_han.' || v_loai,
                'loai_giay', v_loai,
                'reason', 'Thiếu ngày hết hạn của giấy tờ bắt buộc còn hiệu lực',
                'action', 'declare_expiry'
            );
        END IF;

        -- L5: nhất quán chéo giữa đơn/giấy đất/bản vẽ và form
        v_thong_tin := COALESCE(v_item->'thong_tin', '{}'::jsonb);

        IF v_loai = 'don' THEN
            IF NULLIF(v_thong_tin->>'ho_ten', '') IS NOT NULL
               AND p_ho_ten IS NOT NULL
               AND lower(btrim(v_thong_tin->>'ho_ten')) <> lower(btrim(p_ho_ten)) THEN
                v_errors := v_errors || jsonb_build_object(
                    'field', 'ho_ten',
                    'loai_giay', v_loai,
                    'reason', 'Họ tên trên đơn khác hồ sơ',
                    'action', 'fix_form'
                );
            END IF;
            IF NULLIF(v_thong_tin->>'cccd', '') IS NOT NULL
               AND p_cccd IS NOT NULL
               AND btrim(v_thong_tin->>'cccd') <> btrim(p_cccd) THEN
                v_errors := v_errors || jsonb_build_object(
                    'field', 'cccd',
                    'loai_giay', v_loai,
                    'reason', 'CCCD trên đơn khác hồ sơ',
                    'action', 'fix_form'
                );
            END IF;
        ELSIF v_loai = 'giay_to_dat' THEN
            IF NULLIF(v_thong_tin->>'so_thua', '') IS NOT NULL
               AND p_thua_dat IS NOT NULL
               AND lower(btrim(v_thong_tin->>'so_thua')) <> lower(btrim(p_thua_dat)) THEN
                v_errors := v_errors || jsonb_build_object(
                    'field', 'thua_dat',
                    'loai_giay', v_loai,
                    'reason', 'Số thửa trên giấy đất khác hồ sơ',
                    'action', 'fix_form'
                );
            END IF;
            IF NULLIF(v_thong_tin->>'dien_tich', '') IS NOT NULL
               AND p_dien_tich IS NOT NULL
               AND abs((v_thong_tin->>'dien_tich')::numeric - p_dien_tich) > 0.5 THEN
                v_errors := v_errors || jsonb_build_object(
                    'field', 'dien_tich_san_m2',
                    'loai_giay', v_loai,
                    'reason', 'Diện tích trên giấy đất khác hồ sơ',
                    'action', 'fix_form'
                );
            END IF;
        ELSIF v_loai = 'ban_ve_tang' THEN
            IF NULLIF(v_thong_tin->>'so_tang', '') IS NOT NULL
               AND p_so_tang IS NOT NULL
               AND (v_thong_tin->>'so_tang')::int <> p_so_tang THEN
                v_errors := v_errors || jsonb_build_object(
                    'field', 'so_tang',
                    'loai_giay', v_loai,
                    'reason', 'Số tầng trên bản vẽ khác hồ sơ',
                    'action', 'fix_form'
                );
            END IF;
        END IF;
    END LOOP;

    -- L7: quy tắc nghiệp vụ
    IF p_ho_ten IS NULL OR length(btrim(p_ho_ten)) < 3 THEN
        v_errors := v_errors || jsonb_build_object(
            'field', 'ho_ten', 'loai_giay', NULL,
            'reason', 'Họ tên không hợp lệ', 'action', 'fix_form'
        );
    END IF;
    IF p_cccd IS NULL OR p_cccd !~ '^[0-9]{12}$' THEN
        v_errors := v_errors || jsonb_build_object(
            'field', 'cccd', 'loai_giay', NULL,
            'reason', 'CCCD phải gồm đúng 12 chữ số', 'action', 'fix_form'
        );
    END IF;
    IF p_so_tang IS NULL OR p_so_tang < 1 OR p_so_tang > 5 THEN
        v_errors := v_errors || jsonb_build_object(
            'field', 'so_tang', 'loai_giay', NULL,
            'reason', 'Số tầng phải từ 1 đến 5 với nhà ở riêng lẻ', 'action', 'fix_form'
        );
    END IF;
    IF p_dien_tich IS NULL OR p_dien_tich <= 0 OR p_dien_tich > 500 THEN
        v_errors := v_errors || jsonb_build_object(
            'field', 'dien_tich_san_m2', 'loai_giay', NULL,
            'reason', 'Diện tích sàn phải trong khoảng 0-500 m²', 'action', 'fix_form'
        );
    END IF;

    RETURN jsonb_build_object(
        'ok', jsonb_array_length(v_errors) = 0,
        'errors', v_errors
    );
END;
$$;

REVOKE ALL ON FUNCTION app_cap_phep.kiem_tra_giay_to_nop(uuid, jsonb, text, text, text, integer, double precision) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION app_cap_phep.kiem_tra_giay_to_nop(uuid, jsonb, text, text, text, integer, double precision) TO web_user, svc, dxos_svc, dxos_owner;

--------------------------------------------------------------------------------
-- 5. RPC nộp hồ sơ có kiểm tra manifest (fail-closed)
--------------------------------------------------------------------------------
DROP FUNCTION IF EXISTS app_cap_phep.nop_ho_so(text, text, text, text, text, integer, double precision, boolean);

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
    v_han_tong := core.add_business_days(now(), 15);

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

GRANT EXECUTE ON FUNCTION app_cap_phep.nop_ho_so(text, text, text, text, text, integer, double precision, boolean, uuid, jsonb) TO web_user;

--------------------------------------------------------------------------------
-- 6. Nâng cấp dinh_kem_tep: validate loại, chống trùng, versioning
--------------------------------------------------------------------------------
DROP FUNCTION IF EXISTS app_cap_phep.dinh_kem_tep(uuid, uuid, text);

CREATE OR REPLACE FUNCTION app_cap_phep.dinh_kem_tep(
    p_ho_so_id uuid,
    p_file_id uuid,
    p_loai text,
    p_ngay_cap date DEFAULT NULL,
    p_ngay_het_han date DEFAULT NULL,
    p_thong_tin jsonb DEFAULT '{}'::jsonb
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
    v_file core.files%ROWTYPE;
    v_req app_cap_phep.document_requirements%ROWTYPE;
    v_has_access boolean := false;
    v_version integer := 1;
    v_prev_id uuid;
    v_tep_id uuid;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO v_req FROM app_cap_phep.document_requirements WHERE loai = p_loai;
    IF v_req.loai IS NULL THEN
        RAISE EXCEPTION 'Loại giấy không hợp lệ: %', p_loai USING ERRCODE = 'PT422';
    END IF;

    SELECT * INTO v_hs
    FROM app_cap_phep.ho_so
    WHERE id = p_ho_so_id AND tenant = cur_tenant;

    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Hồ sơ không tồn tại hoặc không thuộc địa bàn của bạn' USING ERRCODE = '42501';
    END IF;

    IF v_hs.chu_dau_tu_sub = cur_sub THEN
        IF v_hs.trang_thai NOT IN ('DA_NOP', 'CAN_BO_SUNG') THEN
            RAISE EXCEPTION 'Hồ sơ đang trong quy trình xử lý, không thể đính kèm thêm tệp' USING ERRCODE = '42501';
        END IF;
        v_has_access := true;
    ELSE
        v_has_access := app_cap_phep_private.can_access_ho_so(p_ho_so_id::text, 'write');
    END IF;

    IF NOT v_has_access THEN
        RAISE EXCEPTION 'Bạn không có quyền đính kèm tệp vào hồ sơ này' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO v_file
    FROM core.files
    WHERE id = p_file_id AND tenant = cur_tenant;

    IF v_file.id IS NULL THEN
        RAISE EXCEPTION 'Tệp không tồn tại hoặc không thuộc địa bàn' USING ERRCODE = '42501';
    END IF;
    IF v_file.owner_sub <> cur_sub THEN
        RAISE EXCEPTION 'Tệp không thuộc người tải lên' USING ERRCODE = '42501';
    END IF;
    IF v_file.status <> 'clean' THEN
        RAISE EXCEPTION 'Tệp chưa vượt qua kiểm dịch ClamAV' USING ERRCODE = 'PT422';
    END IF;

    -- L6: không cho trùng SHA-256 trong cùng hồ sơ
    IF EXISTS (
        SELECT 1 FROM app_cap_phep.ho_so_tep
        WHERE ho_so_id = p_ho_so_id AND sha256 = v_file.sha256
    ) THEN
        RAISE EXCEPTION 'Tệp đã tồn tại trong hồ sơ (trùng SHA-256)'
            USING ERRCODE = 'PT422';
    END IF;

    SELECT COALESCE(max(version), 0) + 1 INTO v_version
    FROM app_cap_phep.ho_so_tep
    WHERE ho_so_id = p_ho_so_id AND loai = p_loai;

    SELECT id INTO v_prev_id
    FROM app_cap_phep.ho_so_tep
    WHERE ho_so_id = p_ho_so_id AND loai = p_loai
    ORDER BY version DESC
    LIMIT 1;

    INSERT INTO app_cap_phep.ho_so_tep (
        ho_so_id, file_id, loai, sha256, size, mime,
        nguoi_tai, tai_luc, trang_thai_kiem_tra,
        ngay_cap, ngay_het_han, version, tep_goc_id, thong_tin
    ) VALUES (
        p_ho_so_id, v_file.id, p_loai, v_file.sha256, v_file.size, v_file.mime,
        cur_sub, now(), 'cho_kiem_tra',
        p_ngay_cap, p_ngay_het_han, v_version, v_prev_id, COALESCE(p_thong_tin, '{}'::jsonb)
    )
    RETURNING id INTO v_tep_id;

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'ho_so_tep.dinh_kem', 'ho_so', p_ho_so_id::text,
        jsonb_build_object('tep_id', v_tep_id, 'loai', p_loai, 'version', v_version)
    );

    RETURN jsonb_build_object(
        'status', 'success',
        'tep_id', v_tep_id,
        'loai', p_loai,
        'version', v_version
    );
END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep.dinh_kem_tep(uuid, uuid, text, date, date, jsonb) TO web_user;

--------------------------------------------------------------------------------
-- 7. RPC đánh giá từng tệp (P3)
--------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_cap_phep.danh_gia_tep(
    p_tep_id uuid,
    p_trang_thai text,
    p_ly_do text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_tep app_cap_phep.ho_so_tep%ROWTYPE;
    v_hs app_cap_phep.ho_so%ROWTYPE;
    v_allowed boolean := false;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    IF p_trang_thai NOT IN ('dat', 'khong_dat') THEN
        RAISE EXCEPTION 'Trạng thái đánh giá không hợp lệ' USING ERRCODE = 'PT422';
    END IF;

    IF p_trang_thai = 'khong_dat' AND coalesce(btrim(p_ly_do), '') = '' THEN
        RAISE EXCEPTION 'Phải nhập lý do khi đánh giá không đạt' USING ERRCODE = 'PT422';
    END IF;

    SELECT * INTO v_tep FROM app_cap_phep.ho_so_tep WHERE id = p_tep_id;
    IF v_tep.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy tệp' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO v_hs FROM app_cap_phep.ho_so WHERE id = v_tep.ho_so_id AND tenant = cur_tenant;
    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Tệp không thuộc địa bàn' USING ERRCODE = '42501';
    END IF;

    v_allowed := core.has_role('app:cap-phep:mot-cua')
              OR core.has_role('app:cap-phep:tham-dinh')
              OR core.has_role('app:cap-phep:lanh-dao')
              OR core.has_role('app:cap-phep:trat-tu-xd');

    IF NOT v_allowed OR NOT app_cap_phep_private.can_access_ho_so(v_tep.ho_so_id::text, 'write') THEN
        RAISE EXCEPTION 'Bạn không có quyền đánh giá tệp của hồ sơ này' USING ERRCODE = '42501';
    END IF;

    UPDATE app_cap_phep.ho_so_tep
    SET trang_thai_kiem_tra = p_trang_thai,
        ly_do = p_ly_do,
        nguoi_kiem_tra = cur_sub,
        kiem_tra_luc = now()
    WHERE id = p_tep_id;

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'ho_so_tep.danh_gia', 'ho_so', v_tep.ho_so_id::text,
        jsonb_build_object('tep_id', p_tep_id, 'loai', v_tep.loai, 'trang_thai', p_trang_thai, 'ly_do', p_ly_do)
    );

    RETURN jsonb_build_object('status', 'success', 'tep_id', p_tep_id, 'trang_thai', p_trang_thai);
END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep.danh_gia_tep(uuid, text, text) TO web_user;

--------------------------------------------------------------------------------
-- 8. Manifest giấy tờ của từng hồ sơ: mỗi loại giấy bắt buộc kèm bản tệp đang hiệu lực
--    (phiên bản mới nhất). security_invoker: RLS của ho_so/ho_so_tep áp dụng nguyên vẹn,
--    chủ hồ sơ chỉ thấy hồ sơ của mình, cán bộ chỉ thấy hồ sơ trong địa bàn.
--------------------------------------------------------------------------------
CREATE OR REPLACE VIEW app_cap_phep.document_manifest WITH (security_invoker = true) AS
SELECT
    hs.id AS ho_so_id,
    hs.tenant,
    hs.ma_ho_so,
    r.loai,
    r.ten,
    r.bat_buoc,
    r.thu_tu,
    t.id AS tep_id,
    t.file_id,
    t.version,
    t.trang_thai_kiem_tra,
    t.ly_do,
    t.ngay_het_han,
    CASE
        WHEN t.id IS NULL THEN 'thieu'
        WHEN t.trang_thai_kiem_tra IN ('khong_dat', 'cach_ly') THEN t.trang_thai_kiem_tra
        WHEN r.yeu_cau_hieu_luc AND t.ngay_het_han IS NOT NULL AND t.ngay_het_han < current_date THEN 'het_han'
        ELSE 'co'
    END AS tinh_trang
FROM app_cap_phep.ho_so hs
CROSS JOIN app_cap_phep.document_requirements r
LEFT JOIN LATERAL (
    SELECT * FROM app_cap_phep.ho_so_tep x
    WHERE x.ho_so_id = hs.id AND x.loai = r.loai
    ORDER BY x.version DESC
    LIMIT 1
) t ON true;

GRANT SELECT ON app_cap_phep.document_manifest TO web_user, dxos_owner, dxos_svc, svc;

-- RPC: danh sách giấy tờ bắt buộc còn thiếu / không đạt / hết hạn của một hồ sơ.
-- Rỗng nghĩa là đủ giấy tờ để chuyển bước.
CREATE OR REPLACE FUNCTION app_cap_phep.giay_to_con_thieu(p_ho_so_id uuid)
RETURNS TABLE (loai text, ten text, tinh_trang text)
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = app_cap_phep, pg_temp
AS $$
    SELECT m.loai, m.ten, m.tinh_trang
    FROM app_cap_phep.document_manifest m
    WHERE m.ho_so_id = p_ho_so_id
      AND m.bat_buoc
      AND m.tinh_trang <> 'co'
    ORDER BY m.thu_tu, m.loai;
$$;

-- Chỉ dịch vụ nền dùng; giao diện đọc document_manifest trực tiếp nên không mở RPC này cho web_user.
REVOKE ALL ON FUNCTION app_cap_phep.giay_to_con_thieu(uuid) FROM PUBLIC, web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.giay_to_con_thieu(uuid) TO svc, dxos_svc, dxos_owner;

NOTIFY pgrst, 'reload schema';

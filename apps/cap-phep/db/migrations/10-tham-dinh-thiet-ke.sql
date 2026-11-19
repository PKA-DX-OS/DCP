-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 10-tham-dinh-thiet-ke.sql — Track B / 5.2: bản vẽ, phiên bản, nhận xét thẩm định.
-- Hợp đồng: contracts/design-review.yaml.
-- Idempotent. Chạy sau các migration của app cấp phép.

CREATE SCHEMA IF NOT EXISTS app_cap_phep AUTHORIZATION dxos_owner;
CREATE SCHEMA IF NOT EXISTS app_cap_phep_private AUTHORIZATION dxos_owner;

--------------------------------------------------------------------------------
-- 1. Danh mục bộ môn
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_cap_phep.bo_mon_thiet_ke (
    ma text PRIMARY KEY,
    ten text NOT NULL,
    bat_buoc boolean NOT NULL DEFAULT true,
    thu_tu integer NOT NULL DEFAULT 100
);

INSERT INTO app_cap_phep.bo_mon_thiet_ke (ma, ten, bat_buoc, thu_tu)
VALUES
    ('kien_truc', 'Kiến trúc', true, 10),
    ('ket_cau', 'Kết cấu', true, 20),
    ('mep', 'Cơ điện (MEP)', true, 30),
    ('pccc', 'Phòng cháy chữa cháy', false, 40)
ON CONFLICT (ma) DO UPDATE
SET ten = EXCLUDED.ten, bat_buoc = EXCLUDED.bat_buoc, thu_tu = EXCLUDED.thu_tu;

--------------------------------------------------------------------------------
-- 2. Bảng nghiệp vụ
--------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_cap_phep.phien_ban_thiet_ke (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ho_so_id uuid NOT NULL REFERENCES app_cap_phep.ho_so(id) ON DELETE CASCADE,
    so_phien_ban integer NOT NULL,
    mo_ta_thay_doi text NOT NULL,
    trang_thai text NOT NULL DEFAULT 'dang_soan',
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    idempotency_key text,
    UNIQUE (tenant, ho_so_id, so_phien_ban),
    UNIQUE (tenant, idempotency_key),
    CONSTRAINT chk_phien_ban_trang_thai CHECK (trang_thai IN ('dang_soan', 'dang_tham_dinh', 'dat', 'khong_dat'))
);

CREATE INDEX IF NOT EXISTS idx_phien_ban_thiet_ke_ho_so
    ON app_cap_phep.phien_ban_thiet_ke (tenant, ho_so_id, so_phien_ban DESC);

CREATE TABLE IF NOT EXISTS app_cap_phep.ban_ve (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    phien_ban_id uuid NOT NULL REFERENCES app_cap_phep.phien_ban_thiet_ke(id) ON DELETE CASCADE,
    ho_so_id uuid NOT NULL REFERENCES app_cap_phep.ho_so(id) ON DELETE CASCADE,
    bo_mon text NOT NULL REFERENCES app_cap_phep.bo_mon_thiet_ke(ma),
    ten text NOT NULL,
    file_id uuid NOT NULL,
    sha256 text NOT NULL,
    kich_thuoc bigint,
    trang_thai text NOT NULL DEFAULT 'cho_tham_dinh',
    nguoi_tham_dinh text,
    ngay_tham_dinh timestamptz,
    created_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    idempotency_key text,
    UNIQUE (tenant, phien_ban_id, file_id),
    UNIQUE (tenant, idempotency_key),
    CONSTRAINT chk_ban_ve_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT chk_ban_ve_trang_thai CHECK (trang_thai IN ('cho_tham_dinh', 'dat', 'khong_dat'))
);

CREATE INDEX IF NOT EXISTS idx_ban_ve_phien_ban
    ON app_cap_phep.ban_ve (tenant, phien_ban_id, bo_mon, created_at);

ALTER TABLE app_cap_phep.ban_ve
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS app_cap_phep.nhan_xet_tham_dinh (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ban_ve_id uuid NOT NULL REFERENCES app_cap_phep.ban_ve(id) ON DELETE CASCADE,
    phien_ban_id uuid NOT NULL REFERENCES app_cap_phep.phien_ban_thiet_ke(id) ON DELETE CASCADE,
    bo_mon text NOT NULL REFERENCES app_cap_phep.bo_mon_thiet_ke(ma),
    nguoi_sub text,
    nguoi text NOT NULL,
    noi_dung text NOT NULL,
    muc_do text NOT NULL DEFAULT 'gop_y',
    trang_thai text NOT NULL DEFAULT 'mo',
    ghi_chu_xu_ly text,
    xu_ly_luc timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    idempotency_key text,
    UNIQUE (tenant, idempotency_key),
    CONSTRAINT chk_nhan_xet_muc_do CHECK (muc_do IN ('loi', 'canh_bao', 'gop_y')),
    CONSTRAINT chk_nhan_xet_trang_thai CHECK (trang_thai IN ('mo', 'da_xu_ly'))
);

CREATE INDEX IF NOT EXISTS idx_nhan_xet_phien_ban
    ON app_cap_phep.nhan_xet_tham_dinh (tenant, phien_ban_id, trang_thai, created_at);

ALTER TABLE app_cap_phep.nhan_xet_tham_dinh
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

--------------------------------------------------------------------------------
-- 3. Hàm quyền và audit
--------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_cap_phep_private.la_doc_thiet_ke()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = core, public, pg_temp
AS $$
    SELECT core.has_role('app:cap-phep:tham-dinh')
        OR core.has_role('app:cap-phep:mot-cua')
        OR core.has_role('app:cap-phep:lanh-dao')
        OR core.has_role('app:cap-phep:trat-tu-xd')
        OR core.has_role('dx:auditor')
        OR core.has_role('dx:platform-admin');
$$;

CREATE OR REPLACE FUNCTION app_cap_phep_private.la_tham_dinh_thiet_ke()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = core, public, pg_temp
AS $$
    SELECT core.has_role('app:cap-phep:tham-dinh') OR core.has_role('dx:platform-admin');
$$;

CREATE OR REPLACE FUNCTION app_cap_phep_private.la_chu_ho_so(p_ho_so_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM app_cap_phep.ho_so
        WHERE id = p_ho_so_id
          AND tenant = core.jwt_tenant()
          AND chu_dau_tu_sub = core.jwt_sub()
    );
$$;

CREATE OR REPLACE FUNCTION app_cap_phep_private.nguoi_hien_thi(p_sub text)
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = core, public, pg_temp
AS $$
    SELECT COALESCE(
        (SELECT full_name FROM core.users_directory
         WHERE tenant = core.jwt_tenant()
           AND (id::text = p_sub OR username = p_sub)
         LIMIT 1),
        p_sub
    );
$$;

CREATE OR REPLACE FUNCTION app_cap_phep_private.trg_audit_thiet_ke()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, public, pg_temp
AS $$
DECLARE
    v_row jsonb;
    v_tenant text;
    v_id text;
    v_actor text;
BEGIN
    IF TG_OP = 'DELETE' THEN v_row := to_jsonb(OLD); ELSE v_row := to_jsonb(NEW); END IF;
    v_tenant := COALESCE(v_row->>'tenant', core.jwt_tenant());
    v_id := v_row->>'id';
    v_actor := COALESCE(NULLIF(core.jwt_sub(), ''), 'service');
    PERFORM core.record_audit(
        v_tenant, v_actor,
        CASE WHEN v_actor = 'service' THEN 'service' ELSE 'user' END,
        TG_TABLE_NAME || '.' || lower(TG_OP), TG_TABLE_NAME, v_id,
        jsonb_build_object('schema', TG_TABLE_SCHEMA, 'operation', TG_OP, 'row', v_row)
    );
    RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION app_cap_phep_private.cham_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DO $$
DECLARE v_table text;
BEGIN
    FOREACH v_table IN ARRAY ARRAY['phien_ban_thiet_ke', 'ban_ve', 'nhan_xet_tham_dinh'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_audit_%I ON app_cap_phep.%I', v_table, v_table);
        EXECUTE format(
            'CREATE TRIGGER trg_audit_%I AFTER INSERT OR UPDATE OR DELETE ON app_cap_phep.%I '
            'FOR EACH ROW EXECUTE FUNCTION app_cap_phep_private.trg_audit_thiet_ke()',
            v_table, v_table
        );
        EXECUTE format('DROP TRIGGER IF EXISTS trg_cham_%I ON app_cap_phep.%I', v_table, v_table);
        EXECUTE format(
            'CREATE TRIGGER trg_cham_%I BEFORE UPDATE ON app_cap_phep.%I '
            'FOR EACH ROW EXECUTE FUNCTION app_cap_phep_private.cham_updated_at()',
            v_table, v_table
        );
    END LOOP;
END $$;

GRANT EXECUTE ON FUNCTION app_cap_phep_private.cham_updated_at() TO web_user, svc, dxos_svc, dxos_owner;

--------------------------------------------------------------------------------
-- 4. RLS: đọc theo địa bàn + chủ hồ sơ/cán bộ; ghi chỉ qua RPC
--------------------------------------------------------------------------------
ALTER TABLE app_cap_phep.bo_mon_thiet_ke ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.bo_mon_thiet_ke FORCE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.phien_ban_thiet_ke ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.phien_ban_thiet_ke FORCE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.ban_ve ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.ban_ve FORCE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.nhan_xet_tham_dinh ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.nhan_xet_tham_dinh FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_bo_mon_read ON app_cap_phep.bo_mon_thiet_ke;
CREATE POLICY rls_bo_mon_read ON app_cap_phep.bo_mon_thiet_ke FOR SELECT TO web_user USING (true);
DROP POLICY IF EXISTS rls_bo_mon_svc ON app_cap_phep.bo_mon_thiet_ke;
CREATE POLICY rls_bo_mon_svc ON app_cap_phep.bo_mon_thiet_ke FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_phien_ban_read ON app_cap_phep.phien_ban_thiet_ke;
CREATE POLICY rls_phien_ban_read ON app_cap_phep.phien_ban_thiet_ke
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND (app_cap_phep_private.la_doc_thiet_ke() OR app_cap_phep_private.la_chu_ho_so(ho_so_id)));
DROP POLICY IF EXISTS rls_phien_ban_svc ON app_cap_phep.phien_ban_thiet_ke;
CREATE POLICY rls_phien_ban_svc ON app_cap_phep.phien_ban_thiet_ke FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_ban_ve_read ON app_cap_phep.ban_ve;
CREATE POLICY rls_ban_ve_read ON app_cap_phep.ban_ve
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() AND (app_cap_phep_private.la_doc_thiet_ke() OR app_cap_phep_private.la_chu_ho_so(ho_so_id)));
DROP POLICY IF EXISTS rls_ban_ve_svc ON app_cap_phep.ban_ve;
CREATE POLICY rls_ban_ve_svc ON app_cap_phep.ban_ve FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS rls_nhan_xet_read ON app_cap_phep.nhan_xet_tham_dinh;
CREATE POLICY rls_nhan_xet_read ON app_cap_phep.nhan_xet_tham_dinh
    FOR SELECT TO web_user
    USING (
        tenant = core.jwt_tenant()
        AND (
            app_cap_phep_private.la_doc_thiet_ke()
            OR EXISTS (
                SELECT 1 FROM app_cap_phep.phien_ban_thiet_ke pb
                WHERE pb.id = phien_ban_id AND app_cap_phep_private.la_chu_ho_so(pb.ho_so_id)
            )
        )
    );
DROP POLICY IF EXISTS rls_nhan_xet_svc ON app_cap_phep.nhan_xet_tham_dinh;
CREATE POLICY rls_nhan_xet_svc ON app_cap_phep.nhan_xet_tham_dinh FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

GRANT SELECT ON app_cap_phep.bo_mon_thiet_ke, app_cap_phep.phien_ban_thiet_ke, app_cap_phep.ban_ve, app_cap_phep.nhan_xet_tham_dinh TO web_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON app_cap_phep.bo_mon_thiet_ke, app_cap_phep.phien_ban_thiet_ke, app_cap_phep.ban_ve, app_cap_phep.nhan_xet_tham_dinh TO svc, dxos_svc, dxos_owner;

GRANT EXECUTE ON FUNCTION app_cap_phep_private.la_doc_thiet_ke() TO web_user, svc, dxos_svc;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.la_tham_dinh_thiet_ke() TO web_user, svc, dxos_svc;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.la_chu_ho_so(uuid) TO web_user, svc, dxos_svc;

--------------------------------------------------------------------------------
-- 5. Hàm tính kết luận
--------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_cap_phep_private.tinh_ket_luan_thiet_ke(p_phien_ban_id uuid)
RETURNS text
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = app_cap_phep, pg_catalog
AS $$
DECLARE
    v_missing integer;
    v_ban_ve integer;
    v_fail integer;
    v_open integer;
BEGIN
    SELECT count(*) INTO v_ban_ve FROM app_cap_phep.ban_ve WHERE phien_ban_id = p_phien_ban_id;
    IF v_ban_ve = 0 THEN
        RETURN 'chua_nop';
    END IF;

    SELECT count(*) INTO v_missing
    FROM app_cap_phep.bo_mon_thiet_ke bm
    WHERE bm.bat_buoc
      AND NOT EXISTS (
          SELECT 1 FROM app_cap_phep.ban_ve bv
          WHERE bv.phien_ban_id = p_phien_ban_id AND bv.bo_mon = bm.ma
      );

    SELECT count(*) INTO v_fail
    FROM app_cap_phep.ban_ve
    WHERE phien_ban_id = p_phien_ban_id AND trang_thai = 'khong_dat';

    SELECT count(*) INTO v_open
    FROM app_cap_phep.nhan_xet_tham_dinh
    WHERE phien_ban_id = p_phien_ban_id AND trang_thai = 'mo';

    IF v_missing > 0 OR v_fail > 0 THEN
        RETURN 'khong_dat';
    END IF;
    IF v_open > 0 THEN
        RETURN 'dang_tham_dinh';
    END IF;
    IF EXISTS (
        SELECT 1 FROM app_cap_phep.ban_ve
        WHERE phien_ban_id = p_phien_ban_id AND trang_thai = 'cho_tham_dinh'
    ) THEN
        RETURN 'dang_tham_dinh';
    END IF;
    RETURN 'dat';
END;
$$;

CREATE OR REPLACE FUNCTION app_cap_phep_private.cap_nhat_trang_thai_phien_ban(p_phien_ban_id uuid)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, pg_catalog
AS $$
DECLARE
    v_ket_luan text;
BEGIN
    v_ket_luan := app_cap_phep_private.tinh_ket_luan_thiet_ke(p_phien_ban_id);
    IF v_ket_luan IN ('dat', 'khong_dat', 'dang_tham_dinh') THEN
        UPDATE app_cap_phep.phien_ban_thiet_ke
        SET trang_thai = v_ket_luan, updated_at = now()
        WHERE id = p_phien_ban_id;
    END IF;
    RETURN v_ket_luan;
END;
$$;

--------------------------------------------------------------------------------
-- 6. RPC theo contract
--------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION app_cap_phep.tao_phien_ban(
    p_ho_so_id uuid,
    p_mo_ta text,
    p_idempotency_key text DEFAULT NULL
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
    v_pb app_cap_phep.phien_ban_thiet_ke%ROWTYPE;
    v_so integer;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;
    IF coalesce(btrim(p_mo_ta), '') = '' THEN
        RAISE EXCEPTION 'Mô tả thay đổi không được để trống' USING ERRCODE = '22023';
    END IF;
    IF length(p_mo_ta) > 2000 THEN
        RAISE EXCEPTION 'Mô tả thay đổi quá 2000 ký tự' USING ERRCODE = '22023';
    END IF;

    SELECT * INTO v_hs FROM app_cap_phep.ho_so
    WHERE id = p_ho_so_id AND tenant = cur_tenant;
    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ trong địa bàn' USING ERRCODE = 'PT404';
    END IF;
    IF v_hs.chu_dau_tu_sub <> cur_sub AND NOT core.has_role('dx:platform-admin') THEN
        RAISE EXCEPTION 'Chỉ chủ hồ sơ được tạo phiên bản thiết kế' USING ERRCODE = '42501';
    END IF;
    IF v_hs.trang_thai IN ('TU_CHOI') THEN
        RAISE EXCEPTION 'Hồ sơ đã bị từ chối, không thể tạo phiên bản' USING ERRCODE = 'PT409';
    END IF;

    IF p_idempotency_key IS NOT NULL THEN
        SELECT * INTO v_pb FROM app_cap_phep.phien_ban_thiet_ke
        WHERE tenant = cur_tenant AND idempotency_key = p_idempotency_key;
        IF v_pb.id IS NOT NULL THEN
            RETURN to_jsonb(v_pb);
        END IF;
    END IF;

    PERFORM pg_advisory_xact_lock(hashtext('design_review:' || p_ho_so_id::text));
    SELECT COALESCE(max(so_phien_ban), 0) + 1 INTO v_so
    FROM app_cap_phep.phien_ban_thiet_ke
    WHERE tenant = cur_tenant AND ho_so_id = p_ho_so_id;

    INSERT INTO app_cap_phep.phien_ban_thiet_ke
        (tenant, ho_so_id, so_phien_ban, mo_ta_thay_doi, trang_thai, created_by, idempotency_key)
    VALUES
        (cur_tenant, p_ho_so_id, v_so, btrim(p_mo_ta), 'dang_soan', cur_sub, p_idempotency_key)
    RETURNING * INTO v_pb;

    INSERT INTO core.outbox (tenant, topic, payload)
    VALUES (cur_tenant, 'design_review.version_created',
            jsonb_build_object('ho_so_id', p_ho_so_id, 'phien_ban_id', v_pb.id, 'so_phien_ban', v_so));

    RETURN to_jsonb(v_pb);
END;
$$;

CREATE OR REPLACE FUNCTION app_cap_phep.them_ban_ve(
    p_phien_ban_id uuid,
    p_bo_mon text,
    p_ten text,
    p_file_id uuid,
    p_idempotency_key text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_pb app_cap_phep.phien_ban_thiet_ke%ROWTYPE;
    v_file core.files%ROWTYPE;
    v_bv app_cap_phep.ban_ve%ROWTYPE;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;
    IF p_bo_mon NOT IN (SELECT ma FROM app_cap_phep.bo_mon_thiet_ke) THEN
        RAISE EXCEPTION 'Bộ môn không hợp lệ' USING ERRCODE = '22023';
    END IF;

    SELECT * INTO v_pb FROM app_cap_phep.phien_ban_thiet_ke
    WHERE id = p_phien_ban_id AND tenant = cur_tenant;
    IF v_pb.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy phiên bản thiết kế' USING ERRCODE = 'PT404';
    END IF;
    IF coalesce(btrim(p_ten), '') = '' THEN
        RAISE EXCEPTION 'Tên bản vẽ không được để trống' USING ERRCODE = '22023';
    END IF;
    IF NOT app_cap_phep_private.la_chu_ho_so(v_pb.ho_so_id)
       AND NOT core.has_role('dx:platform-admin') THEN
        RAISE EXCEPTION 'Chỉ chủ hồ sơ được thêm bản vẽ' USING ERRCODE = '42501';
    END IF;
    IF v_pb.trang_thai <> 'dang_soan' THEN
        RAISE EXCEPTION 'Phiên bản đã nộp, không thể thêm bản vẽ' USING ERRCODE = 'PT409';
    END IF;
    IF length(btrim(p_ten)) > 300 THEN
        RAISE EXCEPTION 'Tên bản vẽ quá 300 ký tự' USING ERRCODE = '22023';
    END IF;

    IF p_idempotency_key IS NOT NULL THEN
        SELECT * INTO v_bv FROM app_cap_phep.ban_ve
        WHERE tenant = cur_tenant AND idempotency_key = p_idempotency_key;
        IF v_bv.id IS NOT NULL THEN
            RETURN to_jsonb(v_bv);
        END IF;
    END IF;

    SELECT * INTO v_file FROM core.files
    WHERE id = p_file_id AND tenant = cur_tenant;
    IF v_file.id IS NULL THEN
        RAISE EXCEPTION 'Tệp không tồn tại hoặc không thuộc địa bàn' USING ERRCODE = 'PT404';
    END IF;
    IF v_file.status <> 'clean' THEN
        RAISE EXCEPTION 'Tệp chưa vượt qua kiểm dịch' USING ERRCODE = '22023';
    END IF;
    IF NOT (
        (v_file.object_type = 'ho_so' AND v_file.object_id = v_pb.ho_so_id::text)
        OR (v_file.object_type = 'draft.ho_so' AND v_file.object_id = v_pb.ho_so_id::text)
    ) THEN
        RAISE EXCEPTION 'Tệp không thuộc đúng hồ sơ' USING ERRCODE = '22023';
    END IF;

    INSERT INTO app_cap_phep.ban_ve
        (tenant, phien_ban_id, ho_so_id, bo_mon, ten, file_id, sha256, kich_thuoc,
         trang_thai, created_by, idempotency_key)
    VALUES
        (cur_tenant, p_phien_ban_id, v_pb.ho_so_id, p_bo_mon, btrim(p_ten), p_file_id,
         v_file.sha256, v_file.size, 'cho_tham_dinh', cur_sub, p_idempotency_key)
    RETURNING * INTO v_bv;

    INSERT INTO core.outbox (tenant, topic, payload)
    VALUES (cur_tenant, 'design_review.drawing_added',
            jsonb_build_object('ho_so_id', v_pb.ho_so_id, 'phien_ban_id', p_phien_ban_id,
                               'ban_ve_id', v_bv.id, 'bo_mon', p_bo_mon));

    RETURN to_jsonb(v_bv);
END;
$$;

CREATE OR REPLACE FUNCTION app_cap_phep.ds_ban_ve(
    p_ho_so_id uuid,
    p_phien_ban_id uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_pb app_cap_phep.phien_ban_thiet_ke%ROWTYPE;
    v_nhom jsonb;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM app_cap_phep.ho_so
        WHERE id = p_ho_so_id AND tenant = cur_tenant
    ) THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ trong địa bàn' USING ERRCODE = 'PT404';
    END IF;
    IF NOT app_cap_phep_private.la_doc_thiet_ke() AND NOT app_cap_phep_private.la_chu_ho_so(p_ho_so_id) THEN
        RAISE EXCEPTION 'Bạn không có quyền xem thiết kế của hồ sơ này' USING ERRCODE = '42501';
    END IF;

    IF p_phien_ban_id IS NULL THEN
        SELECT * INTO v_pb FROM app_cap_phep.phien_ban_thiet_ke
        WHERE tenant = cur_tenant AND ho_so_id = p_ho_so_id
        ORDER BY so_phien_ban DESC LIMIT 1;
    ELSE
        SELECT * INTO v_pb FROM app_cap_phep.phien_ban_thiet_ke
        WHERE tenant = cur_tenant AND ho_so_id = p_ho_so_id AND id = p_phien_ban_id;
    END IF;

    SELECT jsonb_agg(
        jsonb_build_object(
            'bo_mon', bm.ma,
            'ten', bm.ten,
            'bat_buoc', bm.bat_buoc,
            'ban_ve', COALESCE((
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'id', bv.id,
                        'phien_ban_id', bv.phien_ban_id,
                        'bo_mon', bv.bo_mon,
                        'ten', bv.ten,
                        'file_id', bv.file_id,
                        'sha256', bv.sha256,
                        'kich_thuoc', bv.kich_thuoc,
                        'trang_thai', bv.trang_thai,
                        'nguoi_tham_dinh', bv.nguoi_tham_dinh,
                        'ngay_tham_dinh', bv.ngay_tham_dinh,
                        'so_nhan_xet_mo', (
                            SELECT count(*) FROM app_cap_phep.nhan_xet_tham_dinh nx
                            WHERE nx.ban_ve_id = bv.id AND nx.trang_thai = 'mo'
                        ),
                        'created_at', bv.created_at
                    ) ORDER BY bv.created_at
                )
                FROM app_cap_phep.ban_ve bv
                WHERE bv.phien_ban_id = v_pb.id AND bv.bo_mon = bm.ma
            ), '[]'::jsonb)
        ) ORDER BY bm.thu_tu
    ) INTO v_nhom
    FROM app_cap_phep.bo_mon_thiet_ke bm;

    RETURN jsonb_build_object(
        'phien_ban', CASE WHEN v_pb.id IS NULL THEN NULL ELSE to_jsonb(v_pb) END,
        'nhom', COALESCE(v_nhom, '[]'::jsonb)
    );
END;
$$;

CREATE OR REPLACE FUNCTION app_cap_phep.ds_phien_ban(p_ho_so_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM app_cap_phep.ho_so
        WHERE id = p_ho_so_id AND tenant = cur_tenant
    ) THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ trong địa bàn' USING ERRCODE = 'PT404';
    END IF;
    IF NOT app_cap_phep_private.la_doc_thiet_ke() AND NOT app_cap_phep_private.la_chu_ho_so(p_ho_so_id) THEN
        RAISE EXCEPTION 'Bạn không có quyền xem thiết kế của hồ sơ này' USING ERRCODE = '42501';
    END IF;

    RETURN COALESCE((
        SELECT jsonb_agg(
            jsonb_build_object(
                'id', pb.id,
                'ho_so_id', pb.ho_so_id,
                'so_phien_ban', pb.so_phien_ban,
                'mo_ta_thay_doi', pb.mo_ta_thay_doi,
                'trang_thai', pb.trang_thai,
                'created_by', pb.created_by,
                'created_at', pb.created_at,
                'ban_ve', COALESCE((
                    SELECT jsonb_agg(to_jsonb(bv) ORDER BY bv.created_at)
                    FROM app_cap_phep.ban_ve bv WHERE bv.phien_ban_id = pb.id
                ), '[]'::jsonb)
            ) ORDER BY pb.so_phien_ban DESC
        )
        FROM app_cap_phep.phien_ban_thiet_ke pb
        WHERE pb.tenant = cur_tenant AND pb.ho_so_id = p_ho_so_id
    ), '[]'::jsonb);
END;
$$;

CREATE OR REPLACE FUNCTION app_cap_phep.danh_gia_ban_ve(
    p_ban_ve_id uuid,
    p_ket_qua text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_bv app_cap_phep.ban_ve%ROWTYPE;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;
    IF NOT app_cap_phep_private.la_tham_dinh_thiet_ke() THEN
        RAISE EXCEPTION 'Chỉ thẩm định viên được đánh giá bản vẽ' USING ERRCODE = '42501';
    END IF;
    IF p_ket_qua NOT IN ('dat', 'khong_dat') THEN
        RAISE EXCEPTION 'Kết quả không hợp lệ' USING ERRCODE = '22023';
    END IF;

    SELECT * INTO v_bv FROM app_cap_phep.ban_ve
    WHERE id = p_ban_ve_id AND tenant = cur_tenant;
    IF v_bv.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy bản vẽ' USING ERRCODE = 'PT404';
    END IF;

    UPDATE app_cap_phep.ban_ve
    SET trang_thai = p_ket_qua,
        nguoi_tham_dinh = app_cap_phep_private.nguoi_hien_thi(cur_sub),
        ngay_tham_dinh = now()
    WHERE id = p_ban_ve_id
    RETURNING * INTO v_bv;

    PERFORM app_cap_phep_private.cap_nhat_trang_thai_phien_ban(v_bv.phien_ban_id);

    INSERT INTO core.outbox (tenant, topic, payload)
    VALUES (cur_tenant, 'design_review.drawing_reviewed',
            jsonb_build_object('ho_so_id', v_bv.ho_so_id, 'phien_ban_id', v_bv.phien_ban_id,
                               'ban_ve_id', v_bv.id, 'ket_qua', p_ket_qua));

    RETURN to_jsonb(v_bv);
END;
$$;

CREATE OR REPLACE FUNCTION app_cap_phep.them_nhan_xet(
    p_ban_ve_id uuid,
    p_noi_dung text,
    p_muc_do text,
    p_idempotency_key text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_bv app_cap_phep.ban_ve%ROWTYPE;
    v_nx app_cap_phep.nhan_xet_tham_dinh%ROWTYPE;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;
    IF NOT app_cap_phep_private.la_tham_dinh_thiet_ke() THEN
        RAISE EXCEPTION 'Chỉ thẩm định viên được nhận xét' USING ERRCODE = '42501';
    END IF;
    IF p_muc_do NOT IN ('loi', 'canh_bao', 'gop_y') THEN
        RAISE EXCEPTION 'Mức độ nhận xét không hợp lệ' USING ERRCODE = '22023';
    END IF;
    IF coalesce(btrim(p_noi_dung), '') = '' THEN
        RAISE EXCEPTION 'Nội dung nhận xét không được để trống' USING ERRCODE = '22023';
    END IF;
    IF length(p_noi_dung) > 4000 THEN
        RAISE EXCEPTION 'Nội dung nhận xét quá 4000 ký tự' USING ERRCODE = '22023';
    END IF;

    IF p_idempotency_key IS NOT NULL THEN
        SELECT * INTO v_nx FROM app_cap_phep.nhan_xet_tham_dinh
        WHERE tenant = cur_tenant AND idempotency_key = p_idempotency_key;
        IF v_nx.id IS NOT NULL THEN
            RETURN to_jsonb(v_nx);
        END IF;
    END IF;

    SELECT * INTO v_bv FROM app_cap_phep.ban_ve
    WHERE id = p_ban_ve_id AND tenant = cur_tenant;
    IF v_bv.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy bản vẽ' USING ERRCODE = 'PT404';
    END IF;

    INSERT INTO app_cap_phep.nhan_xet_tham_dinh
        (tenant, ban_ve_id, phien_ban_id, bo_mon, nguoi_sub, nguoi, noi_dung, muc_do,
         trang_thai, idempotency_key)
    VALUES
        (cur_tenant, p_ban_ve_id, v_bv.phien_ban_id, v_bv.bo_mon, cur_sub,
         app_cap_phep_private.nguoi_hien_thi(cur_sub), btrim(p_noi_dung), p_muc_do,
         'mo', p_idempotency_key)
    RETURNING * INTO v_nx;

    PERFORM app_cap_phep_private.cap_nhat_trang_thai_phien_ban(v_bv.phien_ban_id);

    INSERT INTO core.outbox (tenant, topic, payload)
    VALUES (cur_tenant, 'design_review.comment_added',
            jsonb_build_object('ho_so_id', v_bv.ho_so_id, 'phien_ban_id', v_bv.phien_ban_id,
                               'ban_ve_id', p_ban_ve_id, 'nhan_xet_id', v_nx.id, 'muc_do', p_muc_do));

    RETURN to_jsonb(v_nx);
END;
$$;

CREATE OR REPLACE FUNCTION app_cap_phep.xu_ly_nhan_xet(
    p_nhan_xet_id uuid,
    p_ghi_chu text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_nx app_cap_phep.nhan_xet_tham_dinh%ROWTYPE;
    v_ho_so_id uuid;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    IF length(coalesce(p_ghi_chu, '')) > 2000 THEN
        RAISE EXCEPTION 'Ghi chú xử lý quá 2000 ký tự' USING ERRCODE = '22023';
    END IF;

    SELECT * INTO v_nx FROM app_cap_phep.nhan_xet_tham_dinh
    WHERE id = p_nhan_xet_id AND tenant = cur_tenant;
    IF v_nx.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy nhận xét' USING ERRCODE = 'PT404';
    END IF;
    IF v_nx.trang_thai = 'da_xu_ly' THEN
        RAISE EXCEPTION 'Nhận xét đã được xử lý' USING ERRCODE = 'PT409';
    END IF;

    SELECT ho_so_id INTO v_ho_so_id FROM app_cap_phep.phien_ban_thiet_ke WHERE id = v_nx.phien_ban_id;
    IF NOT app_cap_phep_private.la_tham_dinh_thiet_ke() AND NOT app_cap_phep_private.la_chu_ho_so(v_ho_so_id) THEN
        RAISE EXCEPTION 'Bạn không có quyền xử lý nhận xét này' USING ERRCODE = '42501';
    END IF;

    UPDATE app_cap_phep.nhan_xet_tham_dinh
    SET trang_thai = 'da_xu_ly',
        ghi_chu_xu_ly = p_ghi_chu,
        xu_ly_luc = now()
    WHERE id = p_nhan_xet_id
    RETURNING * INTO v_nx;

    PERFORM app_cap_phep_private.cap_nhat_trang_thai_phien_ban(v_nx.phien_ban_id);

    INSERT INTO core.outbox (tenant, topic, payload)
    VALUES (cur_tenant, 'design_review.comment_resolved',
            jsonb_build_object('ho_so_id', v_ho_so_id, 'phien_ban_id', v_nx.phien_ban_id,
                               'nhan_xet_id', v_nx.id));

    RETURN to_jsonb(v_nx);
END;
$$;

CREATE OR REPLACE FUNCTION app_cap_phep.ds_nhan_xet(
    p_phien_ban_id uuid,
    p_bo_mon text DEFAULT NULL,
    p_muc_do text DEFAULT NULL,
    p_trang_thai text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_ho_so_id uuid;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;
    SELECT ho_so_id INTO v_ho_so_id FROM app_cap_phep.phien_ban_thiet_ke
    WHERE id = p_phien_ban_id AND tenant = cur_tenant;
    IF v_ho_so_id IS NULL AND NOT EXISTS (SELECT 1 FROM app_cap_phep.phien_ban_thiet_ke WHERE id = p_phien_ban_id) THEN
        RAISE EXCEPTION 'Không tìm thấy phiên bản' USING ERRCODE = 'PT404';
    END IF;
    IF NOT app_cap_phep_private.la_doc_thiet_ke() AND NOT app_cap_phep_private.la_chu_ho_so(v_ho_so_id) THEN
        RAISE EXCEPTION 'Bạn không có quyền xem nhận xét' USING ERRCODE = '42501';
    END IF;

    RETURN COALESCE((
        SELECT jsonb_agg(to_jsonb(nx) ORDER BY nx.created_at DESC)
        FROM app_cap_phep.nhan_xet_tham_dinh nx
        WHERE nx.phien_ban_id = p_phien_ban_id
          AND nx.tenant = cur_tenant
          AND (p_bo_mon IS NULL OR nx.bo_mon = p_bo_mon)
          AND (p_muc_do IS NULL OR nx.muc_do = p_muc_do)
          AND (p_trang_thai IS NULL OR nx.trang_thai = p_trang_thai)
    ), '[]'::jsonb);
END;
$$;

CREATE OR REPLACE FUNCTION app_cap_phep.trang_thai_tham_dinh(p_ho_so_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_pb app_cap_phep.phien_ban_thiet_ke%ROWTYPE;
    v_bo_mon jsonb;
    v_thieu jsonb;
    v_nhan_xet_mo integer := 0;
    v_ket_luan text;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM app_cap_phep.ho_so
        WHERE id = p_ho_so_id AND tenant = cur_tenant
    ) THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ trong địa bàn' USING ERRCODE = 'PT404';
    END IF;
    IF NOT app_cap_phep_private.la_doc_thiet_ke() AND NOT app_cap_phep_private.la_chu_ho_so(p_ho_so_id) THEN
        RAISE EXCEPTION 'Bạn không có quyền xem trạng thái thiết kế' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO v_pb FROM app_cap_phep.phien_ban_thiet_ke
    WHERE tenant = cur_tenant AND ho_so_id = p_ho_so_id
    ORDER BY so_phien_ban DESC LIMIT 1;

    IF v_pb.id IS NULL THEN
        v_ket_luan := 'chua_nop';
    ELSE
        v_ket_luan := app_cap_phep_private.tinh_ket_luan_thiet_ke(v_pb.id);
        SELECT count(*) INTO v_nhan_xet_mo
        FROM app_cap_phep.nhan_xet_tham_dinh
        WHERE phien_ban_id = v_pb.id AND trang_thai = 'mo';
    END IF;

    SELECT jsonb_agg(
        jsonb_build_object(
            'bo_mon', bm.ma,
            'ten', bm.ten,
            'bat_buoc', bm.bat_buoc,
            'so_ban_ve', COALESCE(x.so_ban_ve, 0),
            'ket_qua', CASE
                WHEN COALESCE(x.so_ban_ve, 0) = 0 THEN 'chua_co'
                WHEN COALESCE(x.so_khong_dat, 0) > 0 THEN 'khong_dat'
                WHEN COALESCE(x.so_dat, 0) = x.so_ban_ve THEN 'dat'
                ELSE 'cho_tham_dinh'
            END
        ) ORDER BY bm.thu_tu
    ) INTO v_bo_mon
    FROM app_cap_phep.bo_mon_thiet_ke bm
    LEFT JOIN LATERAL (
        SELECT count(*) AS so_ban_ve,
               count(*) FILTER (WHERE bv.trang_thai = 'dat') AS so_dat,
               count(*) FILTER (WHERE bv.trang_thai = 'khong_dat') AS so_khong_dat
        FROM app_cap_phep.ban_ve bv
        WHERE bv.phien_ban_id = v_pb.id AND bv.bo_mon = bm.ma
    ) x ON true;

    SELECT COALESCE(jsonb_agg(bm.ma), '[]'::jsonb) INTO v_thieu
    FROM app_cap_phep.bo_mon_thiet_ke bm
    WHERE bm.bat_buoc
      AND NOT EXISTS (
          SELECT 1 FROM app_cap_phep.ban_ve bv
          WHERE bv.phien_ban_id = v_pb.id AND bv.bo_mon = bm.ma
      );

    RETURN jsonb_build_object(
        'ho_so_id', p_ho_so_id,
        'phien_ban_id', CASE WHEN v_pb.id IS NULL THEN NULL ELSE v_pb.id END,
        'so_phien_ban', COALESCE(v_pb.so_phien_ban, 0),
        'bo_mon', COALESCE(v_bo_mon, '[]'::jsonb),
        'thieu_bo_mon', COALESCE(v_thieu, '[]'::jsonb),
        'nhan_xet_mo', v_nhan_xet_mo,
        'ket_luan', COALESCE(v_ket_luan, 'chua_nop')
    );
END;
$$;

REVOKE ALL ON FUNCTION app_cap_phep.tao_phien_ban(uuid, text, text) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION app_cap_phep.them_ban_ve(uuid, text, text, uuid, text) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION app_cap_phep.ds_ban_ve(uuid, uuid) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION app_cap_phep.ds_phien_ban(uuid) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION app_cap_phep.danh_gia_ban_ve(uuid, text) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION app_cap_phep.them_nhan_xet(uuid, text, text, text) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION app_cap_phep.xu_ly_nhan_xet(uuid, text) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION app_cap_phep.ds_nhan_xet(uuid, text, text, text) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION app_cap_phep.trang_thai_tham_dinh(uuid) FROM PUBLIC, anon;

GRANT EXECUTE ON FUNCTION app_cap_phep.tao_phien_ban(uuid, text, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.them_ban_ve(uuid, text, text, uuid, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.ds_ban_ve(uuid, uuid) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.ds_phien_ban(uuid) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.danh_gia_ban_ve(uuid, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.them_nhan_xet(uuid, text, text, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.xu_ly_nhan_xet(uuid, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.ds_nhan_xet(uuid, text, text, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.trang_thai_tham_dinh(uuid) TO web_user;

NOTIFY pgrst, 'reload schema';

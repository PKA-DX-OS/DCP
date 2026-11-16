-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

CREATE SCHEMA IF NOT EXISTS app_cap_phep AUTHORIZATION dxos_owner;
CREATE SCHEMA IF NOT EXISTS app_cap_phep_private AUTHORIZATION dxos_owner;
REVOKE ALL ON SCHEMA app_cap_phep FROM dxos_svc;
REVOKE ALL ON SCHEMA app_cap_phep_private FROM PUBLIC, web_user, anon;
GRANT USAGE ON SCHEMA app_cap_phep TO anon, web_user, svc, dxos_svc;
GRANT USAGE ON SCHEMA app_cap_phep_private TO svc, dxos_svc, dxos_owner;

--------------------------------------------------------------------------------
-- 1. CÁC BẢNG DỮ LIỆU NGHIỆP VỤ CẤP PHÉP XÂY DỰNG
--------------------------------------------------------------------------------

-- Bảng hồ sơ đề nghị cấp phép
CREATE TABLE IF NOT EXISTS app_cap_phep.ho_so (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ma_ho_so text NOT NULL UNIQUE,
    chu_dau_tu_sub text NOT NULL,
    ho_ten text NOT NULL,
    cccd text NOT NULL,
    dien_thoai text NOT NULL,
    dia_chi_cong_trinh text NOT NULL,
    thua_dat text NOT NULL,
    so_tang integer NOT NULL DEFAULT 1,
    dien_tich_san_m2 double precision NOT NULL DEFAULT 100.0,
    khu_quan_ly_kien_truc boolean NOT NULL DEFAULT true,
    trang_thai text NOT NULL DEFAULT 'DA_NOP',
    buoc text NOT NULL DEFAULT 'tiep_nhan',
    han_buoc_at timestamptz,
    qua_han boolean NOT NULL DEFAULT false,
    han_tong_at timestamptz NOT NULL,
    process_instance_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE app_cap_phep.ho_so ADD COLUMN IF NOT EXISTS qua_han boolean NOT NULL DEFAULT false;
ALTER TABLE app_cap_phep.ho_so ADD COLUMN IF NOT EXISTS ly_do_bo_sung text;

CREATE INDEX IF NOT EXISTS idx_ho_so_tenant_status ON app_cap_phep.ho_so (tenant, trang_thai);
CREATE INDEX IF NOT EXISTS idx_ho_so_cdt ON app_cap_phep.ho_so (tenant, chu_dau_tu_sub);

-- Bảng tệp đính kèm hồ sơ
CREATE TABLE IF NOT EXISTS app_cap_phep.ho_so_tep (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ho_so_id uuid NOT NULL REFERENCES app_cap_phep.ho_so(id) ON DELETE CASCADE,
    file_id uuid NOT NULL,
    loai text NOT NULL, -- don, giay_to_dat, ban_ve_mat_bang, ban_ve_tang, ban_ve_mong, cam_ket_an_toan, pccc, tham_tra
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Bảng lịch sử thay đổi hồ sơ (Snapshot)
CREATE TABLE IF NOT EXISTS app_cap_phep.ho_so_lich_su (
    id bigserial PRIMARY KEY,
    ho_so_id uuid NOT NULL,
    snapshot jsonb NOT NULL,
    changed_at timestamptz NOT NULL DEFAULT now(),
    changed_by text
);

-- Bảng giấy phép xây dựng đã cấp
CREATE TABLE IF NOT EXISTS app_cap_phep.giay_phep (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    ho_so_id uuid NOT NULL REFERENCES app_cap_phep.ho_so(id),
    so_giay_phep text NOT NULL UNIQUE,
    signed_doc_id uuid NOT NULL,
    trang_thai text NOT NULL DEFAULT 'hieu_luc', -- hieu_luc, thu_hoi
    ngay_cap timestamptz NOT NULL DEFAULT now(),
    ly_do_thu_hoi text
);

-- Bảng đếm số giấy phép theo tenant và năm (N-02)
CREATE TABLE IF NOT EXISTS app_cap_phep.so_giay_phep_counter (
    tenant text NOT NULL,
    nam int NOT NULL,
    gia_tri int NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant, nam)
);
ALTER TABLE app_cap_phep.so_giay_phep_counter OWNER TO dxos_owner;
GRANT ALL ON app_cap_phep.so_giay_phep_counter TO dxos_owner, dxos_svc, svc;

-- Khởi tạo giá trị bộ đếm từ dữ liệu giấy phép hiện có (nếu có)
INSERT INTO app_cap_phep.so_giay_phep_counter (tenant, nam, gia_tri)
SELECT tenant,
       to_char(ngay_cap, 'YYYY')::int AS nam,
       COALESCE(MAX(substring(so_giay_phep from '.*-(\d+)$')::int), count(*)::int) AS gia_tri
FROM app_cap_phep.giay_phep
GROUP BY tenant, to_char(ngay_cap, 'YYYY')
ON CONFLICT (tenant, nam) DO UPDATE
SET gia_tri = GREATEST(app_cap_phep.so_giay_phep_counter.gia_tri, EXCLUDED.gia_tri);

CREATE UNIQUE INDEX IF NOT EXISTS uq_giay_phep_ho_so_hieu_luc
ON app_cap_phep.giay_phep(ho_so_id)
WHERE trang_thai = 'hieu_luc';

-- Bảng công trình thi công (đối tượng giám sát IoT)
CREATE TABLE IF NOT EXISTS app_cap_phep.cong_trinh (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    giay_phep_id uuid REFERENCES app_cap_phep.giay_phep(id),
    ma_cong_trinh text NOT NULL UNIQUE,
    entity_id text NOT NULL,
    dia_chi text,
    trang_thai_thi_cong text NOT NULL DEFAULT 'DANG_THI_CONG',
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE app_cap_phep.cong_trinh ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

-- Bảng phiếu kiểm tra hậu kiểm công trường
CREATE TABLE IF NOT EXISTS app_cap_phep.phieu_kiem_tra (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    cong_trinh_id uuid REFERENCES app_cap_phep.cong_trinh(id),
    nguon text NOT NULL DEFAULT 'cam_bien', -- cam_bien, phan_anh, chu_dong
    chi_so text,
    gia_tri double precision,
    nguong double precision,
    trang_thai text NOT NULL DEFAULT 'CHO_KIEM_TRA', -- CHO_KIEM_TRA, DANG_KIEM_TRA, DA_XU_LY
    ket_luan text,
    bien_ban_file_id uuid,
    process_instance_id text,
    nguoi_kiem_tra_sub text,
    ghi_chu text,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE app_cap_phep.phieu_kiem_tra ADD COLUMN IF NOT EXISTS nguoi_kiem_tra_sub text;
ALTER TABLE app_cap_phep.phieu_kiem_tra ADD COLUMN IF NOT EXISTS ghi_chu text;

--------------------------------------------------------------------------------
-- 2. TRIGGER GHI LỊCH SỬ VÀ GHI AUDIT
--------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION app_cap_phep_private.trg_ho_so_audit_history()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Ghi snapshot vào ho_so_lich_su
        INSERT INTO app_cap_phep.ho_so_lich_su (ho_so_id, snapshot, changed_by)
        VALUES (OLD.id, to_jsonb(OLD), core.jwt_sub());
        NEW.updated_at := now();
    END IF;

    -- Ghi audit log vào chuỗi băm lõi
    PERFORM core.record_audit(
        NEW.tenant,
        core.jwt_sub(),
        'user',
        'ho_so.' || lower(TG_OP),
        'ho_so',
        NEW.id::text,
        jsonb_build_object('ma_ho_so', NEW.ma_ho_so, 'trang_thai', NEW.trang_thai, 'buoc', NEW.buoc)
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app_cap_phep, core;

DROP TRIGGER IF EXISTS trg_ho_so_audit ON app_cap_phep.ho_so;
DROP FUNCTION IF EXISTS app_cap_phep.trg_ho_so_audit_history() CASCADE;
CREATE TRIGGER trg_ho_so_audit
    AFTER INSERT OR UPDATE ON app_cap_phep.ho_so
    FOR EACH ROW EXECUTE FUNCTION app_cap_phep_private.trg_ho_so_audit_history();

--------------------------------------------------------------------------------
-- 3. KHUNG NHÌN CHE DẤU DỮ LIỆU CÁ NHÂN (v_ho_so)
--------------------------------------------------------------------------------

DROP VIEW IF EXISTS app_cap_phep.v_ho_so CASCADE;
CREATE OR REPLACE VIEW app_cap_phep.v_ho_so WITH (security_invoker = true) AS
SELECT
    h.id,
    h.tenant,
    h.ma_ho_so,
    h.chu_dau_tu_sub,
    h.ho_ten,
    CASE
        WHEN h.chu_dau_tu_sub = core.jwt_sub()
          OR core.can_access('ho_so', h.id)
          OR core.has_role('dx:platform-admin') THEN h.cccd
        ELSE '********' || right(h.cccd, 4)
    END AS cccd,
    CASE
        WHEN h.chu_dau_tu_sub = core.jwt_sub()
          OR core.can_access('ho_so', h.id)
          OR core.has_role('dx:platform-admin') THEN h.dien_thoai
        ELSE '******' || right(h.dien_thoai, 4)
    END AS dien_thoai,
    h.dia_chi_cong_trinh,
    h.thua_dat,
    h.so_tang,
    h.dien_tich_san_m2,
    h.khu_quan_ly_kien_truc,
    h.trang_thai,
    h.buoc,
    h.han_buoc_at,
    h.qua_han,
    h.han_tong_at,
    h.process_instance_id,
    h.ly_do_bo_sung,
    h.created_at,
    h.updated_at
FROM app_cap_phep.ho_so h;

ALTER VIEW app_cap_phep.v_ho_so OWNER TO dxos_owner;
GRANT SELECT ON app_cap_phep.v_ho_so TO web_user, dxos_owner, dxos_svc, svc;

-- Khung nhìn chi tiết tệp đính kèm hồ sơ (T-01)
DROP VIEW IF EXISTS app_cap_phep.v_ho_so_tep CASCADE;
CREATE OR REPLACE VIEW app_cap_phep.v_ho_so_tep WITH (security_invoker = true) AS
SELECT
    t.id,
    t.ho_so_id,
    t.file_id,
    t.loai,
    t.created_at,
    f.object_key,
    f.sha256,
    f.size,
    f.mime,
    f.status
FROM app_cap_phep.ho_so_tep t
LEFT JOIN core.files f ON t.file_id = f.id;

ALTER VIEW app_cap_phep.v_ho_so_tep OWNER TO dxos_owner;
GRANT SELECT ON app_cap_phep.v_ho_so_tep TO web_user, dxos_owner, dxos_svc, svc;

--------------------------------------------------------------------------------
-- 4. HÀM RPC mo_ho_so: TỪ CHỐI 403 CÓ GHI AUDIT
--------------------------------------------------------------------------------

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
       OR core.can_access('ho_so', p_id) THEN
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

CREATE OR REPLACE FUNCTION app_cap_phep.mo_ho_so(p_ma_ho_so text)
RETURNS jsonb AS $$
DECLARE
    v_id uuid;
BEGIN
    SELECT id INTO v_id FROM app_cap_phep.ho_so WHERE ma_ho_so = p_ma_ho_so;
    IF NOT FOUND THEN
        BEGIN
            v_id := p_ma_ho_so::uuid;
        EXCEPTION WHEN OTHERS THEN
            v_id := NULL;
        END;
    END IF;
    IF v_id IS NULL THEN
        PERFORM set_config('response.status', '404', true);
        RETURN jsonb_build_object('loi', 'Không tìm thấy hồ sơ', 'ma_loi', 'NOT_FOUND');
    END IF;
    RETURN app_cap_phep.mo_ho_so(v_id);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app_cap_phep, core;

GRANT EXECUTE ON FUNCTION app_cap_phep.mo_ho_so(text) TO web_user;

--------------------------------------------------------------------------------
-- 5. TRIGGER BẢO VỆ CỘT VÀ CHẶN NGƯỜI DÙNG WEB TỰ DUYỆT CẤP PHÉP (F-25, F-26)
--------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION app_cap_phep_private.trg_ho_so_protect_columns()
RETURNS trigger AS $$
BEGIN
    -- Dịch vụ hệ thống (backend services hoặc superuser hoặc app owner) được phép cập nhật
    IF current_user <> 'web_user' THEN
        RETURN NEW;
    END IF;

    -- Mọi người dùng qua REST API (kể cả cán bộ lẫn công dân) đều KHÔNG được sửa trực tiếp trạng thái qua REST (V2-07)
    IF NEW.trang_thai IS DISTINCT FROM OLD.trang_thai THEN
        RAISE EXCEPTION 'Không được phép thay đổi trạng thái hồ sơ qua REST API! Mọi chuyển đổi trạng thái phải thực hiện qua quy trình BPMN.'
            USING ERRCODE = '42501';
    END IF;

    IF NEW.buoc IS DISTINCT FROM OLD.buoc OR NEW.han_buoc_at IS DISTINCT FROM OLD.han_buoc_at OR NEW.han_tong_at IS DISTINCT FROM OLD.han_tong_at OR NEW.process_instance_id IS DISTINCT FROM OLD.process_instance_id THEN
        RAISE EXCEPTION 'Không được phép thay đổi bước quy trình hoặc thời hạn qua REST API!'
            USING ERRCODE = '42501';
    END IF;

    IF NEW.tenant <> OLD.tenant OR NEW.chu_dau_tu_sub <> OLD.chu_dau_tu_sub OR NEW.ma_ho_so <> OLD.ma_ho_so THEN
        RAISE EXCEPTION 'Không được phép thay đổi thông tin định danh hồ sơ (tenant, chủ đầu tư, mã hồ sơ)'
            USING ERRCODE = '42501';
    END IF;

    -- Chỉ cho phép cập nhật khi hồ sơ đang ở trạng thái CAN_BO_SUNG
    IF OLD.trang_thai <> 'CAN_BO_SUNG' THEN
        RAISE EXCEPTION 'Hồ sơ chỉ có thể cập nhật khi ở trạng thái CAN_BO_SUNG (trạng thái hiện tại: %)', OLD.trang_thai
            USING ERRCODE = '42501';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = pg_catalog, app_cap_phep, core;

DROP TRIGGER IF EXISTS trg_ho_so_protect ON app_cap_phep.ho_so;
DROP FUNCTION IF EXISTS app_cap_phep.trg_ho_so_protect_columns() CASCADE;
CREATE TRIGGER trg_ho_so_protect
    BEFORE UPDATE ON app_cap_phep.ho_so
    FOR EACH ROW EXECUTE FUNCTION app_cap_phep_private.trg_ho_so_protect_columns();

--------------------------------------------------------------------------------
-- 6. CHÍNH SÁCH ROW-LEVEL SECURITY (RLS) TÁCH BIỆT (F-25, F-26, F-27)
--------------------------------------------------------------------------------

ALTER TABLE app_cap_phep.ho_so ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.ho_so FORCE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.ho_so_tep ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.ho_so_tep FORCE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.giay_phep ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.giay_phep FORCE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.cong_trinh ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.cong_trinh FORCE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.phieu_kiem_tra ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_cap_phep.phieu_kiem_tra FORCE ROW LEVEL SECURITY;

-- 6.1 Chính sách SELECT: chủ đầu tư xem của mình; cán bộ xem trong tenant hoặc khi có quyền
DROP POLICY IF EXISTS rls_ho_so_tenant ON app_cap_phep.ho_so;
DROP POLICY IF EXISTS rls_ho_so_select ON app_cap_phep.ho_so;
CREATE POLICY rls_ho_so_select ON app_cap_phep.ho_so
    FOR SELECT TO web_user
    USING (
        tenant = core.jwt_tenant() AND (
            chu_dau_tu_sub = core.jwt_sub()
            OR core.can_access('ho_so', id)
            OR core.has_role('app:cap-phep:lanh-dao')
            OR core.has_role('app:cap-phep:mot-cua')
            OR core.has_role('dx:platform-admin')
        )
    );

-- 6.2 Chính sách INSERT: công dân chỉ nộp vào chính tenant của mình và trạng thái DA_NOP
DROP POLICY IF EXISTS rls_ho_so_insert ON app_cap_phep.ho_so;
CREATE POLICY rls_ho_so_insert ON app_cap_phep.ho_so
    FOR INSERT TO web_user
    WITH CHECK (
        tenant = core.jwt_tenant()
        AND chu_dau_tu_sub = core.jwt_sub()
        AND trang_thai = 'DA_NOP'
    );

-- 6.3 Chính sách UPDATE: công dân chỉ sửa khi CAN_BO_SUNG (Z-02)
DROP POLICY IF EXISTS rls_ho_so_update ON app_cap_phep.ho_so;
CREATE POLICY rls_ho_so_update ON app_cap_phep.ho_so
    FOR UPDATE TO web_user
    USING (
        tenant = core.jwt_tenant()
        AND chu_dau_tu_sub = core.jwt_sub()
        AND trang_thai = 'CAN_BO_SUNG'
    )
    WITH CHECK (
        tenant = core.jwt_tenant()
        AND chu_dau_tu_sub = core.jwt_sub()
        AND trang_thai = 'CAN_BO_SUNG'
    );

-- 6.4 Chính sách ho_so_tep: chỉ xem tệp nếu có quyền xem hồ sơ tương ứng
DROP POLICY IF EXISTS rls_ho_so_tep_tenant ON app_cap_phep.ho_so_tep;
CREATE POLICY rls_ho_so_tep_tenant ON app_cap_phep.ho_so_tep
    FOR ALL TO web_user
    USING (
        EXISTS (
            SELECT 1 FROM app_cap_phep.ho_so h
            WHERE h.id = ho_so_tep.ho_so_id
              AND h.tenant = core.jwt_tenant()
              AND (
                  h.chu_dau_tu_sub = core.jwt_sub()
                  OR core.can_access('ho_so', h.id)
                  OR core.has_role('app:cap-phep:lanh-dao')
                  OR core.has_role('app:cap-phep:mot-cua')
                  OR core.has_role('dx:platform-admin')
              )
        )
    );

-- 6.5 Giấy phép, công trình, phiếu kiểm tra: siết chặt RLS bảo vệ quyền riêng tư (Q-02)
DROP POLICY IF EXISTS rls_giay_phep_tenant ON app_cap_phep.giay_phep;
DROP POLICY IF EXISTS rls_giay_phep_select ON app_cap_phep.giay_phep;
CREATE POLICY rls_giay_phep_select ON app_cap_phep.giay_phep
    FOR SELECT TO web_user
    USING (
        core.has_role('dx:platform-admin')
        OR (
            tenant = core.jwt_tenant()
            AND (
                core.has_role('app:cap-phep:mot-cua')
                OR core.has_role('app:cap-phep:lanh-dao')
                OR core.has_role('app:cap-phep:tham-dinh')
                OR core.has_role('app:cap-phep:trat-tu-xd')
                OR core.has_role('dx:tenant-admin')
                OR core.has_role('dx:auditor')
                OR EXISTS (
                    SELECT 1 FROM app_cap_phep.ho_so hs
                    WHERE hs.id = giay_phep.ho_so_id
                      AND hs.chu_dau_tu_sub = core.jwt_sub()
                      AND hs.tenant = core.jwt_tenant()
                )
            )
        )
    );

DROP POLICY IF EXISTS rls_cong_trinh_tenant ON app_cap_phep.cong_trinh;
DROP POLICY IF EXISTS rls_cong_trinh_select ON app_cap_phep.cong_trinh;
CREATE POLICY rls_cong_trinh_select ON app_cap_phep.cong_trinh
    FOR SELECT TO web_user
    USING (
        core.has_role('dx:platform-admin')
        OR (
            tenant = core.jwt_tenant()
            AND (
                core.has_role('app:cap-phep:mot-cua')
                OR core.has_role('app:cap-phep:lanh-dao')
                OR core.has_role('app:cap-phep:tham-dinh')
                OR core.has_role('app:cap-phep:trat-tu-xd')
                OR core.has_role('dx:tenant-admin')
                OR core.has_role('dx:auditor')
                OR EXISTS (
                    SELECT 1 FROM app_cap_phep.giay_phep gp
                    JOIN app_cap_phep.ho_so hs ON hs.id = gp.ho_so_id
                    WHERE gp.id = cong_trinh.giay_phep_id
                      AND hs.chu_dau_tu_sub = core.jwt_sub()
                      AND hs.tenant = core.jwt_tenant()
                )
            )
        )
    );

DROP POLICY IF EXISTS rls_phieu_kiem_tra_tenant ON app_cap_phep.phieu_kiem_tra;
DROP POLICY IF EXISTS rls_phieu_kiem_tra_select ON app_cap_phep.phieu_kiem_tra;
CREATE POLICY rls_phieu_kiem_tra_select ON app_cap_phep.phieu_kiem_tra
    FOR SELECT TO web_user
    USING (
        core.has_role('dx:platform-admin')
        OR (
            tenant = core.jwt_tenant()
            AND (
                core.has_role('app:cap-phep:trat-tu-xd')
                OR core.has_role('app:cap-phep:lanh-dao')
                OR core.has_role('dx:tenant-admin')
                OR core.has_role('dx:auditor')
                OR EXISTS (
                    SELECT 1 FROM app_cap_phep.cong_trinh ct
                    JOIN app_cap_phep.giay_phep gp ON gp.id = ct.giay_phep_id
                    JOIN app_cap_phep.ho_so hs ON hs.id = gp.ho_so_id
                    WHERE ct.id = phieu_kiem_tra.cong_trinh_id
                      AND hs.chu_dau_tu_sub = core.jwt_sub()
                      AND hs.tenant = core.jwt_tenant()
                )
            )
        )
    );

-- Khung nhìn công khai giấy phép xây dựng phục vụ tra cứu cộng đồng (Q-02)
DROP VIEW IF EXISTS app_cap_phep.cong_khai_giay_phep CASCADE;
CREATE OR REPLACE VIEW app_cap_phep.cong_khai_giay_phep AS
SELECT
    gp.so_giay_phep,
    ct.ma_cong_trinh,
    ct.dia_chi,
    gp.trang_thai,
    gp.ngay_cap
FROM app_cap_phep.giay_phep gp
LEFT JOIN app_cap_phep.cong_trinh ct ON ct.giay_phep_id = gp.id;

ALTER VIEW app_cap_phep.cong_khai_giay_phep OWNER TO dxos_owner;
GRANT SELECT ON app_cap_phep.cong_khai_giay_phep TO web_user, anon;

-- Khung nhìn công trình thi công phục vụ giao diện và giám sát (T-03)
DROP VIEW IF EXISTS app_cap_phep.v_cong_trinh CASCADE;
CREATE OR REPLACE VIEW app_cap_phep.v_cong_trinh
WITH (security_invoker = true) AS
SELECT
    ct.id,
    ct.tenant,
    ct.ma_cong_trinh,
    ct.entity_id,
    ct.dia_chi,
    ct.trang_thai_thi_cong,
    ct.created_at,
    hs.ma_ho_so,
    hs.id AS ho_so_id,
    (
        SELECT jsonb_build_object(
            'chi_so', p.chi_so,
            'gia_tri', p.gia_tri,
            'nguong', p.nguong,
            'created_at', p.created_at
        )
        FROM app_cap_phep.phieu_kiem_tra p
        WHERE p.cong_trinh_id = ct.id
        ORDER BY p.created_at DESC
        LIMIT 1
    ) AS canh_bao_gan_nhat
FROM app_cap_phep.cong_trinh ct
LEFT JOIN app_cap_phep.giay_phep gp ON gp.id = ct.giay_phep_id
LEFT JOIN app_cap_phep.ho_so hs ON hs.id = gp.ho_so_id;

ALTER VIEW app_cap_phep.v_cong_trinh OWNER TO dxos_owner;
GRANT SELECT ON app_cap_phep.v_cong_trinh TO web_user;

-- Khung nhìn phiếu kiểm tra hậu kiểm phục vụ giao diện (T-03)
DROP VIEW IF EXISTS app_cap_phep.v_phieu_kiem_tra CASCADE;
CREATE OR REPLACE VIEW app_cap_phep.v_phieu_kiem_tra
WITH (security_invoker = true) AS
SELECT
    p.id,
    p.tenant,
    p.cong_trinh_id,
    ct.ma_cong_trinh,
    ct.dia_chi,
    p.nguon,
    p.chi_so,
    p.gia_tri,
    p.nguong,
    p.trang_thai,
    p.ket_luan,
    p.bien_ban_file_id,
    p.process_instance_id,
    p.nguoi_kiem_tra_sub,
    COALESCE(u.full_name, p.nguoi_kiem_tra_sub) AS nguoi_kiem_tra_ten,
    p.ghi_chu,
    p.created_at
FROM app_cap_phep.phieu_kiem_tra p
JOIN app_cap_phep.cong_trinh ct ON ct.id = p.cong_trinh_id
LEFT JOIN core.users_directory u ON u.username = p.nguoi_kiem_tra_sub OR u.id::text = p.nguoi_kiem_tra_sub;

ALTER VIEW app_cap_phep.v_phieu_kiem_tra OWNER TO dxos_owner;
GRANT SELECT ON app_cap_phep.v_phieu_kiem_tra TO web_user;

-- RPC lập phiếu kiểm tra chủ động cho cán bộ trật tự xây dựng (T-03)
CREATE OR REPLACE FUNCTION app_cap_phep.lap_phieu_kiem_tra(
    p_cong_trinh_id uuid,
    p_ghi_chu text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_ct_tenant text;
    v_ma_ct text;
    v_id uuid;
BEGIN
    IF NOT (
        core.has_role('app:cap-phep:trat-tu-xd')
        OR core.has_role('dx:tenant-admin')
        OR core.has_role('dx:platform-admin')
    ) THEN
        RAISE EXCEPTION 'Chỉ cán bộ trật tự xây dựng hoặc quản trị viên mới được tạo phiếu kiểm tra'
            USING ERRCODE = '42501';
    END IF;

    SELECT tenant, ma_cong_trinh INTO v_ct_tenant, v_ma_ct
    FROM app_cap_phep.cong_trinh
    WHERE id = p_cong_trinh_id;

    IF v_ct_tenant IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy công trình' USING ERRCODE = 'P0002';
    END IF;

    IF v_ct_tenant != core.jwt_tenant() AND NOT core.has_role('dx:platform-admin') THEN
        RAISE EXCEPTION 'Không có quyền trên công trình thuộc đơn vị khác' USING ERRCODE = '42501';
    END IF;

    INSERT INTO app_cap_phep.phieu_kiem_tra (
        tenant, cong_trinh_id, nguon, chi_so, gia_tri, nguong,
        trang_thai, nguoi_kiem_tra_sub, ghi_chu, created_at
    ) VALUES (
        v_ct_tenant, p_cong_trinh_id, 'chu_dong', 'kiem_tra_dinh_ky', 0.0, 0.0,
        'CHO_KIEM_TRA', core.jwt_sub(), p_ghi_chu, now()
    ) RETURNING id INTO v_id;

    PERFORM core.record_audit(
        v_ct_tenant,
        core.jwt_sub(),
        'user',
        'phieu_kiem_tra.created',
        'phieu_kiem_tra',
        v_id::text,
        jsonb_build_object(
            'cong_trinh_id', p_cong_trinh_id,
            'ma_cong_trinh', v_ma_ct,
            'nguon', 'chu_dong',
            'ghi_chu', p_ghi_chu
        )
    );

    PERFORM app_cap_phep.gui_thong_bao(
        v_ct_tenant,
        ARRAY['app:cap-phep:trat-tu-xd'],
        NULL,
        'Phiếu kiểm tra hậu kiểm mới ' || COALESCE(v_ma_ct, ''),
        'Công trình ' || COALESCE(v_ma_ct, '') || ' có phiếu kiểm tra mới: ' || COALESCE(p_ghi_chu, 'Kiểm tra hiện trường'),
        v_id::text
    );

    RETURN jsonb_build_object(
        'status', 'success',
        'id', v_id,
        'phieu_id', v_id,
        'cong_trinh_id', p_cong_trinh_id
    );
END;
$$;

ALTER FUNCTION app_cap_phep.lap_phieu_kiem_tra(uuid, text) OWNER TO dxos_owner;
GRANT EXECUTE ON FUNCTION app_cap_phep.lap_phieu_kiem_tra(uuid, text) TO web_user, svc, dxos_svc, dxos_owner;

-- 6.6 Chính sách cho vai trò hệ thống svc (dành cho microservices xác thực) và dxos_owner
DROP POLICY IF EXISTS rls_ho_so_svc ON app_cap_phep.ho_so;
CREATE POLICY rls_ho_so_svc ON app_cap_phep.ho_so FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_ho_so_tep_svc ON app_cap_phep.ho_so_tep;
CREATE POLICY rls_ho_so_tep_svc ON app_cap_phep.ho_so_tep FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_giay_phep_svc ON app_cap_phep.giay_phep;
CREATE POLICY rls_giay_phep_svc ON app_cap_phep.giay_phep FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_cong_trinh_svc ON app_cap_phep.cong_trinh;
CREATE POLICY rls_cong_trinh_svc ON app_cap_phep.cong_trinh FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_phieu_kiem_tra_svc ON app_cap_phep.phieu_kiem_tra;
CREATE POLICY rls_phieu_kiem_tra_svc ON app_cap_phep.phieu_kiem_tra FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

ALTER TABLE app_cap_phep.so_giay_phep_counter ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_so_giay_phep_counter_svc ON app_cap_phep.so_giay_phep_counter;
CREATE POLICY rls_so_giay_phep_counter_svc ON app_cap_phep.so_giay_phep_counter FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

REVOKE ALL ON app_cap_phep.giay_phep, app_cap_phep.cong_trinh, app_cap_phep.phieu_kiem_tra, app_cap_phep.ho_so FROM web_user;
GRANT SELECT, INSERT ON app_cap_phep.ho_so TO web_user;
GRANT UPDATE (dia_chi_cong_trinh, thua_dat, so_tang, dien_tich_san_m2, khu_quan_ly_kien_truc, updated_at) ON app_cap_phep.ho_so TO web_user;
GRANT SELECT, INSERT ON app_cap_phep.ho_so_tep TO web_user;
GRANT SELECT ON app_cap_phep.giay_phep TO web_user;
GRANT SELECT ON app_cap_phep.cong_trinh TO web_user;
GRANT SELECT ON app_cap_phep.phieu_kiem_tra TO web_user;

-- Cấp quyền DML và thực thi cần thiết cho vai trò dịch vụ nền dxos_svc và vai trò svc (V3-02)
GRANT USAGE ON SCHEMA app_cap_phep TO dxos_svc, svc;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app_cap_phep TO dxos_svc, svc;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app_cap_phep TO dxos_svc, svc;
GRANT EXECUTE ON ALL ROUTINES IN SCHEMA app_cap_phep TO dxos_svc, svc;

-- Tích hợp RPC truy cập khẩn cấp (Break-Glass) cho schema app_cap_phep (V2-09, V3-07, P-01)
CREATE OR REPLACE VIEW app_cap_phep.break_glass AS
SELECT * FROM core_api.break_glass;
REVOKE ALL ON app_cap_phep.break_glass FROM web_user, anon, PUBLIC;

DROP FUNCTION IF EXISTS app_cap_phep.ds_truy_cap_khan(text) CASCADE;
CREATE OR REPLACE FUNCTION app_cap_phep.ds_truy_cap_khan(p_trang_thai text DEFAULT NULL)
RETURNS TABLE(
    id uuid,
    tenant text,
    requester_sub text,
    requester_name text,
    object_type text,
    object_id uuid,
    ma_ho_so text,
    chu_dau_tu_ten text,
    reason text,
    status text,
    approved_by text,
    approved_at timestamptz,
    expires_at timestamptz,
    created_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
BEGIN
    RETURN QUERY
    SELECT
        bg.id,
        bg.tenant,
        bg.requester_sub,
        COALESCE(u.full_name, bg.requester_sub) AS requester_name,
        bg.object_type,
        bg.object_id,
        hs.ma_ho_so,
        hs.ho_ten AS chu_dau_tu_ten,
        bg.reason,
        bg.status,
        bg.approved_by,
        bg.approved_at,
        bg.expires_at,
        bg.created_at
    FROM core_api.ds_truy_cap_khan(p_trang_thai) bg
    LEFT JOIN core.users_directory u ON u.username = bg.requester_sub OR u.id::text = bg.requester_sub
    LEFT JOIN app_cap_phep.ho_so hs ON hs.id = bg.object_id;
END;
$$;

REVOKE ALL ON FUNCTION app_cap_phep.ds_truy_cap_khan(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION app_cap_phep.ds_truy_cap_khan(text) TO web_user, svc, dxos_svc, dxos_owner;

CREATE OR REPLACE FUNCTION app_cap_phep.xin_truy_cap_khan(p_ho_so_id uuid, p_ly_do text)
RETURNS jsonb AS $$
DECLARE
    v_res jsonb;
    v_ma text;
    v_tenant text;
BEGIN
    v_res := core_api.xin_truy_cap_khan('ho_so', p_ho_so_id, p_ly_do);
    SELECT ma_ho_so, tenant INTO v_ma, v_tenant FROM app_cap_phep.ho_so WHERE id = p_ho_so_id;
    IF v_tenant IS NOT NULL THEN
        PERFORM app_cap_phep.gui_thong_bao(
            v_tenant,
            ARRAY['app:cap-phep:lanh-dao'],
            NULL,
            'Yêu cầu truy cập khẩn cấp',
            'Cán bộ yêu cầu truy cập khẩn cấp hồ sơ ' || coalesce(v_ma, p_ho_so_id::text) || '. Lý do: ' || p_ly_do,
            p_ho_so_id::text
        );
    END IF;
    RETURN v_res;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = app_cap_phep, core_api, core, pg_catalog;

CREATE OR REPLACE FUNCTION app_cap_phep.duyet_truy_cap_khan(p_ho_so_id uuid, p_user_sub text, p_dong_y boolean DEFAULT true)
RETURNS jsonb AS $$
DECLARE
    v_sub text;
BEGIN
    SELECT id::text INTO v_sub FROM core.users_directory WHERE username = p_user_sub LIMIT 1;
    v_sub := COALESCE(v_sub, p_user_sub);
    RETURN core_api.duyet_truy_cap_khan('ho_so', p_ho_so_id, v_sub, p_dong_y);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core_api, core;

CREATE OR REPLACE FUNCTION app_cap_phep.duyet_truy_cap_khan(p_object_type text, p_object_id uuid, p_user_sub text, p_dong_y boolean)
RETURNS jsonb AS $$
    SELECT core_api.duyet_truy_cap_khan(p_object_type, p_object_id, p_user_sub, p_dong_y);
$$ LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, core_api, core;

GRANT EXECUTE ON FUNCTION app_cap_phep.xin_truy_cap_khan(uuid, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.duyet_truy_cap_khan(uuid, text, boolean) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.duyet_truy_cap_khan(text, uuid, text, boolean) TO web_user;

CREATE OR REPLACE VIEW app_cap_phep.consents
WITH (security_invoker = true) AS
SELECT * FROM core_api.consents;
REVOKE ALL ON app_cap_phep.consents FROM web_user;
GRANT SELECT ON app_cap_phep.consents TO web_user;

CREATE OR REPLACE VIEW app_cap_phep.dsar_requests
WITH (security_invoker = true) AS
SELECT * FROM core_api.dsar_requests;
REVOKE ALL ON app_cap_phep.dsar_requests FROM PUBLIC, anon, web_user;
GRANT SELECT ON app_cap_phep.dsar_requests TO web_user;

-- N-01: Xóa hoàn toàn view v_audit_log để ngăn ngừa lộ nhật ký kiểm toán toàn phường
DROP VIEW IF EXISTS app_cap_phep.v_audit_log CASCADE;
DROP FUNCTION IF EXISTS app_cap_phep.lay_nhat_ky_ho_so(uuid, int);
DROP FUNCTION IF EXISTS app_cap_phep.lay_nhat_ky_phuong(int);

-- N-01: Hàm lấy nhật ký kiểm toán theo từng hồ sơ có kiểm soát quyền truy cập chặt chẽ
CREATE OR REPLACE FUNCTION app_cap_phep.lay_nhat_ky_ho_so(
    p_ho_so_id uuid,
    p_limit int DEFAULT 50
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, app_cap_phep, core
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_has_access boolean := false;
    v_is_officer boolean := false;
    v_res jsonb;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        PERFORM set_config('response.status', '401', true);
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    -- Kiểm tra quyền truy cập hồ sơ qua hàm can_access_ho_so
    v_has_access := app_cap_phep_private.can_access_ho_so(p_ho_so_id::text, 'read');
    IF NOT v_has_access THEN
        PERFORM core.record_audit(
            cur_tenant,
            cur_sub,
            'user',
            'access.denied',
            'ho_so',
            p_ho_so_id::text,
            jsonb_build_object('loi', 'Truy cap trai phep nhat ky ho so', 'action', 'lay_nhat_ky_ho_so')
        );
        PERFORM set_config('response.status', '403', true);
        RETURN jsonb_build_object('loi', 'Bạn không có quyền xem nhật ký của hồ sơ này', 'ma_loi', 'ACCESS_DENIED');
    END IF;

    -- Kiểm tra người gọi có phải là cán bộ không để lọc PII
    v_is_officer := core.has_role('dx:tenant-admin')
        OR core.has_role('dx:platform-admin')
        OR core.has_role('dx:auditor')
        OR core.has_role('app:cap-phep:tham-dinh')
        OR core.has_role('app:cap-phep:lanh-dao')
        OR core.has_role('app:cap-phep:mot-cua')
        OR core.has_role('app:cap-phep:trat-tu-xd');

    SELECT coalesce(jsonb_agg(sub_q), '[]'::jsonb) INTO v_res
    FROM (
        -- U-07: chủ hồ sơ chỉ thấy họ tên, vai, hành động, thời điểm, lý do; không thấy sub hay chi tiết kỹ thuật
        SELECT
            a.at,
            CASE WHEN v_is_officer THEN a.actor_sub END AS actor_sub,
            COALESCE(u.full_name, CASE WHEN v_is_officer THEN a.actor_sub ELSE 'Hệ thống' END) AS actor_name,
            u.roles AS actor_roles,
            a.action,
            a.object_type,
            a.object_id,
            CASE
                WHEN v_is_officer THEN a.detail
                ELSE jsonb_strip_nulls(jsonb_build_object(
                    'ly_do', COALESCE(a.detail->>'ly_do', a.detail->>'reason', a.detail->>'lyDo'),
                    'trang_thai_moi', a.detail->>'trang_thai_moi'
                ))
            END AS detail
        FROM core.audit_log a
        LEFT JOIN core.users_directory u ON u.username = a.actor_sub OR u.id::text = a.actor_sub
        WHERE a.tenant = cur_tenant
          AND (
              (a.object_id = p_ho_so_id::text)
              OR (a.detail->>'ho_so_id' = p_ho_so_id::text)
              OR (a.detail->>'dossier_id' = p_ho_so_id::text)
              OR (a.action LIKE 'break_glass.%' AND a.object_id = p_ho_so_id::text)
          )
        ORDER BY a.at DESC
        LIMIT coalesce(p_limit, 50)
    ) sub_q;

    RETURN v_res;
END;
$$;
REVOKE ALL ON FUNCTION app_cap_phep.lay_nhat_ky_ho_so(uuid, int) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION app_cap_phep.lay_nhat_ky_ho_so(uuid, int) TO web_user;

-- N-01: Hàm lấy nhật ký kiểm toán toàn phường dành riêng cho tenant-admin và auditor
CREATE OR REPLACE FUNCTION app_cap_phep.lay_nhat_ky_phuong(
    p_limit int DEFAULT 100
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, app_cap_phep, core
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_res jsonb;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        PERFORM set_config('response.status', '401', true);
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    IF NOT (core.has_role('dx:tenant-admin') OR core.has_role('dx:auditor') OR core.has_role('dx:platform-admin')) THEN
        PERFORM set_config('response.status', '403', true);
        RAISE EXCEPTION 'Bạn không có quyền truy cập nhật ký phường' USING ERRCODE = '42501';
    END IF;

    SELECT coalesce(jsonb_agg(sub_q), '[]'::jsonb) INTO v_res
    FROM (
        SELECT
            a.at,
            a.actor_sub,
            a.action,
            a.detail
        FROM core.audit_log a
        WHERE a.tenant = cur_tenant
        ORDER BY a.at DESC
        LIMIT coalesce(p_limit, 100)
    ) sub_q;

    RETURN v_res;
END;
$$;
REVOKE ALL ON FUNCTION app_cap_phep.lay_nhat_ky_phuong(int) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION app_cap_phep.lay_nhat_ky_phuong(int) TO web_user;

---------------------------------------------------------------------------------
-- HỆ THỐNG THÔNG BÁO TÍCH HỢP CHO NGHIỆP VỤ CẤP PHÉP (T-09)
---------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION app_cap_phep.gui_thong_bao(
    p_tenant text,
    p_roles text[],
    p_user_sub text,
    p_title text,
    p_body text,
    p_link text DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_target_user record;
BEGIN
    IF p_user_sub IS NOT NULL AND trim(p_user_sub) <> '' THEN
        INSERT INTO core.notifications (tenant, user_sub, title, body, link)
        VALUES (p_tenant, p_user_sub, p_title, p_body, p_link);

        FOR v_target_user IN
            SELECT username, id::text AS uid FROM core.users_directory
            WHERE (username = p_user_sub OR id::text = p_user_sub) AND tenant = p_tenant
        LOOP
            IF v_target_user.username <> p_user_sub THEN
                INSERT INTO core.notifications (tenant, user_sub, title, body, link)
                VALUES (p_tenant, v_target_user.username, p_title, p_body, p_link);
            END IF;
            IF v_target_user.uid <> p_user_sub THEN
                INSERT INTO core.notifications (tenant, user_sub, title, body, link)
                VALUES (p_tenant, v_target_user.uid, p_title, p_body, p_link);
            END IF;
        END LOOP;
    END IF;

    IF p_roles IS NOT NULL AND array_length(p_roles, 1) > 0 THEN
        FOR v_target_user IN
            SELECT DISTINCT username, id::text AS uid
            FROM core.users_directory
            WHERE tenant = p_tenant
              AND roles && p_roles
        LOOP
            INSERT INTO core.notifications (tenant, user_sub, title, body, link)
            VALUES (p_tenant, v_target_user.username, p_title, p_body, p_link);
            INSERT INTO core.notifications (tenant, user_sub, title, body, link)
            VALUES (p_tenant, v_target_user.uid, p_title, p_body, p_link);
        END LOOP;
    END IF;
END;
$$;

ALTER FUNCTION app_cap_phep.gui_thong_bao(text, text[], text, text, text, text) OWNER TO dxos_owner;
REVOKE ALL ON FUNCTION app_cap_phep.gui_thong_bao(text, text[], text, text, text, text) FROM PUBLIC, anon, web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.gui_thong_bao(text, text[], text, text, text, text) TO svc, dxos_svc, dxos_owner;

DROP FUNCTION IF EXISTS app_cap_phep.lay_thong_bao();
CREATE OR REPLACE FUNCTION app_cap_phep.lay_thong_bao()
RETURNS TABLE (
    id uuid,
    tenant text,
    title text,
    body text,
    link text,
    read_at timestamptz,
    created_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        PERFORM set_config('response.status', '401', true);
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT d.id, d.tenant, d.title, d.body, d.link, d.read_at, d.created_at
    FROM (
        SELECT DISTINCT ON (n.id) n.id, n.tenant, n.title, n.body, n.link, n.read_at, n.created_at
        FROM core.notifications n
        WHERE n.tenant = cur_tenant
          AND (
              n.user_sub = cur_sub
              OR n.user_sub = (SELECT u.username FROM core.users_directory u WHERE u.id::text = cur_sub OR u.username = cur_sub LIMIT 1)
          )
        ORDER BY n.id, n.created_at DESC
    ) d
    ORDER BY d.created_at DESC
    LIMIT 50;
END;
$$;

DROP FUNCTION IF EXISTS app_cap_phep.danh_dau_da_doc(uuid);
CREATE OR REPLACE FUNCTION app_cap_phep.danh_dau_da_doc(p_id uuid DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_username text;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        PERFORM set_config('response.status', '401', true);
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    SELECT u.username INTO v_username
    FROM core.users_directory u
    WHERE u.id::text = cur_sub OR u.username = cur_sub
    LIMIT 1;

    IF p_id IS NULL THEN
        UPDATE core.notifications
        SET read_at = now()
        WHERE tenant = cur_tenant
          AND (user_sub = cur_sub OR user_sub = v_username)
          AND read_at IS NULL;
    ELSE
        UPDATE core.notifications
        SET read_at = now()
        WHERE tenant = cur_tenant
          AND (user_sub = cur_sub OR user_sub = v_username)
          AND id = p_id;
    END IF;

    RETURN jsonb_build_object('success', true);
END;
$$;

REVOKE ALL ON FUNCTION app_cap_phep.lay_thong_bao() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION app_cap_phep.lay_thong_bao() TO web_user;

REVOKE ALL ON FUNCTION app_cap_phep.danh_dau_da_doc(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION app_cap_phep.danh_dau_da_doc(uuid) TO web_user;



---------------------------------------------------------------------------------
-- RPC LẤY DANH SÁCH CÁN BỘ ĐỒNG BỘ THEO TENANT VÀ VAI TRÒ (N-06)
---------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION app_cap_phep.ds_can_bo(p_vai text DEFAULT 'tham-dinh')
RETURNS TABLE (
    sub uuid,
    username text,
    ho_ten text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog, pg_temp
AS $$
DECLARE
    v_tenant text;
    v_role_needed text;
BEGIN
    v_tenant := core.jwt_tenant();
    IF v_tenant IS NULL OR v_tenant = '' THEN
        RAISE EXCEPTION 'Chưa đăng nhập' USING ERRCODE = '42501';
    END IF;

    -- Chỉ vai lãnh đạo và một cửa được gọi (N-06)
    IF NOT (core.has_role('app:cap-phep:lanh-dao') OR core.has_role('app:cap-phep:mot-cua') OR core.has_role('dx:platform-admin')) THEN
        RAISE EXCEPTION 'Chỉ lãnh đạo hoặc một cửa mới có quyền lấy danh sách cán bộ' USING ERRCODE = '42501';
    END IF;

    -- U-07: chỉ trả cán bộ theo đúng một vai nghiệp vụ trong danh sách cho phép, so khớp chính xác
    v_role_needed := CASE WHEN p_vai LIKE 'app:cap-phep:%' THEN p_vai ELSE 'app:cap-phep:' || coalesce(p_vai, '') END;
    IF v_role_needed NOT IN ('app:cap-phep:tham-dinh', 'app:cap-phep:mot-cua', 'app:cap-phep:lanh-dao', 'app:cap-phep:trat-tu-xd') THEN
        RAISE EXCEPTION 'Vai không hợp lệ' USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT
        u.id AS sub,
        u.username,
        u.full_name AS ho_ten
    FROM core.users_directory u
    WHERE u.tenant = v_tenant
      AND u.active = true
      AND v_role_needed = ANY(u.roles)
    ORDER BY u.username;
END;
$$;

REVOKE ALL ON FUNCTION app_cap_phep.ds_can_bo(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION app_cap_phep.ds_can_bo(text) TO web_user, svc, dxos_svc, dxos_owner;

CREATE OR REPLACE FUNCTION app_cap_phep.xu_ly_dsar(
    p_request_id uuid,
    p_status text,
    p_result text DEFAULT NULL,
    p_due_at timestamptz DEFAULT NULL
)
RETURNS jsonb AS $$
    SELECT core_api.xu_ly_dsar(p_request_id, p_status, p_result, p_due_at);
$$ LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, core_api, core;
GRANT EXECUTE ON FUNCTION app_cap_phep.xu_ly_dsar(uuid, text, text, timestamptz) TO web_user;

CREATE OR REPLACE FUNCTION app_cap_phep.dong_y_du_lieu(p_purpose text, p_text_version text DEFAULT '1.0')
RETURNS jsonb AS $$
    SELECT core_api.dong_y_du_lieu(p_purpose, p_text_version);
$$ LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, core_api, core;

CREATE OR REPLACE FUNCTION app_cap_phep.rut_dong_y_du_lieu(p_purpose text)
RETURNS jsonb AS $$
    SELECT core_api.rut_dong_y_du_lieu(p_purpose);
$$ LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, core_api, core;

CREATE OR REPLACE FUNCTION app_cap_phep.gui_yeu_cau_dsar(p_type text, p_legal_basis_note text DEFAULT NULL)
RETURNS jsonb AS $$
    SELECT core_api.gui_yeu_cau_dsar(p_type, p_legal_basis_note);
$$ LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, core_api, core;

GRANT EXECUTE ON FUNCTION app_cap_phep.dong_y_du_lieu(text, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.rut_dong_y_du_lieu(text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.gui_yeu_cau_dsar(text, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.ds_truy_cap_khan(text) TO web_user;

-- RPC Nộp hồ sơ xin cấp phép xây dựng (V2-11)
CREATE OR REPLACE FUNCTION app_cap_phep.nop_ho_so(
    ho_ten text,
    cccd text,
    dien_thoai text,
    dia_chi_cong_trinh text,
    thua_dat text,
    so_tang integer DEFAULT 1,
    dien_tich_san_m2 double precision DEFAULT 100.0,
    khu_quan_ly_kien_truc boolean DEFAULT true
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
#variable_conflict use_column
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_new_id uuid := gen_random_uuid();
    v_ma text;
    v_han_tong timestamptz;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    -- Chỉ vai chu-dau-tu mới có quyền nộp hồ sơ (V4-02)
    IF NOT core.has_role('app:cap-phep:chu-dau-tu') AND NOT core.has_role('dx:platform-admin') THEN
        RAISE EXCEPTION 'Chỉ chủ đầu tư mới có quyền nộp hồ sơ' USING ERRCODE = '42501';
    END IF;

    -- Mã hồ sơ tự động
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
        khu_quan_ly_kien_truc, 'DA_NOP', 'taskKiemTraHopLe', v_han_tong, now(), now()
    );

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'ho_so.nop', 'ho_so', v_new_id::text,
        jsonb_build_object('ma_ho_so', v_ma, 'dia_chi', dia_chi_cong_trinh)
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
        'message', 'Đã nộp hồ sơ xin cấp phép xây dựng thành công'
    );
END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep.nop_ho_so(text, text, text, text, text, integer, double precision, boolean) TO web_user;

-- RPC Bổ sung hồ sơ (V2-11, T-07)
-- U-06: một chữ ký duy nhất. Hàm chỉ cập nhật DỮ LIỆU hồ sơ đang CAN_BO_SUNG;
-- chuyển trạng thái do quy trình làm khi chủ đầu tư hoàn thành taskChoBoSung (sync_flow_state).
DROP FUNCTION IF EXISTS app_cap_phep.bo_sung_ho_so(uuid, uuid, text, text, integer, double precision, boolean, text, text, integer, double precision, boolean);
DROP FUNCTION IF EXISTS app_cap_phep.bo_sung_ho_so(uuid, text, text, integer, double precision, boolean);
CREATE OR REPLACE FUNCTION app_cap_phep.bo_sung_ho_so(
    p_ho_so_id uuid,
    p_dia_chi_cong_trinh text DEFAULT NULL,
    p_thua_dat text DEFAULT NULL,
    p_so_tang integer DEFAULT NULL,
    p_dien_tich_san_m2 double precision DEFAULT NULL,
    p_khu_quan_ly_kien_truc boolean DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_hs app_cap_phep.ho_so%ROWTYPE;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO v_hs FROM app_cap_phep.ho_so WHERE id = p_ho_so_id AND tenant = cur_tenant;
    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ' USING ERRCODE = 'PT404';
    END IF;

    IF v_hs.chu_dau_tu_sub <> cur_sub THEN
        RAISE EXCEPTION 'Chỉ chủ đầu tư mới có quyền bổ sung hồ sơ của mình' USING ERRCODE = '42501';
    END IF;

    IF v_hs.trang_thai <> 'CAN_BO_SUNG' THEN
        RAISE EXCEPTION 'Hồ sơ không ở trạng thái CẦN BỔ SUNG' USING ERRCODE = '22023';
    END IF;

    IF p_so_tang IS NOT NULL AND p_so_tang < 1 THEN
        RAISE EXCEPTION 'Số tầng không hợp lệ' USING ERRCODE = '22023';
    END IF;
    IF p_dien_tich_san_m2 IS NOT NULL AND p_dien_tich_san_m2 <= 0 THEN
        RAISE EXCEPTION 'Diện tích sàn không hợp lệ' USING ERRCODE = '22023';
    END IF;

    UPDATE app_cap_phep.ho_so
    SET dia_chi_cong_trinh = COALESCE(NULLIF(btrim(p_dia_chi_cong_trinh), ''), dia_chi_cong_trinh),
        thua_dat = COALESCE(NULLIF(btrim(p_thua_dat), ''), thua_dat),
        so_tang = COALESCE(p_so_tang, so_tang),
        dien_tich_san_m2 = COALESCE(p_dien_tich_san_m2, dien_tich_san_m2),
        khu_quan_ly_kien_truc = COALESCE(p_khu_quan_ly_kien_truc, khu_quan_ly_kien_truc),
        updated_at = now()
    WHERE id = v_hs.id;

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'ho_so.bo_sung', 'ho_so', v_hs.id::text,
        jsonb_build_object('ma_ho_so', v_hs.ma_ho_so)
    );

    RETURN jsonb_build_object('status', 'success', 'id', v_hs.id);
END;
$$;
ALTER FUNCTION app_cap_phep.bo_sung_ho_so(uuid, text, text, integer, double precision, boolean) OWNER TO dxos_owner;
REVOKE ALL ON FUNCTION app_cap_phep.bo_sung_ho_so(uuid, text, text, integer, double precision, boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_cap_phep.bo_sung_ho_so(uuid, text, text, integer, double precision, boolean) TO web_user;

-- RPC Đính kèm tệp vào hồ sơ (V2-11, V4-01)
CREATE OR REPLACE FUNCTION app_cap_phep.dinh_kem_tep(
    p_ho_so_id uuid,
    p_file_id uuid,
    p_loai text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
#variable_conflict use_column
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_hs app_cap_phep.ho_so%ROWTYPE;
    v_file core.files%ROWTYPE;
    v_has_access boolean := false;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    -- 1. Kiểm tra hồ sơ tồn tại và thuộc tenant của người gọi
    SELECT * INTO v_hs
    FROM app_cap_phep.ho_so
    WHERE id = p_ho_so_id AND tenant = cur_tenant;

    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Hồ sơ không tồn tại hoặc không thuộc địa bàn của bạn' USING ERRCODE = '42501';
    END IF;

    -- 2. Kiểm tra thẩm quyền trên hồ sơ:
    -- Nếu là chủ đầu tư của hồ sơ: chỉ được đính kèm khi ở trạng thái cho phép nộp/bổ sung
    IF v_hs.chu_dau_tu_sub = cur_sub THEN
        IF v_hs.trang_thai NOT IN ('DA_NOP', 'CAN_BO_SUNG') THEN
            RAISE EXCEPTION 'Hồ sơ đang trong quy trình xử lý, không thể đính kèm thêm tệp' USING ERRCODE = '42501';
        END IF;
        v_has_access := true;
    ELSE
        -- Nếu là cán bộ: phải có quyền can_access_ho_so
        v_has_access := app_cap_phep_private.can_access_ho_so(p_ho_so_id::text, 'write');
    END IF;

    IF NOT v_has_access THEN
        RAISE EXCEPTION 'Bạn không có quyền đính kèm tệp vào hồ sơ này' USING ERRCODE = '42501';
    END IF;

    -- 3. Kiểm tra tệp đính kèm: tệp phải thuộc sở hữu của người gọi và cùng tenant
    SELECT * INTO v_file
    FROM core.files
    WHERE id = p_file_id AND tenant = cur_tenant;

    IF v_file.id IS NULL THEN
        RAISE EXCEPTION 'Tệp không tồn tại hoặc không thuộc đơn vị' USING ERRCODE = '42501';
    END IF;

    IF v_file.owner_sub != cur_sub AND NOT core.has_role('dx:platform-admin') THEN
        RAISE EXCEPTION 'Tệp không thuộc sở hữu của người gọi' USING ERRCODE = '42501';
    END IF;

    -- 4. Thêm liên kết tệp vào hồ sơ
    INSERT INTO app_cap_phep.ho_so_tep (ho_so_id, file_id, loai)
    VALUES (p_ho_so_id, p_file_id, p_loai);

    -- Cập nhật liên kết đối tượng trên bảng core.files
    UPDATE core.files
    SET object_type = 'ho_so', object_id = p_ho_so_id::text
    WHERE id = p_file_id;

    RETURN jsonb_build_object('status', 'success', 'ho_so_id', p_ho_so_id, 'file_id', p_file_id);
END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep.dinh_kem_tep(uuid, uuid, text) TO web_user;

--------------------------------------------------------------------------------
-- RPC thong_tin_giay_phep (T-02)
--------------------------------------------------------------------------------

DROP FUNCTION IF EXISTS app_cap_phep.thong_tin_giay_phep(uuid);
CREATE OR REPLACE FUNCTION app_cap_phep.thong_tin_giay_phep(
    p_ho_so_id uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_has_access boolean := false;
    v_hs app_cap_phep.ho_so%ROWTYPE;
    v_gp app_cap_phep.giay_phep%ROWTYPE;
    v_sd core.signed_docs%ROWTYPE;
    v_signer_name text;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    -- Kiểm tra hồ sơ tồn tại
    SELECT * INTO v_hs
    FROM app_cap_phep.ho_so
    WHERE id = p_ho_so_id AND tenant = cur_tenant;

    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ hoặc hồ sơ thuộc địa bàn khác' USING ERRCODE = '42501';
    END IF;

    -- Kiểm tra quyền truy cập: chủ hồ sơ hoặc cán bộ cùng phường (can_access_ho_so)
    v_has_access := app_cap_phep_private.can_access_ho_so(p_ho_so_id::text, 'read');
    IF NOT v_has_access THEN
        RAISE EXCEPTION 'Bạn không có quyền xem thông tin giấy phép của hồ sơ này' USING ERRCODE = '42501';
    END IF;

    -- Nếu hồ sơ đang chờ ký hoặc chưa cấp phép
    IF v_hs.trang_thai = 'CHO_KY' THEN
        RETURN jsonb_build_object(
            'status', 'cho_ky',
            'trang_thai', 'cho_ky',
            'thong_bao', 'Hồ sơ đã được duyệt, đang chờ hệ thống ký số điện tử',
            'ma_ho_so', v_hs.ma_ho_so
        );
    END IF;

    -- Lấy thông tin giấy phép đã cấp
    SELECT * INTO v_gp
    FROM app_cap_phep.giay_phep
    WHERE ho_so_id = p_ho_so_id AND trang_thai = 'hieu_luc'
    ORDER BY ngay_cap DESC
    LIMIT 1;

    IF v_gp.id IS NULL THEN
        RETURN jsonb_build_object(
            'status', 'chua_cap',
            'trang_thai', 'chua_cap',
            'thong_bao', 'Hồ sơ chưa được cấp giấy phép',
            'ma_ho_so', v_hs.ma_ho_so
        );
    END IF;

    -- Lấy thông tin signed_docs
    SELECT * INTO v_sd
    FROM core.signed_docs
    WHERE id = v_gp.signed_doc_id;

    -- U-05: người ký là người thật đã ký (signer_sub lưu lúc ký); không có thì để null, không đoán
    IF v_sd.signer_sub IS NOT NULL THEN
        SELECT u.full_name INTO v_signer_name
        FROM core.users_directory u
        WHERE u.id::text = v_sd.signer_sub
        LIMIT 1;
    END IF;

    RETURN jsonb_build_object(
        'status', 'success',
        'trang_thai', v_sd.status,
        'so_giay_phep', v_gp.so_giay_phep,
        'ngay_cap', v_gp.ngay_cap,
        'nguoi_ky', v_signer_name,
        -- Văn bản cũ chưa có cột algorithm thì suy ra từ kiểu chữ ký (PAdES hoặc OpenBao Transit)
        'thuat_toan', COALESCE(v_sd.algorithm,
                               CASE WHEN COALESCE(v_sd.signature, '') LIKE 'pades%'
                                    THEN 'PAdES (PKCS#11)' ELSE 'Ed25519' END),
        'khoa_phien_ban', v_sd.key_version,
        'ma_bam', v_sd.sha256,
        'chu_ky', v_sd.signature,
        'ma_cong_khai', v_sd.public_code,
        'url_kiem_tra', CASE WHEN v_sd.public_code IS NULL THEN NULL ELSE '/kiem-tra/' || v_sd.public_code END,
        -- U-01: bản gốc chỉ tải được khi đăng nhập và có quyền với hồ sơ
        'file_url', CASE WHEN v_sd.id IS NULL THEN NULL ELSE '/api/v1/docs/' || v_sd.id::text || '/download' END
    );
END;
$$;

ALTER FUNCTION app_cap_phep.thong_tin_giay_phep(uuid) OWNER TO dxos_owner;
GRANT EXECUTE ON FUNCTION app_cap_phep.thong_tin_giay_phep(uuid) TO web_user, dxos_owner, dxos_svc, svc;

-- Hợp đồng phân quyền đối tượng ho_so (V2-08, V3-03: đặt trong schema nội bộ app_cap_phep_private)
CREATE OR REPLACE FUNCTION app_cap_phep_private.can_access_ho_so(p_ho_so_id text, p_action text DEFAULT 'read')
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
#variable_conflict use_column
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_hs app_cap_phep.ho_so%ROWTYPE;
    v_is_assigned boolean := false;
    v_has_break_glass boolean := false;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RETURN false;
    END IF;

    IF core.has_role('dx:platform-admin') OR core.has_role('dx:service') THEN
        RETURN true;
    END IF;

    SELECT * INTO v_hs
    FROM app_cap_phep.ho_so
    WHERE id = p_ho_so_id::uuid AND tenant = cur_tenant;

    IF v_hs.id IS NULL THEN
        RETURN false;
    END IF;

    -- Chủ đầu tư truy cập hồ sơ của mình
    IF v_hs.chu_dau_tu_sub = cur_sub THEN
        RETURN true;
    END IF;

    -- Cán bộ một cửa hoặc lãnh đạo
    IF core.has_role('app:cap-phep:lanh-dao') OR core.has_role('app:cap-phep:mot-cua') THEN
        RETURN true;
    END IF;

    -- Thẩm định viên được phân công
    SELECT EXISTS (
        SELECT 1 FROM core.assignments a
        WHERE a.tenant = cur_tenant AND a.object_type = 'ho_so' AND a.object_id = v_hs.id
          AND (
              a.user_sub = cur_sub
              OR a.user_sub = (SELECT username FROM core.users_directory WHERE id::text = cur_sub LIMIT 1)
              OR a.user_sub = (SELECT id::text FROM core.users_directory WHERE username = cur_sub LIMIT 1)
          )
    ) INTO v_is_assigned;

    IF v_is_assigned THEN
        RETURN true;
    END IF;

    -- Quyền truy cập khẩn cấp hợp lệ
    SELECT EXISTS (
        SELECT 1 FROM core.break_glass bg
        WHERE bg.tenant = cur_tenant AND bg.object_type = 'ho_so' AND bg.object_id = v_hs.id
          AND (
              bg.requester_sub = cur_sub
              OR bg.requester_sub = (SELECT username FROM core.users_directory WHERE id::text = cur_sub LIMIT 1)
              OR bg.requester_sub = (SELECT id::text FROM core.users_directory WHERE username = cur_sub LIMIT 1)
          )
          AND bg.status = 'approved' AND bg.expires_at > now()
    ) INTO v_has_break_glass;

    IF v_has_break_glass THEN
        RETURN true;
    END IF;

    RETURN false;
END;
$$;

DROP FUNCTION IF EXISTS app_cap_phep.can_access_ho_so(text, text);
GRANT EXECUTE ON FUNCTION app_cap_phep_private.can_access_ho_so(text, text) TO svc, dxos_svc, dxos_owner;

-- Hợp đồng đồng bộ trạng thái quy trình nghiệp vụ (V2-08, V3-03: đặt trong schema nội bộ app_cap_phep_private)
CREATE OR REPLACE FUNCTION app_cap_phep_private.sync_flow_state(
    p_process_id text,
    p_task_def text,
    p_variables jsonb DEFAULT '{}'::jsonb
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    new_trang_thai text := NULL;
    new_buoc text := NULL;
    v_hs app_cap_phep.ho_so%ROWTYPE;
BEGIN
    SELECT * INTO v_hs FROM app_cap_phep.ho_so
    WHERE (process_instance_id IS NOT NULL AND process_instance_id = p_process_id)
       OR (ma_ho_so IS NOT NULL AND (ma_ho_so = (p_variables->>'ma_ho_so') OR ma_ho_so = (p_variables->>'business_key')))
       OR (id IS NOT NULL AND id::text = (p_variables->>'ho_so_id'))
    ORDER BY created_at DESC
    LIMIT 1;

    IF p_task_def IN ('process_started', 'start') THEN
        UPDATE app_cap_phep.ho_so
        SET process_instance_id = p_process_id,
            han_buoc_at = COALESCE((p_variables->>'han_buoc_at')::timestamptz, han_buoc_at),
            updated_at = now()
        WHERE (ma_ho_so IS NOT NULL AND (ma_ho_so = (p_variables->>'ma_ho_so') OR ma_ho_so = (p_variables->>'business_key')))
           OR (id IS NOT NULL AND id::text = (p_variables->>'ho_so_id'));
        RETURN;
    END IF;

    IF p_task_def = 'taskKiemTraHopLe' THEN
        IF (p_variables->>'hoSoHopLe')::boolean IS FALSE THEN
            new_trang_thai := 'CAN_BO_SUNG';
            new_buoc := 'tiep_nhan';
            UPDATE app_cap_phep.ho_so
            SET ly_do_bo_sung = COALESCE(p_variables->>'lyDoBoSung', p_variables->>'lyDoTra', 'Cần bổ sung tài liệu hồ sơ'),
                updated_at = now()
            WHERE process_instance_id = p_process_id
               OR (id IS NOT NULL AND id::text = (p_variables->>'ho_so_id'));

            IF v_hs.id IS NOT NULL THEN
                PERFORM app_cap_phep.gui_thong_bao(
                    v_hs.tenant,
                    NULL,
                    v_hs.chu_dau_tu_sub,
                    'Yêu cầu bổ sung hồ sơ ' || v_hs.ma_ho_so,
                    'Hồ sơ ' || v_hs.ma_ho_so || ' cần bổ sung giấy tờ. Lý do: ' || COALESCE(p_variables->>'lyDoBoSung', p_variables->>'lyDoTra', 'Cần bổ sung hồ sơ theo quy định'),
                    v_hs.id::text
                );
            END IF;
        ELSE
            new_trang_thai := 'TIEP_NHAN';
            new_buoc := 'phan_cong';

            IF v_hs.id IS NOT NULL THEN
                PERFORM app_cap_phep.gui_thong_bao(
                    v_hs.tenant,
                    ARRAY['app:cap-phep:lanh-dao'],
                    NULL,
                    'Hồ sơ cần phân công ' || v_hs.ma_ho_so,
                    'Hồ sơ ' || v_hs.ma_ho_so || ' đã được tiếp nhận hợp lệ, chờ lãnh đạo phân công cán bộ thẩm định.',
                    v_hs.id::text
                );
            END IF;
        END IF;
    ELSIF p_task_def = 'taskChoBoSung' THEN
        new_trang_thai := 'DA_NOP';
        new_buoc := 'tiep_nhan';
        IF v_hs.id IS NOT NULL THEN
            PERFORM app_cap_phep.gui_thong_bao(
                v_hs.tenant,
                ARRAY['app:cap-phep:mot-cua'],
                NULL,
                'Hồ sơ đã bổ sung ' || v_hs.ma_ho_so,
                'Chủ đầu tư đã bổ sung hồ sơ ' || v_hs.ma_ho_so || ', cần kiểm tra lại.',
                v_hs.id::text
            );
        END IF;
    ELSIF p_task_def = 'taskPhanCong' THEN
        new_trang_thai := 'DUOC_PHAN_CONG';
        new_buoc := 'tham_dinh';
        IF p_variables->>'nguoiThamDinh' IS NOT NULL THEN
            INSERT INTO core.assignments (tenant, object_type, object_id, user_sub, role)
            SELECT tenant, 'ho_so', id,
                   COALESCE((SELECT id::text FROM core.users_directory WHERE username = p_variables->>'nguoiThamDinh' LIMIT 1), p_variables->>'nguoiThamDinh'),
                   'tham-dinh'
            FROM app_cap_phep.ho_so
            WHERE process_instance_id = p_process_id
               OR (ma_ho_so IS NOT NULL AND ma_ho_so = (p_variables->>'ma_ho_so'))
               OR (id IS NOT NULL AND id::text = (p_variables->>'ho_so_id'))
            ON CONFLICT DO NOTHING;

            IF v_hs.id IS NOT NULL THEN
                PERFORM app_cap_phep.gui_thong_bao(
                    v_hs.tenant,
                    NULL,
                    p_variables->>'nguoiThamDinh',
                    'Phân công thẩm định ' || v_hs.ma_ho_so,
                    'Bạn đã được phân công thẩm định hồ sơ ' || v_hs.ma_ho_so || '.',
                    v_hs.id::text
                );
            END IF;
        END IF;
    ELSIF p_task_def IN ('taskThamDinh', 'taskThamDinhNhanh', 'taskThamDinhChuyenSau', 'taskThamDinhDonGian') THEN
        new_trang_thai := 'CHO_DUYET';
        new_buoc := 'phe_duyet';

        IF v_hs.id IS NOT NULL THEN
            PERFORM app_cap_phep.gui_thong_bao(
                v_hs.tenant,
                ARRAY['app:cap-phep:lanh-dao'],
                NULL,
                'Hồ sơ chờ phê duyệt ' || v_hs.ma_ho_so,
                'Hồ sơ ' || v_hs.ma_ho_so || ' đã thẩm định kỹ thuật xong, đang chờ lãnh đạo phê duyệt ký số.',
                v_hs.id::text
            );
        END IF;
    ELSIF p_task_def = 'taskDuyetCapPhep' OR p_task_def = 'taskPheDuyet' THEN
        IF (p_variables->>'pheDuyet')::boolean IS FALSE OR (p_variables->>'dongYCapPhep')::boolean IS FALSE THEN
            new_trang_thai := 'TU_CHOI';
            new_buoc := 'hoan_thanh';
        ELSE
            new_trang_thai := 'CHO_KY';
            new_buoc := 'hoan_thanh';
        END IF;
    ELSIF p_task_def = 'taskKiemTraHienTruong' THEN
        UPDATE app_cap_phep.phieu_kiem_tra
        SET ket_luan = CASE WHEN (p_variables->>'ketLuan') = 'dat' THEN 'Đạt tiêu chuẩn' ELSE 'Có vi phạm' END,
            trang_thai = CASE WHEN (p_variables->>'ketLuan') = 'dat' THEN 'DA_XU_LY' ELSE 'DANG_KIEM_TRA' END,
            bien_ban_file_id = CASE WHEN (p_variables->>'bien_ban_file_id') IS NOT NULL THEN (p_variables->>'bien_ban_file_id')::uuid ELSE bien_ban_file_id END,
            nguoi_kiem_tra_sub = COALESCE(core.jwt_sub(), nguoi_kiem_tra_sub),
            ghi_chu = COALESCE(p_variables->>'ghiChu', ghi_chu)
        WHERE process_instance_id = p_process_id;

        PERFORM core.record_audit(
            core.jwt_tenant(),
            core.jwt_sub(),
            'user',
            'phieu_kiem_tra.completed',
            'phieu_kiem_tra',
            COALESCE((SELECT id::text FROM app_cap_phep.phieu_kiem_tra WHERE process_instance_id = p_process_id LIMIT 1), 'unknown'),
            p_variables
        );
    ELSIF p_task_def = 'taskXuLyViPham' THEN
        UPDATE app_cap_phep.phieu_kiem_tra
        SET trang_thai = 'DA_XU_LY',
            ghi_chu = COALESCE(p_variables->>'ghiChu', ghi_chu),
            bien_ban_file_id = CASE WHEN (p_variables->>'bien_ban_file_id') IS NOT NULL THEN (p_variables->>'bien_ban_file_id')::uuid ELSE bien_ban_file_id END
        WHERE process_instance_id = p_process_id;

        PERFORM core.record_audit(
            core.jwt_tenant(),
            core.jwt_sub(),
            'user',
            'phieu_kiem_tra.xu_ly_vi_pham',
            'phieu_kiem_tra',
            COALESCE((SELECT id::text FROM app_cap_phep.phieu_kiem_tra WHERE process_instance_id = p_process_id LIMIT 1), 'unknown'),
            p_variables
        );
    END IF;

    IF new_trang_thai IS NOT NULL THEN
        UPDATE app_cap_phep.ho_so
        SET trang_thai = new_trang_thai,
            buoc = new_buoc,
            han_buoc_at = COALESCE((p_variables->>'han_buoc_at')::timestamptz, han_buoc_at),
            process_instance_id = COALESCE(process_instance_id, p_process_id),
            updated_at = now()
        WHERE process_instance_id = p_process_id
           OR (ma_ho_so IS NOT NULL AND ma_ho_so = (p_variables->>'ma_ho_so'))
           OR (id IS NOT NULL AND id::text = (p_variables->>'ho_so_id'));
    END IF;
END;
$$;

DROP FUNCTION IF EXISTS app_cap_phep.sync_flow_state(text, text, jsonb);
GRANT EXECUTE ON FUNCTION app_cap_phep_private.sync_flow_state(text, text, jsonb) TO svc, dxos_svc, dxos_owner;

-- Hàm hook ghi nhận quá hạn bước quy trình SLA (P-04)
DROP FUNCTION IF EXISTS app_cap_phep.ghi_qua_han(text, text);
DROP FUNCTION IF EXISTS app_cap_phep_private.ghi_qua_han(text, text);
DROP FUNCTION IF EXISTS app_cap_phep_private.ghi_qua_han(text, text, text);

CREATE OR REPLACE FUNCTION app_cap_phep_private.ghi_qua_han(
    p_process_id text,
    p_task_def text DEFAULT NULL,
    p_tenant text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_hs app_cap_phep.ho_so%ROWTYPE;
BEGIN
    SELECT * INTO v_hs
    FROM app_cap_phep.ho_so
    WHERE process_instance_id = p_process_id
      AND (p_tenant IS NULL OR tenant = p_tenant)
    LIMIT 1;

    IF v_hs.id IS NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'reason', 'ho_so_not_found',
            'process_id', p_process_id
        );
    END IF;

    UPDATE app_cap_phep.ho_so
    SET qua_han = true,
        updated_at = now()
    WHERE id = v_hs.id;

    -- Ghi nhận audit log với hành động sla.qua_han vào chuỗi băm WORM
    PERFORM core.record_audit(
        v_hs.tenant,
        'system',
        'system',
        'sla.qua_han',
        'ho_so',
        v_hs.id::text,
        jsonb_build_object(
            'ma_ho_so', v_hs.ma_ho_so,
            'process_instance_id', p_process_id,
            'task_def', p_task_def,
            'han_buoc_at', v_hs.han_buoc_at,
            'ghi_chu', 'Quá hạn giải quyết bước quy trình theo SLA'
        )
    );

    RETURN jsonb_build_object(
        'success', true,
        'process_id', p_process_id,
        'ho_so_id', v_hs.id,
        'qua_han', true
    );
END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep_private.ghi_qua_han(text, text, text) TO svc, dxos_svc, dxos_owner;

-- Hàm kiểm tra hợp lệ trước khi ký lại hoặc ký duyệt hook (P-02)
CREATE OR REPLACE FUNCTION app_cap_phep_private.kiem_tra_hook_ky(p_process_id text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_hs app_cap_phep.ho_so%ROWTYPE;
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
            'ho_so_id', NULL
        );
    END IF;

    RETURN jsonb_build_object(
        'found', true,
        'tenant', v_hs.tenant,
        'trang_thai', v_hs.trang_thai,
        'ho_so_id', v_hs.id
    );
END;
$$;
DROP FUNCTION IF EXISTS app_cap_phep.kiem_tra_hook_ky(text);
GRANT EXECUTE ON FUNCTION app_cap_phep_private.kiem_tra_hook_ky(text) TO svc, dxos_svc, dxos_owner;

-- Hàm trích xuất dữ liệu hồ sơ để ký số (Z-04, P-02)
DROP FUNCTION IF EXISTS app_cap_phep_private.du_lieu_giay_phep(text);
DROP FUNCTION IF EXISTS app_cap_phep_private.du_lieu_giay_phep(text, text);
CREATE OR REPLACE FUNCTION app_cap_phep_private.du_lieu_giay_phep(
    p_process_id text,
    p_tenant text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_hs app_cap_phep.ho_so%ROWTYPE;
BEGIN
    SELECT * INTO v_hs
    FROM app_cap_phep.ho_so
    WHERE process_instance_id = p_process_id
      AND (p_tenant IS NULL OR tenant = p_tenant)
    LIMIT 1;

    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ với process_instance_id = %', p_process_id;
    END IF;

    RETURN jsonb_build_object(
        'ho_so_id', v_hs.id,
        'ma_ho_so', v_hs.ma_ho_so,
        'chu_dau_tu', v_hs.ho_ten,
        'cccd', v_hs.cccd,
        'dia_chi_cong_trinh', v_hs.dia_chi_cong_trinh,
        'thua_dat', v_hs.thua_dat,
        'so_tang', v_hs.so_tang,
        'dien_tich_san_m2', v_hs.dien_tich_san_m2,
        'tenant', v_hs.tenant,
        'ngay_cap', to_char(now(), 'DD/MM/YYYY')
    );
END;
$$;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.du_lieu_giay_phep(text, text) TO svc, dxos_svc, dxos_owner;

-- Hàm cấp giấy phép và tạo công trình sau khi ký số (Z-04, N-02, P-02, P-07)
DROP FUNCTION IF EXISTS app_cap_phep_private.cap_giay_phep(text, uuid, text);
DROP FUNCTION IF EXISTS app_cap_phep_private.cap_giay_phep(text, uuid, text, text);
CREATE OR REPLACE FUNCTION app_cap_phep_private.cap_giay_phep(
    p_process_id text,
    p_signed_doc_id uuid,
    p_public_code text,
    p_tenant text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_hs app_cap_phep.ho_so%ROWTYPE;
    v_existing_gp app_cap_phep.giay_phep%ROWTYPE;
    v_existing_entity_id text;
    v_existing_public_code text;
    v_so_gp text;
    v_year text := to_char(now(), 'YYYY');
    v_seq int;
    v_gp_id uuid;
    v_ct_id uuid;
    v_ma_ct text;
BEGIN
    -- 1. Khóa hàng hồ sơ chống race condition (N-02, P-02)
    SELECT * INTO v_hs
    FROM app_cap_phep.ho_so
    WHERE process_instance_id = p_process_id
      AND (p_tenant IS NULL OR tenant = p_tenant)
    FOR UPDATE;

    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ với process_instance_id = %', p_process_id;
    END IF;

    -- 2. Kiểm tra tính idempotent: nếu đã có giấy phép hiệu lực cho hồ sơ này, trả về giấy phép hiện tại (N-02, P-07)
    SELECT * INTO v_existing_gp
    FROM app_cap_phep.giay_phep
    WHERE ho_so_id = v_hs.id AND trang_thai = 'hieu_luc'
    LIMIT 1;

    IF v_existing_gp.id IS NOT NULL THEN
        SELECT public_code INTO v_existing_public_code
        FROM core.signed_docs
        WHERE id = v_existing_gp.signed_doc_id;

        SELECT id, entity_id INTO v_ct_id, v_existing_entity_id
        FROM app_cap_phep.cong_trinh
        WHERE giay_phep_id = v_existing_gp.id
        LIMIT 1;

        RETURN jsonb_build_object(
            'status', 'success',
            'idempotent', true,
            'giay_phep_id', v_existing_gp.id,
            'so_giay_phep', v_existing_gp.so_giay_phep,
            'cong_trinh_id', v_ct_id,
            'entity_id', COALESCE(v_existing_entity_id, 'urn:ngsi-ld:Site:CT-' || replace(v_existing_gp.so_giay_phep, 'GPXD-', '')),
            'public_code', COALESCE(v_existing_public_code, p_public_code)
        );
    END IF;

    -- 3. Kiểm tra trạng thái hồ sơ phải là CHO_KY (N-02)
    IF v_hs.trang_thai <> 'CHO_KY' THEN
        RAISE EXCEPTION 'Hồ sơ chưa ở trạng thái CHO_KY (trạng thái hiện tại: %)', v_hs.trang_thai
            USING ERRCODE = '55000';
    END IF;

    -- 4. Bảng đếm số giấy phép theo tenant và năm để sinh số tăng dần không đụng độ (N-02)
    INSERT INTO app_cap_phep.so_giay_phep_counter (tenant, nam, gia_tri)
    VALUES (v_hs.tenant, EXTRACT(YEAR FROM now())::int, 1)
    ON CONFLICT (tenant, nam)
    DO UPDATE SET gia_tri = app_cap_phep.so_giay_phep_counter.gia_tri + 1
    RETURNING gia_tri INTO v_seq;

    v_so_gp := 'GPXD-' || v_hs.tenant || '-' || v_year || '-' || lpad(v_seq::text, 6, '0');

    -- 5. Insert giay_phep
    INSERT INTO app_cap_phep.giay_phep (
        tenant, ho_so_id, so_giay_phep, signed_doc_id
    ) VALUES (
        v_hs.tenant, v_hs.id, v_so_gp, p_signed_doc_id
    ) RETURNING id INTO v_gp_id;

    -- Mã công trình
    v_ma_ct := 'CT-' || replace(v_so_gp, 'GPXD-', '');

    -- Insert cong_trinh (entity_id = 'urn:ngsi-ld:Site:' || ma_cong_trinh)
    INSERT INTO app_cap_phep.cong_trinh (
        tenant, giay_phep_id, ma_cong_trinh, entity_id, dia_chi
    ) VALUES (
        v_hs.tenant, v_gp_id, v_ma_ct, 'urn:ngsi-ld:Site:' || v_ma_ct, v_hs.dia_chi_cong_trinh
    ) RETURNING id INTO v_ct_id;

    -- Đặt hồ sơ sang DA_CAP
    UPDATE app_cap_phep.ho_so
    SET trang_thai = 'DA_CAP',
        buoc = 'da_cap',
        updated_at = now()
    WHERE id = v_hs.id;

    -- Ghi audit log
    PERFORM core.record_audit(
        v_hs.tenant,
        core.jwt_sub(),
        'service',
        'giay_phep.issued',
        'giay_phep',
        v_gp_id::text,
        jsonb_build_object(
            'so_giay_phep', v_so_gp,
            'ho_so_id', v_hs.id,
            'signed_doc_id', p_signed_doc_id,
            'public_code', p_public_code,
            'cong_trinh_id', v_ct_id,
            'entity_id', 'urn:ngsi-ld:Site:' || v_ma_ct
        )
    );

    PERFORM app_cap_phep.gui_thong_bao(
        v_hs.tenant,
        NULL,
        v_hs.chu_dau_tu_sub,
        'Đã cấp giấy phép ' || v_so_gp,
        'Hồ sơ ' || v_hs.ma_ho_so || ' đã được cấp Giấy phép xây dựng số ' || v_so_gp || '.',
        v_hs.id::text
    );

    RETURN jsonb_build_object(
        'status', 'success',
        'idempotent', false,
        'giay_phep_id', v_gp_id,
        'so_giay_phep', v_so_gp,
        'cong_trinh_id', v_ct_id,
        'entity_id', 'urn:ngsi-ld:Site:' || v_ma_ct,
        'public_code', p_public_code
    );
END;
$$;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.cap_giay_phep(text, uuid, text, text) TO svc, dxos_svc, dxos_owner;

-- Hàm tạo phiếu kiểm tra hậu kiểm cho cảnh báo IoT (Z-06, N-04, N-05)
CREATE OR REPLACE FUNCTION app_cap_phep_private.tao_phieu_kiem_tra(
    p_tenant text,
    p_site_id text,
    p_entity_id text,
    p_chi_so text,
    p_gia_tri double precision,
    p_nguong double precision,
    p_process_instance_id text DEFAULT NULL,
    p_window_minutes int DEFAULT 60
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_ct_id uuid;
    v_exists boolean := false;
    v_id uuid;
    v_clean_site_id text;
BEGIN
    v_clean_site_id := regexp_replace(COALESCE(p_site_id, ''), '^urn:ngsi-ld:Site:', '');

    -- 1. Tìm công trình theo entity_id hoặc ma_cong_trinh
    SELECT id INTO v_ct_id
    FROM app_cap_phep.cong_trinh
    WHERE tenant = p_tenant
      AND (
          entity_id = p_entity_id
          OR ma_cong_trinh = p_site_id
          OR ma_cong_trinh = v_clean_site_id
          OR entity_id = 'urn:ngsi-ld:Site:' || p_site_id
          OR entity_id = 'urn:ngsi-ld:Site:' || v_clean_site_id
      )
    LIMIT 1;

    -- N-05: Nếu không tìm thấy công trình khớp với site_id, KHÔNG sinh phiếu, ghi audit alert.unmatched_site
    IF v_ct_id IS NULL THEN
        PERFORM core.record_audit(
            p_tenant,
            core.jwt_sub(),
            'system',
            'alert.unmatched_site',
            'sensor',
            COALESCE(p_site_id, p_entity_id),
            jsonb_build_object(
                'site_id', p_site_id,
                'entity_id', p_entity_id,
                'chi_so', p_chi_so,
                'gia_tri', p_gia_tri,
                'nguong', p_nguong,
                'ly_do', 'Site khong khop voi bat ky cong trinh nao tren dia ban'
            )
        );

        RETURN jsonb_build_object(
            'created', false,
            'reason', 'unmatched_site',
            'site_id', p_site_id
        );
    END IF;

    -- N-04: Dùng khóa advisory theo (tenant, cong_trinh_id, chi_so) chống race condition
    PERFORM pg_advisory_xact_lock(hashtext(p_tenant || ':' || v_ct_id::text || ':' || p_chi_so));

    -- P-03: Kiểm tra chống trùng trong cửa sổ window_minutes
    DECLARE
        v_existing_phieu app_cap_phep.phieu_kiem_tra%ROWTYPE;
    BEGIN
        SELECT * INTO v_existing_phieu
        FROM app_cap_phep.phieu_kiem_tra
        WHERE tenant = p_tenant
          AND cong_trinh_id = v_ct_id
          AND chi_so = p_chi_so
          AND created_at >= (now() - (p_window_minutes || ' minutes')::interval)
        ORDER BY created_at DESC
        LIMIT 1;

        IF v_existing_phieu.id IS NOT NULL THEN
            -- P-03: Nếu phiếu trong cửa sổ chưa có process_instance_id, trả pending_process để relay mở bù quy trình
            IF v_existing_phieu.process_instance_id IS NULL THEN
                RETURN jsonb_build_object(
                    'created', false,
                    'reason', 'pending_process',
                    'phieu_id', v_existing_phieu.id,
                    'id', v_existing_phieu.id,
                    'cong_trinh_id', v_ct_id,
                    'chi_so', p_chi_so
                );
            END IF;

            RETURN jsonb_build_object(
                'created', false,
                'reason', 'deduplicated',
                'cong_trinh_id', v_ct_id,
                'chi_so', p_chi_so,
                'phieu_id', v_existing_phieu.id,
                'process_instance_id', v_existing_phieu.process_instance_id
            );
        END IF;
    END;

    -- Tạo phiếu kiểm tra
    INSERT INTO app_cap_phep.phieu_kiem_tra (
        tenant, cong_trinh_id, nguon, chi_so, gia_tri, nguong, trang_thai, process_instance_id
    ) VALUES (
        p_tenant, v_ct_id, 'cam_bien', p_chi_so, p_gia_tri, p_nguong, 'CHO_KIEM_TRA', p_process_instance_id
    ) RETURNING id INTO v_id;

    -- Ghi audit log
    PERFORM core.record_audit(
        p_tenant,
        core.jwt_sub(),
        'system',
        'phieu_kiem_tra.created',
        'phieu_kiem_tra',
        v_id::text,
        jsonb_build_object(
            'site_id', p_site_id,
            'entity_id', p_entity_id,
            'chi_so', p_chi_so,
            'gia_tri', p_gia_tri,
            'nguong', p_nguong,
            'cong_trinh_id', v_ct_id,
            'process_instance_id', p_process_instance_id
        )
    );

    PERFORM app_cap_phep.gui_thong_bao(
        p_tenant,
        ARRAY['app:cap-phep:trat-tu-xd'],
        NULL,
        'Cảnh báo cảm biến công trình ' || COALESCE(p_site_id, ''),
        'Chỉ số ' || p_chi_so || ' đạt ' || p_gia_tri || ' vượt ngưỡng ' || p_nguong || '. Đã tự động tạo phiếu kiểm tra.',
        v_id::text
    );

    RETURN jsonb_build_object(
        'created', true,
        'phieu_id', v_id,
        'id', v_id,
        'cong_trinh_id', v_ct_id,
        'process_instance_id', p_process_instance_id
    );
END;
$$;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.tao_phieu_kiem_tra(text, text, text, text, double precision, double precision, text, int) TO svc, dxos_svc, dxos_owner;

-- Hàm liên kết quy trình Flowable sau khi khởi tạo vào phiếu kiểm tra (N-04)
CREATE OR REPLACE FUNCTION app_cap_phep_private.gan_quy_trinh_phieu(
    p_phieu_id uuid,
    p_process_instance_id text
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
BEGIN
    UPDATE app_cap_phep.phieu_kiem_tra
    SET process_instance_id = p_process_instance_id
    WHERE id = p_phieu_id;
END;
$$;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.gan_quy_trinh_phieu(uuid, text) TO svc, dxos_svc, dxos_owner;

-- Thu hồi quyền mặc định và cấp quyền an toàn (Z-14)
ALTER DEFAULT PRIVILEGES IN SCHEMA app_cap_phep REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA app_cap_phep_private REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA app_cap_phep, app_cap_phep_private FROM PUBLIC, anon;

-- Cấp lại quyền gọi hàm RPC có chọn lọc cho web_user
GRANT EXECUTE ON FUNCTION app_cap_phep.mo_ho_so(uuid) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.mo_ho_so(text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.nop_ho_so(text, text, text, text, text, integer, double precision, boolean) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.dinh_kem_tep(uuid, uuid, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.xin_truy_cap_khan(uuid, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.duyet_truy_cap_khan(uuid, text, boolean) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.xu_ly_dsar(uuid, text, text, timestamptz) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.dong_y_du_lieu(text, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.rut_dong_y_du_lieu(text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.gui_yeu_cau_dsar(text, text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.ds_truy_cap_khan(text) TO web_user;
GRANT EXECUTE ON FUNCTION app_cap_phep.gui_thong_bao(text, text[], text, text, text, text) TO svc, dxos_svc, dxos_owner;
GRANT EXECUTE ON FUNCTION app_cap_phep.lay_nhat_ky_ho_so(uuid, int) TO web_user, svc, dxos_svc, dxos_owner;
GRANT EXECUTE ON FUNCTION app_cap_phep.lay_nhat_ky_phuong(int) TO web_user, svc, dxos_svc, dxos_owner;
GRANT EXECUTE ON FUNCTION app_cap_phep.lay_thong_bao() TO web_user, svc, dxos_svc, dxos_owner;
GRANT EXECUTE ON FUNCTION app_cap_phep.danh_dau_da_doc(uuid) TO web_user, svc, dxos_svc, dxos_owner;
GRANT EXECUTE ON FUNCTION app_cap_phep.thong_tin_giay_phep(uuid) TO web_user, svc, dxos_svc, dxos_owner;
GRANT EXECUTE ON FUNCTION app_cap_phep.lap_phieu_kiem_tra(uuid, text) TO web_user, svc, dxos_svc, dxos_owner;
GRANT EXECUTE ON FUNCTION app_cap_phep.ds_can_bo(text) TO web_user, svc, dxos_svc, dxos_owner;

-- U-04: kiểm tra vị trí (mã công trình hoặc entity_id) thuộc địa bàn, dùng cho mô phỏng cảm biến
CREATE OR REPLACE FUNCTION app_cap_phep_private.vi_tri_thuoc_dia_ban(p_site text, p_tenant text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = app_cap_phep, pg_catalog
AS $$
    SELECT EXISTS (
        SELECT 1 FROM app_cap_phep.cong_trinh
        WHERE tenant = p_tenant
          AND (ma_cong_trinh = p_site OR entity_id = p_site OR entity_id = 'urn:ngsi-ld:Site:' || p_site)
    );
$$;
ALTER FUNCTION app_cap_phep_private.vi_tri_thuoc_dia_ban(text, text) OWNER TO dxos_owner;
REVOKE ALL ON FUNCTION app_cap_phep_private.vi_tri_thuoc_dia_ban(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.vi_tri_thuoc_dia_ban(text, text) TO svc, dxos_svc, dxos_owner;

-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

-- Cài đặt các tiện ích mở rộng
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- Khởi tạo các vai trò PostgREST
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'web_user') THEN
        CREATE ROLE web_user NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'svc') THEN
        CREATE ROLE svc NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticator') THEN
        CREATE ROLE authenticator NOINHERIT LOGIN;
    END IF;
END $$;

GRANT anon TO authenticator;
GRANT web_user TO authenticator;
GRANT web_user, svc TO dxos_svc;

-- Khởi tạo các schema
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS core_api;

GRANT USAGE ON SCHEMA core TO anon, web_user, svc, dxos_svc, dxos_owner;
GRANT USAGE ON SCHEMA core_api TO anon, web_user, svc, dxos_svc, dxos_owner;

--------------------------------------------------------------------------------
-- 1. CÁC HÀM TIỆN ÍCH ĐỊNH DANH VÀ BẢO MẬT (LÕI TẦNG 1)
--------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION core.jwt_claims()
RETURNS jsonb AS $$
    SELECT coalesce(nullif(current_setting('request.jwt.claims', true), '')::jsonb, '{}'::jsonb);
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION core.jwt_tenant()
RETURNS text AS $$
    SELECT coalesce(core.jwt_claims()->>'tenant', '');
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION core.jwt_sub()
RETURNS text AS $$
    SELECT coalesce(core.jwt_claims()->>'sub', '');
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION core.has_role(p_role text)
RETURNS boolean AS $$
DECLARE
    roles_val jsonb;
BEGIN
    roles_val := core.jwt_claims()->'roles';
    IF roles_val IS NULL THEN
        RETURN false;
    END IF;
    IF jsonb_typeof(roles_val) = 'array' THEN
        RETURN roles_val ? p_role;
    ELSIF jsonb_typeof(roles_val) = 'string' THEN
        RETURN (roles_val #>> '{}') = p_role;
    END IF;
    RETURN false;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION core.add_business_days(start_ts timestamptz, n integer)
RETURNS timestamptz AS $$
DECLARE
    cur_ts timestamptz := start_ts;
    added integer := 0;
    dow integer;
BEGIN
    IF n <= 0 THEN
        RETURN start_ts;
    END IF;
    WHILE added < n LOOP
        cur_ts := cur_ts + interval '1 day';
        dow := EXTRACT(DOW FROM cur_ts);
        -- 0 = Chủ nhật, 6 = Thứ bảy
        IF dow <> 0 AND dow <> 6 THEN
            added := added + 1;
        END IF;
    END LOOP;
    RETURN cur_ts;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

--------------------------------------------------------------------------------
-- 2. CÁC BẢNG DỮ LIỆU LÕI TẦNG 1 (KHÔNG CHỨA NGHIỆP VỤ)
--------------------------------------------------------------------------------

-- Bảng kiểm toán chuỗi băm bất biến
CREATE TABLE IF NOT EXISTS core.audit_log (
    id bigserial PRIMARY KEY,
    tenant text NOT NULL,
    at timestamptz NOT NULL DEFAULT now(),
    actor_sub text,
    actor_type text NOT NULL DEFAULT 'user', -- user, service, ai, device
    action text NOT NULL,
    object_type text,
    object_id text,
    detail jsonb NOT NULL DEFAULT '{}'::jsonb,
    prev_hash bytea,
    hash bytea NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_id ON core.audit_log (tenant, id);
CREATE INDEX IF NOT EXISTS idx_audit_log_object ON core.audit_log (tenant, object_type, object_id);

-- Bảng niêm phong chuỗi kiểm toán WORM
CREATE TABLE IF NOT EXISTS core.audit_seal (
    id bigserial PRIMARY KEY,
    tenant text NOT NULL,
    sealed_at timestamptz NOT NULL DEFAULT now(),
    last_audit_id bigint NOT NULL,
    head_hash bytea NOT NULL,
    object_key text NOT NULL
);

-- Bảng hàng đợi phát sự kiện Transactional Outbox
CREATE TABLE IF NOT EXISTS core.outbox (
    id bigserial PRIMARY KEY,
    tenant text NOT NULL,
    topic text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON core.outbox (id) WHERE published_at IS NULL;

-- Bảng quản lý tệp tin đính kèm
CREATE TABLE IF NOT EXISTS core.files (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    owner_sub text NOT NULL,
    object_type text,
    object_id text,
    object_key text NOT NULL,
    sha256 text NOT NULL,
    size bigint NOT NULL,
    mime text NOT NULL,
    status text NOT NULL DEFAULT 'clean', -- clean, infected, scan_failed
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_files_tenant ON core.files (tenant);
CREATE INDEX IF NOT EXISTS idx_files_object ON core.files (tenant, object_type, object_id);

-- Bảng quản lý chính sách hợp đồng ứng dụng (V2-08)
CREATE TABLE IF NOT EXISTS core.app_policies (
    id bigserial PRIMARY KEY,
    app_code text NOT NULL,
    policy_type text NOT NULL, -- object_access, flow_policies, doc_signers
    policy_key text NOT NULL,
    policy_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (app_code, policy_type, policy_key)
);

-- Bảng tài liệu đã ký số
CREATE TABLE IF NOT EXISTS core.signed_docs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    doc_type text NOT NULL,
    public_code text NOT NULL UNIQUE,
    object_key text NOT NULL,
    sha256 text NOT NULL,
    signature text NOT NULL,
    key_version text NOT NULL DEFAULT '1',
    status text NOT NULL DEFAULT 'valid', -- valid, revoked
    issued_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    revoke_reason text
);

CREATE INDEX IF NOT EXISTS idx_signed_docs_public_code ON core.signed_docs (public_code);

-- U-01, U-05: người ký thật, thuật toán, và đối tượng nghiệp vụ mà văn bản thuộc về (để kiểm quyền tải bản gốc)
ALTER TABLE core.signed_docs ADD COLUMN IF NOT EXISTS signer_sub text;
ALTER TABLE core.signed_docs ADD COLUMN IF NOT EXISTS algorithm text;
ALTER TABLE core.signed_docs ADD COLUMN IF NOT EXISTS object_type text;
ALTER TABLE core.signed_docs ADD COLUMN IF NOT EXISTS object_id text;

-- Bảng phân công xử lý đối tượng (Access Control)
CREATE TABLE IF NOT EXISTS core.assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    object_type text NOT NULL,
    object_id uuid NOT NULL,
    user_sub text NOT NULL,
    role text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    assigned_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_assignments_lookup ON core.assignments (tenant, object_type, object_id, user_sub) WHERE active = true;

-- Bảng yêu cầu truy cập khẩn cấp (Break-Glass)
CREATE TABLE IF NOT EXISTS core.break_glass (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    requester_sub text NOT NULL,
    object_type text NOT NULL,
    object_id uuid NOT NULL,
    reason text NOT NULL,
    status text NOT NULL DEFAULT 'pending', -- pending, approved, rejected, expired
    approved_by text,
    approved_at timestamptz,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_break_glass_lookup ON core.break_glass (tenant, object_type, object_id, requester_sub, status);

-- Bảng cấu hình hệ thống lõi (core.settings)
CREATE TABLE IF NOT EXISTS core.settings (
    key text PRIMARY KEY,
    value text NOT NULL,
    description text,
    updated_at timestamptz DEFAULT now()
);

-- Bảng quản lý sự đồng ý dữ liệu cá nhân (Consent)
CREATE TABLE IF NOT EXISTS core.consents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    subject_sub text NOT NULL,
    purpose text NOT NULL,
    text_version text NOT NULL DEFAULT '1.0',
    granted_at timestamptz NOT NULL DEFAULT now(),
    withdrawn_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_consents_subject ON core.consents (tenant, subject_sub);

-- Bảng yêu cầu của chủ thể dữ liệu (DSAR)
CREATE TABLE IF NOT EXISTS core.dsar_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    subject_sub text NOT NULL,
    type text NOT NULL, -- access, rectify, erase, restrict, withdraw
    status text NOT NULL DEFAULT 'received', -- received, in_progress, completed, rejected
    received_at timestamptz NOT NULL DEFAULT now(),
    ack_due_at timestamptz NOT NULL,
    due_at timestamptz NOT NULL,
    closed_at timestamptz,
    result jsonb,
    legal_basis_note text
);

CREATE INDEX IF NOT EXISTS idx_dsar_tenant ON core.dsar_requests (tenant, subject_sub);

-- Bảng trạng thái thực thể đô thị (NGSI-LD Entity State)
CREATE TABLE IF NOT EXISTS core.entity_state (
    tenant text NOT NULL,
    entity_id text NOT NULL,
    entity_type text NOT NULL,
    attrs jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant, entity_id)
);

-- Bảng dữ liệu chuỗi thời gian (Timeseries)
CREATE TABLE IF NOT EXISTS core.timeseries (
    tenant text NOT NULL,
    entity_id text NOT NULL,
    metric text NOT NULL,
    ts timestamptz NOT NULL,
    value double precision NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_timeseries_query ON core.timeseries (tenant, entity_id, metric, ts DESC);

-- Bảng phả hệ dữ liệu OpenLineage
CREATE TABLE IF NOT EXISTS core.lineage_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_time timestamptz NOT NULL DEFAULT now(),
    job text NOT NULL,
    run_id text NOT NULL,
    inputs jsonb NOT NULL DEFAULT '[]'::jsonb,
    outputs jsonb NOT NULL DEFAULT '[]'::jsonb,
    facets jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_lineage_job ON core.lineage_events (job, event_time DESC);

-- Bảng thông báo người dùng
CREATE TABLE IF NOT EXISTS core.notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    user_sub text NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    link text,
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON core.notifications (tenant, user_sub, read_at);

-- Bảng tài liệu tri thức RAG (pgvector)
CREATE TABLE IF NOT EXISTS core.knowledge_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    app text NOT NULL,
    source text NOT NULL,
    chunk text NOT NULL,
    embedding vector(1024),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_tenant_app ON core.knowledge_chunks (tenant, app);

-- Bảng lưu vết chạy hook quy trình (N-03)
CREATE TABLE IF NOT EXISTS core.hook_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    process_instance_id text NOT NULL,
    task_def text NOT NULL,
    signed_doc_id uuid,
    public_code text,
    status text NOT NULL, -- PENDING, SIGNED, COMPLETED, FAILED
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hook_runs_proc_task ON core.hook_runs (tenant, process_instance_id, task_def);

-- Bảng thư mục người dùng đồng bộ từ IdP (N-06)
CREATE TABLE IF NOT EXISTS core.users_directory (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant text NOT NULL,
    username text NOT NULL,
    full_name text NOT NULL,
    email text,
    roles text[] NOT NULL DEFAULT '{}',
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant, username)
);

CREATE INDEX IF NOT EXISTS idx_users_directory_tenant ON core.users_directory (tenant, active);

--------------------------------------------------------------------------------
-- 3. HÀM KIỂM TRA PHÂN QUYỀN ĐỐI TƯỢNG (can_access)
--------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION core.can_access(
    p_object_type text,
    p_object_id text,
    p_action text DEFAULT 'read'
)
RETURNS boolean AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_func text;
    v_sql text;
    v_result boolean := false;
    v_uuid uuid;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RETURN false;
    END IF;

    -- 1. Generic object hoặc rỗng: mặc định cho phép trong cùng tenant
    IF p_object_type IS NULL OR p_object_type = 'generic' THEN
        RETURN true;
    END IF;

    -- 2. Quản trị viên nền tảng hoặc dịch vụ hệ thống luôn có quyền
    IF core.has_role('dx:platform-admin') OR core.has_role('dx:service') THEN
        RETURN true;
    END IF;

    -- 3. Tìm hàm delegate từ core.app_policies (V2-08)
    SELECT policy_data->>'function_name' INTO v_func
    FROM core.app_policies
    WHERE policy_type = 'object_access' AND policy_key = p_object_type
    LIMIT 1;

    IF v_func IS NOT NULL THEN
        v_sql := format('SELECT %s($1, $2)', v_func);
        BEGIN
            EXECUTE v_sql INTO v_result USING p_object_id, p_action;
            RETURN coalesce(v_result, false);
        EXCEPTION WHEN OTHERS THEN
            RETURN false;
        END;
    END IF;

    -- 4. Thử ép kiểu UUID để kiểm tra core.assignments và core.break_glass
    BEGIN
        v_uuid := p_object_id::uuid;
    EXCEPTION WHEN OTHERS THEN
        RETURN false;
    END;

    IF EXISTS (
        SELECT 1 FROM core.assignments
        WHERE tenant = cur_tenant
          AND object_type = p_object_type
          AND object_id = v_uuid
          AND (
              user_sub = cur_sub
              OR user_sub = (SELECT username FROM core.users_directory WHERE id::text = cur_sub LIMIT 1)
              OR (SELECT id::text FROM core.users_directory WHERE username = user_sub LIMIT 1) = cur_sub
          )
          AND active = true
    ) THEN
        RETURN true;
    END IF;

    IF EXISTS (
        SELECT 1 FROM core.break_glass
        WHERE tenant = cur_tenant
          AND object_type = p_object_type
          AND object_id = v_uuid
          AND requester_sub = cur_sub
          AND status = 'approved'
          AND expires_at > now()
    ) THEN
        RETURN true;
    END IF;

    RETURN false;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = core, public, pg_temp;

CREATE OR REPLACE FUNCTION core.can_access(p_object_type text, p_object_id uuid)
RETURNS boolean AS $$
BEGIN
    RETURN core.can_access(p_object_type, p_object_id::text, 'read');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = core, public, pg_temp;

GRANT EXECUTE ON FUNCTION core.can_access(text, text, text) TO web_user;
GRANT EXECUTE ON FUNCTION core.can_access(text, uuid) TO web_user;

--------------------------------------------------------------------------------
-- 4. HÀM GHI VÀ BẢO VỆ CHUỖI BĂM KIỂM TOÁN (AUDIT HASH CHAIN)
--------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION core.record_audit(
    p_tenant text,
    p_actor_sub text,
    p_actor_type text,
    p_action text,
    p_object_type text,
    p_object_id text,
    p_detail jsonb
)
RETURNS bigint AS $$
DECLARE
    v_prev_hash bytea;
    v_curr_hash bytea;
    v_data_bytes bytea;
    v_new_id bigint;
BEGIN
    -- Sử dụng advisory lock theo tenant để đảm bảo tính tuần tự tuyệt đối
    PERFORM pg_advisory_xact_lock(hashtext('audit_lock_' || p_tenant));

    -- Lấy mã băm gần nhất của tenant
    SELECT hash INTO v_prev_hash
    FROM core.audit_log
    WHERE tenant = p_tenant
    ORDER BY id DESC
    LIMIT 1;

    IF v_prev_hash IS NULL THEN
        v_prev_hash := '\x0000000000000000000000000000000000000000000000000000000000000000'::bytea;
    END IF;

    -- Chuẩn hóa dữ liệu thành bytea để băm
    v_data_bytes := convert_to(
        p_tenant || '|' ||
        coalesce(p_actor_sub, '') || '|' ||
        p_actor_type || '|' ||
        p_action || '|' ||
        coalesce(p_object_type, '') || '|' ||
        coalesce(p_object_id, '') || '|' ||
        p_detail::text,
        'UTF8'
    );

    v_curr_hash := public.digest(v_prev_hash || v_data_bytes, 'sha256');

    INSERT INTO core.audit_log (
        tenant, actor_sub, actor_type, action, object_type, object_id, detail, prev_hash, hash
    ) VALUES (
        p_tenant, p_actor_sub, p_actor_type, p_action, p_object_type, p_object_id, p_detail, v_prev_hash, v_curr_hash
    ) RETURNING id INTO v_new_id;

    RETURN v_new_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = core, public, pg_temp;

-- Thu hồi quyền sửa/xóa/truncate/insert bảng audit_log và audit_seal đối với mọi vai trò trừ postgres
REVOKE TRUNCATE, UPDATE, DELETE, INSERT ON core.audit_log FROM PUBLIC, anon, web_user, dxos_svc, svc, dxos_owner;
REVOKE TRUNCATE, UPDATE, DELETE ON core.audit_seal FROM PUBLIC, anon, web_user, dxos_svc, svc, dxos_owner;
REVOKE INSERT ON core.audit_seal FROM PUBLIC, anon, web_user, dxos_owner;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON core.signed_docs FROM PUBLIC, anon, web_user;

CREATE OR REPLACE FUNCTION core.trg_audit_log_immutable()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Nhật ký kiểm toán là bất biến (WORM): không được phép sửa hoặc xóa!'
        USING ERRCODE = '42501';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION core.trg_audit_log_no_truncate()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Nhật ký kiểm toán là bất biến (WORM): không được phép TRUNCATE!'
        USING ERRCODE = '42501';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_log_immutable ON core.audit_log;
CREATE TRIGGER trg_audit_log_immutable
    BEFORE UPDATE OR DELETE ON core.audit_log
    FOR EACH ROW EXECUTE FUNCTION core.trg_audit_log_immutable();

DROP TRIGGER IF EXISTS trg_audit_log_no_truncate ON core.audit_log;
CREATE TRIGGER trg_audit_log_no_truncate
    BEFORE TRUNCATE ON core.audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION core.trg_audit_log_no_truncate();

DROP TRIGGER IF EXISTS trg_audit_seal_immutable ON core.audit_seal;
CREATE TRIGGER trg_audit_seal_immutable
    BEFORE UPDATE OR DELETE ON core.audit_seal
    FOR EACH ROW EXECUTE FUNCTION core.trg_audit_log_immutable();

DROP TRIGGER IF EXISTS trg_audit_seal_no_truncate ON core.audit_seal;
CREATE TRIGGER trg_audit_seal_no_truncate
    BEFORE TRUNCATE ON core.audit_seal
    FOR EACH STATEMENT EXECUTE FUNCTION core.trg_audit_log_no_truncate();

--------------------------------------------------------------------------------
-- 5. CHÍNH SÁCH BẢO VỆ MỨC DÒNG (ROW-LEVEL SECURITY - RLS)
--------------------------------------------------------------------------------

ALTER TABLE core.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.audit_log FORCE ROW LEVEL SECURITY;
ALTER TABLE core.outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.outbox FORCE ROW LEVEL SECURITY;
ALTER TABLE core.files ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.files FORCE ROW LEVEL SECURITY;
ALTER TABLE core.signed_docs ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.signed_docs FORCE ROW LEVEL SECURITY;
ALTER TABLE core.assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.assignments FORCE ROW LEVEL SECURITY;
ALTER TABLE core.break_glass ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.audit_seal ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.break_glass FORCE ROW LEVEL SECURITY;
ALTER TABLE core.consents ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.consents FORCE ROW LEVEL SECURITY;
ALTER TABLE core.dsar_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.dsar_requests FORCE ROW LEVEL SECURITY;
ALTER TABLE core.entity_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.entity_state FORCE ROW LEVEL SECURITY;
ALTER TABLE core.timeseries ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.timeseries FORCE ROW LEVEL SECURITY;
ALTER TABLE core.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.notifications FORCE ROW LEVEL SECURITY;
ALTER TABLE core.knowledge_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.knowledge_chunks FORCE ROW LEVEL SECURITY;
ALTER TABLE core.app_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.hook_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.hook_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE core.users_directory ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.users_directory FORCE ROW LEVEL SECURITY;

-- Chính sách cách ly đa thuê ước mặc định cho web_user
DROP POLICY IF EXISTS rls_audit_log_tenant ON core.audit_log;
CREATE POLICY rls_audit_log_tenant ON core.audit_log
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'));

DROP POLICY IF EXISTS rls_outbox_tenant ON core.outbox;
CREATE POLICY rls_outbox_tenant ON core.outbox
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'))
    WITH CHECK (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'));

DROP POLICY IF EXISTS rls_files_tenant ON core.files;
CREATE POLICY rls_files_tenant ON core.files
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'));

DROP POLICY IF EXISTS rls_signed_docs_tenant ON core.signed_docs;
CREATE POLICY rls_signed_docs_tenant ON core.signed_docs
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'));

DROP POLICY IF EXISTS rls_assignments_tenant ON core.assignments;
CREATE POLICY rls_assignments_tenant ON core.assignments
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'));

DROP POLICY IF EXISTS rls_break_glass_tenant ON core.break_glass;
CREATE POLICY rls_break_glass_tenant ON core.break_glass
    FOR ALL TO web_user
    USING (
        tenant = core.jwt_tenant() AND (
            requester_sub = core.jwt_sub()
            OR core.has_role('dx:platform-admin')
            OR core.has_role('dx:tenant-admin')
            OR core.has_role('dx:approver')
            OR EXISTS (
                SELECT 1 FROM core.app_policies ap
                CROSS JOIN LATERAL jsonb_array_elements_text(ap.policy_data->'approver_roles') AS r(role_name)
                WHERE ap.policy_type = 'break_glass'
                  AND core.has_role(r.role_name)
            )
        )
    );

DROP POLICY IF EXISTS rls_consents_tenant ON core.consents;
CREATE POLICY rls_consents_tenant ON core.consents
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND (subject_sub = core.jwt_sub() OR core.has_role('dx:tenant-admin') OR core.has_role('dx:platform-admin')));

DROP POLICY IF EXISTS rls_dsar_requests_tenant ON core.dsar_requests;
CREATE POLICY rls_dsar_requests_tenant ON core.dsar_requests
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND (subject_sub = core.jwt_sub() OR core.has_role('dx:tenant-admin') OR core.has_role('dx:platform-admin')));

DROP POLICY IF EXISTS rls_entity_state_tenant ON core.entity_state;
CREATE POLICY rls_entity_state_tenant ON core.entity_state
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'))
    WITH CHECK (tenant = core.jwt_tenant());

DROP POLICY IF EXISTS rls_timeseries_tenant ON core.timeseries;
CREATE POLICY rls_timeseries_tenant ON core.timeseries
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'))
    WITH CHECK (tenant = core.jwt_tenant());

DROP POLICY IF EXISTS rls_notifications_tenant ON core.notifications;
CREATE POLICY rls_notifications_tenant ON core.notifications
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() AND user_sub = core.jwt_sub());

DROP POLICY IF EXISTS rls_knowledge_chunks_tenant ON core.knowledge_chunks;
CREATE POLICY rls_knowledge_chunks_tenant ON core.knowledge_chunks
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'));

DROP POLICY IF EXISTS rls_hook_runs_tenant ON core.hook_runs;
CREATE POLICY rls_hook_runs_tenant ON core.hook_runs
    FOR ALL TO web_user
    USING (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'))
    WITH CHECK (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'));

DROP POLICY IF EXISTS rls_users_directory_tenant ON core.users_directory;
CREATE POLICY rls_users_directory_tenant ON core.users_directory
    FOR SELECT TO web_user
    USING (tenant = core.jwt_tenant() OR core.has_role('dx:platform-admin'));

DROP POLICY IF EXISTS rls_audit_seal_tenant ON core.audit_seal;
CREATE POLICY rls_audit_seal_tenant ON core.audit_seal
    FOR ALL TO web_user
    USING ((tenant = core.jwt_tenant()) OR core.has_role('dx:platform-admin') OR core.has_role('dx:auditor'))
    WITH CHECK ((tenant = core.jwt_tenant()) OR core.has_role('dx:platform-admin') OR core.has_role('dx:auditor'));

-- Chính sách truy cập cho vai trò dịch vụ nền svc và dxos_svc cùng quản trị ứng dụng dxos_owner
DROP POLICY IF EXISTS rls_core_audit_log_svc ON core.audit_log;
CREATE POLICY rls_core_audit_log_svc ON core.audit_log FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_audit_seal_svc ON core.audit_seal;
CREATE POLICY rls_core_audit_seal_svc ON core.audit_seal FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_outbox_svc ON core.outbox;
CREATE POLICY rls_core_outbox_svc ON core.outbox FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_files_svc ON core.files;
CREATE POLICY rls_core_files_svc ON core.files FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_signed_docs_svc ON core.signed_docs;
CREATE POLICY rls_core_signed_docs_svc ON core.signed_docs FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_assignments_svc ON core.assignments;
CREATE POLICY rls_core_assignments_svc ON core.assignments FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_break_glass_svc ON core.break_glass;
CREATE POLICY rls_core_break_glass_svc ON core.break_glass FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_consents_svc ON core.consents;
CREATE POLICY rls_core_consents_svc ON core.consents FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_dsar_requests_svc ON core.dsar_requests;
CREATE POLICY rls_core_dsar_requests_svc ON core.dsar_requests FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_entity_state_svc ON core.entity_state;
CREATE POLICY rls_core_entity_state_svc ON core.entity_state FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_timeseries_svc ON core.timeseries;
CREATE POLICY rls_core_timeseries_svc ON core.timeseries FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_notifications_svc ON core.notifications;
CREATE POLICY rls_core_notifications_svc ON core.notifications FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_knowledge_chunks_svc ON core.knowledge_chunks;
CREATE POLICY rls_core_knowledge_chunks_svc ON core.knowledge_chunks FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_hook_runs_svc ON core.hook_runs;
CREATE POLICY rls_core_hook_runs_svc ON core.hook_runs FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_users_directory_svc ON core.users_directory;
CREATE POLICY rls_core_users_directory_svc ON core.users_directory FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_app_policies_all ON core.app_policies;
CREATE POLICY rls_app_policies_all ON core.app_policies FOR ALL TO web_user, svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);

ALTER TABLE core.settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.settings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_core_settings_svc ON core.settings;
CREATE POLICY rls_core_settings_svc ON core.settings FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS rls_core_settings_read ON core.settings;
CREATE POLICY rls_core_settings_read ON core.settings FOR SELECT TO web_user USING (true);
GRANT SELECT ON core.settings TO web_user;
GRANT ALL ON core.settings TO svc, dxos_svc, dxos_owner;

INSERT INTO core.settings (key, value, description)
VALUES ('BREAK_GLASS_TTL', 'PT2H', 'Thời hạn hiệu lực truy cập khẩn cấp')
ON CONFLICT (key) DO NOTHING;

-- Cấp quyền SELECT/INSERT cơ bản cho web_user (cấm INSERT trực tiếp core.audit_log - chỉ qua core.record_audit)
GRANT SELECT, INSERT ON core.files TO web_user;
GRANT SELECT ON core.audit_log TO web_user;
GRANT SELECT ON core.audit_seal TO web_user;
GRANT SELECT ON core.app_policies TO web_user;
GRANT EXECUTE ON FUNCTION core.record_audit TO svc, dxos_svc;
GRANT SELECT, INSERT ON core.outbox TO web_user;
GRANT SELECT ON core.signed_docs TO web_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core TO web_user, svc, dxos_svc;
GRANT SELECT ON core.assignments TO web_user;
REVOKE ALL ON core.break_glass FROM web_user;
GRANT SELECT, INSERT, UPDATE ON core.consents TO web_user;
GRANT SELECT, INSERT, UPDATE ON core.dsar_requests TO web_user;
GRANT SELECT, INSERT, UPDATE ON core.entity_state TO web_user;
GRANT SELECT, INSERT ON core.timeseries TO web_user;
GRANT SELECT, UPDATE ON core.notifications TO web_user;
GRANT SELECT ON core.knowledge_chunks TO web_user;
GRANT SELECT ON core.lineage_events TO web_user;
GRANT SELECT, INSERT, UPDATE ON core.hook_runs TO web_user, svc, dxos_svc, dxos_owner;
GRANT SELECT ON core.users_directory TO web_user;
GRANT ALL ON core.users_directory TO svc, dxos_svc, dxos_owner;

-- View break_glass: Thu hồi quyền SELECT khỏi web_user, anon, public để chống lộ dữ liệu (P-01)
CREATE OR REPLACE VIEW core_api.break_glass AS
SELECT id, tenant, requester_sub, object_type, object_id, reason, status, approved_by, approved_at, expires_at, created_at
FROM core.break_glass;

REVOKE ALL ON core_api.break_glass FROM web_user, anon, PUBLIC;

-- Views và RPCs Quản lý Dữ liệu Cá nhân & Quyền Đồng thuận (V2-10, V3-04)
CREATE OR REPLACE VIEW core_api.consents
WITH (security_invoker = true) AS
SELECT id, tenant, subject_sub, purpose, text_version, granted_at, withdrawn_at
FROM core.consents
WHERE tenant = core.jwt_tenant() AND (subject_sub = core.jwt_sub() OR core.has_role('dx:platform-admin'));

REVOKE ALL ON core_api.consents FROM web_user;
GRANT SELECT ON core_api.consents TO web_user;

CREATE OR REPLACE VIEW core_api.dsar_requests
WITH (security_invoker = true) AS
SELECT id, tenant, subject_sub, type, status, received_at, ack_due_at, due_at, closed_at, result, legal_basis_note
FROM core.dsar_requests
WHERE tenant = core.jwt_tenant() AND (
    subject_sub = core.jwt_sub()
    OR core.has_role('dx:dpo')
    OR core.has_role('dx:platform-admin')
    OR core.has_role('dx:tenant-admin')
    OR EXISTS (
        SELECT 1 FROM core.app_policies ap
        CROSS JOIN LATERAL jsonb_array_elements_text(ap.policy_data->'approver_roles') AS r(role_name)
        WHERE ap.policy_type IN ('break_glass', 'dsar_policies') AND core.has_role(r.role_name)
    )
);

REVOKE ALL ON core_api.dsar_requests FROM web_user;
GRANT SELECT ON core_api.dsar_requests TO web_user;

DROP TRIGGER IF EXISTS trg_consents_view_insert ON core_api.consents;
DROP FUNCTION IF EXISTS core_api.trg_consents_insert();
DROP TRIGGER IF EXISTS trg_dsar_requests_view_insert ON core_api.dsar_requests;
DROP FUNCTION IF EXISTS core_api.trg_dsar_requests_insert();

-- RPC Cán bộ xử lý / cập nhật yêu cầu dữ liệu cá nhân (V3-04)
CREATE OR REPLACE FUNCTION core_api.xu_ly_dsar(
    p_request_id uuid,
    p_status text,
    p_result text DEFAULT NULL,
    p_due_at timestamptz DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, core_api, pg_catalog
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_req core.dsar_requests%ROWTYPE;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    IF p_status NOT IN ('in_progress', 'completed', 'rejected', 'closed') THEN
        RAISE EXCEPTION 'Trạng thái DSAR không hợp lệ' USING ERRCODE = '22023';
    END IF;

    IF NOT (
        core.has_role('dx:dpo') OR core.has_role('dx:platform-admin') OR core.has_role('dx:tenant-admin')
        OR EXISTS (
            SELECT 1 FROM core.app_policies ap
            CROSS JOIN LATERAL jsonb_array_elements_text(ap.policy_data->'approver_roles') AS r(role_name)
            WHERE ap.policy_type IN ('break_glass', 'dsar_policies') AND core.has_role(r.role_name)
        )
    ) THEN
        RAISE EXCEPTION 'Bạn không có thẩm quyền xử lý yêu cầu dữ liệu cá nhân' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO v_req FROM core.dsar_requests WHERE id = p_request_id AND tenant = cur_tenant;
    IF v_req.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy yêu cầu DSAR' USING ERRCODE = '42501';
    END IF;

    UPDATE core.dsar_requests
    SET status = p_status,
        result = coalesce(case when p_result is not null then to_jsonb(p_result) else null end, result),
        due_at = coalesce(p_due_at, due_at),
        closed_at = CASE WHEN p_status IN ('closed', 'completed', 'rejected') THEN now() ELSE closed_at END
    WHERE id = p_request_id;

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'dsar.updated', 'dsar_request', p_request_id::text,
        jsonb_build_object('status', p_status, 'result', p_result)
    );

    RETURN jsonb_build_object('status', 'success', 'message', 'Đã cập nhật trạng thái yêu cầu DSAR');
END;
$$;
GRANT EXECUTE ON FUNCTION core_api.xu_ly_dsar(uuid, text, text, timestamptz) TO web_user;

-- RPC Đồng ý dữ liệu
CREATE OR REPLACE FUNCTION core_api.dong_y_du_lieu(
    p_purpose text,
    p_text_version text DEFAULT '1.0'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, core_api, pg_catalog
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_id uuid;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    INSERT INTO core.consents (tenant, subject_sub, purpose, text_version, granted_at, withdrawn_at)
    VALUES (cur_tenant, cur_sub, p_purpose, p_text_version, now(), NULL)
    RETURNING id INTO v_id;

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'consent.granted', 'consent', v_id::text,
        jsonb_build_object('purpose', p_purpose, 'version', p_text_version)
    );

    RETURN jsonb_build_object(
        'status', 'success',
        'id', v_id,
        'message', 'Đã ghi nhận sự đồng thuận sử dụng dữ liệu'
    );
END;
$$;
GRANT EXECUTE ON FUNCTION core_api.dong_y_du_lieu(text, text) TO web_user;

-- RPC Rút đồng ý dữ liệu
CREATE OR REPLACE FUNCTION core_api.rut_dong_y_du_lieu(
    p_purpose text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, core_api, pg_catalog
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_count integer;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    UPDATE core.consents
    SET withdrawn_at = now()
    WHERE tenant = cur_tenant AND subject_sub = cur_sub AND purpose = p_purpose AND withdrawn_at IS NULL;
    GET DIAGNOSTICS v_count = ROW_COUNT;

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'consent.withdrawn', 'consent', p_purpose,
        jsonb_build_object('purpose', p_purpose, 'count', v_count)
    );

    RETURN jsonb_build_object(
        'status', 'success',
        'withdrawn_count', v_count,
        'message', 'Đã rút lại sự đồng thuận dữ liệu'
    );
END;
$$;
GRANT EXECUTE ON FUNCTION core_api.rut_dong_y_du_lieu(text) TO web_user;

-- RPC Gửi yêu cầu dữ liệu cá nhân (DSAR) với hạn tính bằng add_business_days
CREATE OR REPLACE FUNCTION core_api.gui_yeu_cau_dsar(
    p_type text,
    p_legal_basis_note text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, core_api, pg_catalog
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_id uuid;
    v_ack_due timestamptz;
    v_due timestamptz;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    IF p_type NOT IN ('access', 'rectify', 'erase', 'restrict', 'withdraw') THEN
        RAISE EXCEPTION 'Loại yêu cầu DSAR không hợp lệ: %', p_type USING ERRCODE = '22023';
    END IF;

    v_ack_due := core.add_business_days(now(), 2);
    CASE p_type
        WHEN 'access' THEN v_due := core.add_business_days(now(), 10);
        WHEN 'rectify' THEN v_due := core.add_business_days(now(), 10);
        WHEN 'withdraw' THEN v_due := core.add_business_days(now(), 15);
        WHEN 'restrict' THEN v_due := core.add_business_days(now(), 15);
        WHEN 'erase' THEN v_due := core.add_business_days(now(), 20);
        ELSE v_due := core.add_business_days(now(), 10);
    END CASE;

    INSERT INTO core.dsar_requests (
        tenant, subject_sub, type, status, received_at, ack_due_at, due_at, legal_basis_note
    )
    VALUES (
        cur_tenant, cur_sub, p_type, 'received', now(), v_ack_due, v_due, p_legal_basis_note
    )
    RETURNING id INTO v_id;

    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'dsar.requested', 'dsar_request', v_id::text,
        jsonb_build_object('type', p_type, 'due_at', v_due)
    );

    RETURN jsonb_build_object(
        'status', 'success',
        'id', v_id,
        'ack_due_at', v_ack_due,
        'due_at', v_due,
        'message', 'Đã tiếp nhận yêu cầu dữ liệu cá nhân (DSAR)'
    );
END;
$$;
GRANT EXECUTE ON FUNCTION core_api.gui_yeu_cau_dsar(text, text) TO web_user;

-- RPC xin truy cập khẩn cấp (Break-Glass) - chỉ tạo bản ghi pending (V2-09, V3-07, V4-02)
CREATE OR REPLACE FUNCTION core_api.xin_truy_cap_khan(
    p_object_type text,
    p_object_id uuid,
    p_ly_do text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, core_api, pg_catalog
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_id uuid;
    v_valid_type boolean := false;
    v_has_requester_role boolean := false;
    v_obj_exists boolean := false;
    v_tbl text;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    IF p_ly_do IS NULL OR trim(p_ly_do) = '' THEN
        RAISE EXCEPTION 'Lý do xin truy cập khẩn cấp không được để trống' USING ERRCODE = '22023';
    END IF;

    -- 1. Kiểm tra thẩm quyền yêu cầu: chỉ vai cán bộ được khai báo trong break_glass.requester_roles (V4-02)
    IF core.has_role('dx:platform-admin') OR core.has_role('dx:tenant-admin') THEN
        v_has_requester_role := true;
    ELSE
        SELECT EXISTS (
            SELECT 1 FROM core.app_policies ap
            CROSS JOIN LATERAL jsonb_array_elements_text(ap.policy_data->'requester_roles') AS r(role_name)
            WHERE ap.policy_type = 'break_glass'
              AND core.has_role(r.role_name)
        ) INTO v_has_requester_role;
    END IF;

    IF NOT v_has_requester_role THEN
        RAISE EXCEPTION 'Bạn không có quyền yêu cầu truy cập khẩn cấp' USING ERRCODE = '42501';
    END IF;

    -- 2. Kiểm tra object_type có được phép break-glass qua core.app_policies (V3-07)
    SELECT EXISTS (
        SELECT 1 FROM core.app_policies
        WHERE policy_type = 'break_glass'
          AND policy_data->'object_types' ? p_object_type
    ) INTO v_valid_type;

    IF NOT v_valid_type AND NOT core.has_role('dx:platform-admin') THEN
        RAISE EXCEPTION 'Loại đối tượng không hỗ trợ truy cập khẩn cấp' USING ERRCODE = '22023';
    END IF;

    -- 3. Đối tượng phải tồn tại TRONG TENANT của người gọi (V4-02, V3-07)
    FOR v_tbl IN
        SELECT table_schema || '.' || table_name
        FROM information_schema.columns
        WHERE table_schema LIKE 'app_%'
          AND column_name = 'tenant'
          AND table_name = p_object_type
    LOOP
        EXECUTE format('SELECT EXISTS (SELECT 1 FROM %s WHERE id = $1 AND tenant = $2)', v_tbl)
        INTO v_obj_exists
        USING p_object_id, cur_tenant;
        IF NOT v_obj_exists THEN
            RAISE EXCEPTION 'Đối tượng không tồn tại hoặc không thuộc thẩm quyền địa bàn' USING ERRCODE = '42501';
        END IF;
    END LOOP;

    -- Tạo bản ghi với trạng thái PENDING, expires_at tạm thời = now()
    INSERT INTO core.break_glass (
        tenant, requester_sub, object_type, object_id, reason, status, expires_at
    ) VALUES (
        cur_tenant, cur_sub, p_object_type, p_object_id, p_ly_do, 'pending', now()
    ) RETURNING id INTO v_id;

    -- Ghi audit log
    PERFORM core.record_audit(
        cur_tenant, cur_sub, 'user', 'break_glass.requested', p_object_type, p_object_id::text,
        jsonb_build_object('request_id', v_id, 'reason', p_ly_do, 'object_type', p_object_type)
    );

    RETURN jsonb_build_object(
        'status', 'pending',
        'request_id', v_id,
        'message', 'Đã ghi nhận yêu cầu truy cập khẩn cấp, đang chờ lãnh đạo phê duyệt'
    );
END;
$$;

DROP FUNCTION IF EXISTS core_api.xin_truy_cap_khan(uuid, text);
GRANT EXECUTE ON FUNCTION core_api.xin_truy_cap_khan(text, uuid, text) TO web_user;

-- RPC phê duyệt truy cập khẩn cấp (Break-Glass) có TTL cấu hình và kiểm tra SoD (V2-09, V3-07)
CREATE OR REPLACE FUNCTION core_api.duyet_truy_cap_khan(
    p_object_type text,
    p_object_id uuid,
    p_user_sub text,
    p_dong_y boolean DEFAULT true
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, core_api, pg_catalog
AS $$
DECLARE
    cur_tenant text := core.jwt_tenant();
    cur_sub text := core.jwt_sub();
    v_req_id uuid;
    v_ttl_str text;
    v_ttl interval;
    v_has_approver_role boolean := false;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    -- 1. Kiểm tra thẩm quyền phê duyệt: approver_roles khai báo trong app.yaml nạp vào core.app_policies (V3-07)
    IF core.has_role('dx:platform-admin') OR core.has_role('dx:tenant-admin') OR core.has_role('dx:approver') THEN
        v_has_approver_role := true;
    ELSE
        SELECT EXISTS (
            SELECT 1 FROM core.app_policies ap
            CROSS JOIN LATERAL jsonb_array_elements_text(ap.policy_data->'approver_roles') AS r(role_name)
            WHERE ap.policy_type = 'break_glass'
              AND core.has_role(r.role_name)
        ) INTO v_has_approver_role;
    END IF;

    IF NOT v_has_approver_role THEN
        RAISE EXCEPTION 'Bạn không có thẩm quyền phê duyệt truy cập khẩn cấp' USING ERRCODE = '42501';
    END IF;

    -- 2. Kiểm tra SoD: Người xin KHÔNG ĐƯỢC tự duyệt
    IF cur_sub = p_user_sub THEN
        RAISE EXCEPTION 'Vi phạm phân tách nhiệm vụ: Cán bộ không được phép tự phê duyệt yêu cầu truy cập khẩn của chính mình'
            USING ERRCODE = '42501';
    END IF;

    -- 3. TTL đọc từ BREAK_GLASS_TTL qua bảng cấu hình core.settings (V3-07)
    SELECT value INTO v_ttl_str FROM core.settings WHERE key = 'BREAK_GLASS_TTL' LIMIT 1;
    IF v_ttl_str IS NULL OR trim(v_ttl_str) = '' THEN
        v_ttl := interval '2 hours';
    ELSE
        BEGIN
            v_ttl := v_ttl_str::interval;
        EXCEPTION WHEN OTHERS THEN
            v_ttl := interval '2 hours';
        END;
    END IF;

    -- 4. Tìm yêu cầu pending gần nhất của requester đối với đối tượng này
    SELECT id INTO v_req_id
    FROM core.break_glass
    WHERE tenant = cur_tenant
      AND object_type = p_object_type
      AND object_id = p_object_id
      AND requester_sub = p_user_sub
      AND status = 'pending'
    ORDER BY created_at DESC
    LIMIT 1;

    IF v_req_id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy yêu cầu truy cập khẩn cấp đang chờ duyệt của cán bộ này'
            USING ERRCODE = 'PT404';
    END IF;

    IF p_dong_y THEN
        UPDATE core.break_glass
        SET status = 'approved',
            approved_by = cur_sub,
            approved_at = now(),
            expires_at = now() + v_ttl
        WHERE id = v_req_id;

        PERFORM core.record_audit(
            cur_tenant, cur_sub, 'user', 'break_glass.approved', p_object_type, p_object_id::text,
            jsonb_build_object('request_id', v_req_id, 'requester_sub', p_user_sub, 'ttl', v_ttl_str)
        );

        RETURN jsonb_build_object(
            'status', 'approved',
            'request_id', v_req_id,
            'expires_at', (now() + v_ttl),
            'message', 'Đã phê duyệt quyền truy cập khẩn cấp thành công'
        );
    ELSE
        UPDATE core.break_glass
        SET status = 'rejected',
            approved_by = cur_sub,
            approved_at = now(),
            expires_at = now()
        WHERE id = v_req_id;

        PERFORM core.record_audit(
            cur_tenant, cur_sub, 'user', 'break_glass.rejected', p_object_type, p_object_id::text,
            jsonb_build_object('request_id', v_req_id, 'requester_sub', p_user_sub)
        );

        RETURN jsonb_build_object(
            'status', 'rejected',
            'request_id', v_req_id,
            'message', 'Đã từ chối yêu cầu truy cập khẩn cấp'
        );
    END IF;
END;
$$;

DROP FUNCTION IF EXISTS core_api.duyet_truy_cap_khan(uuid, text, boolean);
GRANT EXECUTE ON FUNCTION core_api.duyet_truy_cap_khan(text, uuid, text, boolean) TO web_user;

-- RPC liệt kê yêu cầu truy cập khẩn có phân quyền nghiêm ngặt (P-01)
CREATE OR REPLACE FUNCTION core_api.ds_truy_cap_khan(p_trang_thai text DEFAULT NULL)
RETURNS TABLE(
    id uuid,
    tenant text,
    requester_sub text,
    object_type text,
    object_id uuid,
    reason text,
    status text,
    approved_by text,
    approved_at timestamptz,
    expires_at timestamptz,
    created_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, core_api, public, pg_temp
AS $$
DECLARE
    cur_sub text := core.jwt_sub();
    cur_tenant text := core.jwt_tenant();
    v_is_approver boolean := false;
BEGIN
    IF coalesce(cur_sub, '') = '' OR coalesce(cur_tenant, '') = '' THEN
        RAISE EXCEPTION 'Chưa xác thực danh tính' USING ERRCODE = '42501';
    END IF;

    IF core.has_role('dx:platform-admin') OR core.has_role('dx:tenant-admin') OR core.has_role('dx:approver') THEN
        v_is_approver := true;
    ELSE
        SELECT EXISTS (
            SELECT 1 FROM core.app_policies ap
            CROSS JOIN LATERAL jsonb_array_elements_text(ap.policy_data->'approver_roles') AS r(role_name)
            WHERE ap.policy_type = 'break_glass'
              AND core.has_role(r.role_name)
        ) INTO v_is_approver;
    END IF;

    IF v_is_approver THEN
        RETURN QUERY
        SELECT bg.id, bg.tenant, bg.requester_sub, bg.object_type, bg.object_id, bg.reason, bg.status, bg.approved_by, bg.approved_at, bg.expires_at, bg.created_at
        FROM core.break_glass bg
        WHERE bg.tenant = cur_tenant
          AND (p_trang_thai IS NULL OR bg.status = p_trang_thai)
        ORDER BY bg.created_at DESC;
    ELSE
        RETURN QUERY
        SELECT bg.id, bg.tenant, bg.requester_sub, bg.object_type, bg.object_id, bg.reason, bg.status, bg.approved_by, bg.approved_at, bg.expires_at, bg.created_at
        FROM core.break_glass bg
        WHERE bg.tenant = cur_tenant
          AND bg.requester_sub = cur_sub
          AND (p_trang_thai IS NULL OR bg.status = p_trang_thai)
        ORDER BY bg.created_at DESC;
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION core_api.ds_truy_cap_khan(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION core_api.ds_truy_cap_khan(text) TO web_user;

-- Cấp quyền tối thiểu theo nhu cầu cho vai trò dịch vụ nền dxos_svc, svc và quản trị ứng dụng dxos_owner (Z-01)
GRANT USAGE ON SCHEMA core, core_api TO dxos_svc, svc, dxos_owner;
GRANT SELECT, INSERT, UPDATE, DELETE ON 
    core.consents, core.dsar_requests, core.files, core.outbox, core.settings, 
    core.assignments, core.break_glass, core.app_policies, 
    core.entity_state, core.timeseries, core.knowledge_chunks, core.lineage_events, core.notifications
TO dxos_svc, svc, dxos_owner;

GRANT SELECT, INSERT, UPDATE ON core.signed_docs TO dxos_svc, svc, dxos_owner;
GRANT SELECT, INSERT ON core.audit_seal TO dxos_svc, svc;
GRANT SELECT ON core.audit_seal TO dxos_owner;
GRANT SELECT ON core.audit_log TO dxos_svc, svc, dxos_owner, web_user;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA core_api TO dxos_svc, svc, dxos_owner;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA core, core_api TO dxos_svc, svc, dxos_owner;
GRANT ALL PRIVILEGES ON ALL ROUTINES IN SCHEMA core, core_api TO dxos_svc, svc, dxos_owner;

-- Đảm bảo bất biến WORM tuyệt đối cho core.audit_log và core.audit_seal (Z-01)
REVOKE TRUNCATE, UPDATE, DELETE, INSERT ON core.audit_log FROM PUBLIC, anon, web_user, dxos_svc, svc, dxos_owner;
REVOKE TRUNCATE, UPDATE, DELETE ON core.audit_seal FROM PUBLIC, anon, web_user, dxos_svc, svc, dxos_owner;
REVOKE INSERT ON core.audit_seal FROM PUBLIC, anon, web_user, dxos_owner;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON core.signed_docs FROM PUBLIC, anon, web_user;

-- Thu hồi quyền gọi core.record_audit từ web_user, chỉ cấp cho dxos_svc và svc
REVOKE EXECUTE ON FUNCTION core.record_audit(text, text, text, text, text, text, jsonb) FROM PUBLIC, anon, web_user;
GRANT EXECUTE ON FUNCTION core.record_audit(text, text, text, text, text, text, jsonb) TO dxos_svc, svc;

-- Thu hồi quyền mặc định của anon và PUBLIC trong schema core và core_api (Z-14)
ALTER DEFAULT PRIVILEGES IN SCHEMA core REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA core_api REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA core, core_api FROM PUBLIC, anon;

-- Cấp lại quyền EXECUTE có chọn lọc cho web_user đối với các hàm RPC trong core và core_api
GRANT EXECUTE ON FUNCTION core.jwt_claims() TO web_user;
GRANT EXECUTE ON FUNCTION core.jwt_tenant() TO web_user;
GRANT EXECUTE ON FUNCTION core.jwt_sub() TO web_user;
GRANT EXECUTE ON FUNCTION core.has_role(text) TO web_user;
GRANT EXECUTE ON FUNCTION core.can_access(text, text, text) TO web_user;
GRANT EXECUTE ON FUNCTION core.can_access(text, uuid) TO web_user;

GRANT EXECUTE ON FUNCTION core_api.xin_truy_cap_khan(text, uuid, text) TO web_user;
GRANT EXECUTE ON FUNCTION core_api.duyet_truy_cap_khan(text, uuid, text, boolean) TO web_user;
GRANT EXECUTE ON FUNCTION core_api.xu_ly_dsar(uuid, text, text, timestamptz) TO web_user;
GRANT EXECUTE ON FUNCTION core_api.dong_y_du_lieu(text, text) TO web_user;
GRANT EXECUTE ON FUNCTION core_api.rut_dong_y_du_lieu(text) TO web_user;
GRANT EXECUTE ON FUNCTION core_api.gui_yeu_cau_dsar(text, text) TO web_user;
GRANT EXECUTE ON FUNCTION core_api.ds_truy_cap_khan(text) TO web_user;


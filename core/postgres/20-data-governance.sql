-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 20-data-governance.sql — danh mục tài sản dữ liệu, chủ sở hữu, phân loại (D-GOV-01, D-GOV-02).
-- Danh mục là dữ liệu cấp nền tảng, không chứa dữ liệu cá nhân. Lõi khai báo tài sản lõi;
-- gói ứng dụng khai báo tài sản của mình trong migration riêng. Ghi danh mục chỉ qua migration
-- (web_user chỉ đọc). Idempotent.

-- Vai có quyền đọc danh mục và dữ liệu quản trị (dùng cho RLS các bảng D)
CREATE OR REPLACE FUNCTION core.dh_co_vai(p_vai text[])
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
    SELECT core.has_role('dx:platform-admin')
        OR EXISTS (SELECT 1 FROM unnest(p_vai) v WHERE core.has_role(v));
$$;
GRANT EXECUTE ON FUNCTION core.dh_co_vai(text[]) TO web_user, svc, dxos_svc;

CREATE TABLE IF NOT EXISTS core.data_owners (
    domain text PRIMARY KEY,
    ten text NOT NULL,
    owner text NOT NULL,
    steward text,
    mo_ta text,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.data_assets (
    asset text PRIMARY KEY,
    domain text NOT NULL REFERENCES core.data_owners(domain),
    description text NOT NULL,
    owner text NOT NULL,
    steward text,
    classification text NOT NULL,
    retention text,
    freshness_sla text,
    version text NOT NULL DEFAULT '1',
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_data_assets_asset CHECK (asset ~ '^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$'),
    CONSTRAINT chk_data_assets_class CHECK (classification IN ('public', 'internal', 'pii', 'sensitive'))
);

CREATE TABLE IF NOT EXISTS core.data_asset_columns (
    asset text NOT NULL REFERENCES core.data_assets(asset) ON DELETE CASCADE,
    name text NOT NULL,
    classification text NOT NULL,
    description text,
    masked_in_api boolean NOT NULL DEFAULT false,
    PRIMARY KEY (asset, name),
    CONSTRAINT chk_data_asset_columns_class CHECK (classification IN ('public', 'internal', 'pii', 'sensitive'))
);

CREATE INDEX IF NOT EXISTS idx_data_assets_domain ON core.data_assets (domain, asset);

-- Đọc: kiểm toán, quản trị phường, người quản lý dữ liệu, quản trị nền tảng
DO $$
DECLARE
    v_bang text;
BEGIN
    FOREACH v_bang IN ARRAY ARRAY['data_owners', 'data_assets', 'data_asset_columns'] LOOP
        EXECUTE format('ALTER TABLE core.%I ENABLE ROW LEVEL SECURITY', v_bang);
        EXECUTE format('ALTER TABLE core.%I FORCE ROW LEVEL SECURITY', v_bang);
        EXECUTE format('DROP POLICY IF EXISTS rls_%s_read ON core.%I', v_bang, v_bang);
        EXECUTE format(
            'CREATE POLICY rls_%s_read ON core.%I FOR SELECT TO web_user '
            'USING (core.dh_co_vai(ARRAY[''dx:auditor'', ''dx:tenant-admin'', ''dx:data-steward'']))',
            v_bang, v_bang);
        EXECUTE format('DROP POLICY IF EXISTS rls_%s_svc ON core.%I', v_bang, v_bang);
        EXECUTE format(
            'CREATE POLICY rls_%s_svc ON core.%I FOR ALL TO svc, dxos_svc, dxos_owner USING (true) WITH CHECK (true)',
            v_bang, v_bang);
        EXECUTE format('GRANT SELECT ON core.%I TO web_user', v_bang);
        EXECUTE format('GRANT ALL ON core.%I TO svc, dxos_svc, dxos_owner', v_bang);
    END LOOP;
END $$;

-- 9 miền dữ liệu (D-GOV-01) và đơn vị chủ quản
INSERT INTO core.data_owners (domain, ten, owner, steward, mo_ta) VALUES
    ('cong_dan', 'Công dân, tổ chức', 'Bộ phận một cửa', 'dx:data-steward', 'Người nộp, chủ đầu tư; định danh chỉ lưu dạng HMAC'),
    ('thua_dat', 'Thửa đất, địa điểm', 'Bộ phận thẩm định', 'dx:data-steward', 'Thửa đất, mã định danh địa điểm'),
    ('ho_so', 'Hồ sơ thủ tục', 'Bộ phận một cửa', 'dx:data-steward', 'Hồ sơ, lịch sử xử lý'),
    ('giay_phep', 'Giấy phép', 'Lãnh đạo phường', 'dx:data-steward', 'Giấy phép đã cấp, văn bản ký số'),
    ('cong_trinh', 'Công trình', 'Bộ phận trật tự xây dựng', 'dx:data-steward', 'Công trình, thi công'),
    ('giay_to', 'Giấy tờ, tệp', 'Bộ phận một cửa', 'dx:data-steward', 'Tệp đính kèm, văn bản ký'),
    ('kiem_tra', 'Kiểm tra, nghiệm thu', 'Bộ phận thẩm định', 'dx:data-steward', 'Kiểm tra quy hoạch, nghiệm thu, hiện trường'),
    ('tai_chinh', 'Phí, lệ phí', 'Bộ phận một cửa', 'dx:data-steward', 'Biểu phí, biên lai'),
    ('audit', 'Kiểm toán, phả hệ', 'Quản trị nền tảng', 'dx:auditor', 'Nhật ký kiểm toán, phả hệ dữ liệu')
ON CONFLICT (domain) DO UPDATE
SET ten = EXCLUDED.ten, owner = EXCLUDED.owner, steward = EXCLUDED.steward, mo_ta = EXCLUDED.mo_ta, updated_at = now();

-- Tài sản lõi
INSERT INTO core.data_assets (asset, domain, description, owner, steward, classification, retention, freshness_sla) VALUES
    ('core.audit_log', 'audit', 'Nhật ký kiểm toán chuỗi băm, chỉ ghi thêm', 'Quản trị nền tảng', 'dx:auditor', 'sensitive', 'vinh_vien', 'realtime'),
    ('core.lineage_events', 'audit', 'Sự kiện phả hệ dữ liệu (OpenLineage tối giản)', 'Quản trị nền tảng', 'dx:data-steward', 'internal', '5_nam', 'realtime'),
    ('core.signed_docs', 'giay_to', 'Văn bản đã ký số và mã tra cứu công khai', 'Lãnh đạo phường', 'dx:data-steward', 'internal', 'vinh_vien', 'realtime'),
    ('core.files', 'giay_to', 'Tệp tải lên, kết quả quét virus', 'Bộ phận một cửa', 'dx:data-steward', 'pii', '10_nam', 'realtime'),
    ('core.users_directory', 'cong_dan', 'Danh bạ người dùng đồng bộ từ Keycloak', 'Quản trị nền tảng', 'dx:tenant-admin', 'pii', 'khi_con_tai_khoan', '1h'),
    ('core.notifications', 'audit', 'Thông báo cho người dùng', 'Quản trị nền tảng', NULL, 'internal', '1_nam', 'realtime')
ON CONFLICT (asset) DO UPDATE
SET domain = EXCLUDED.domain, description = EXCLUDED.description, owner = EXCLUDED.owner,
    steward = EXCLUDED.steward, classification = EXCLUDED.classification, retention = EXCLUDED.retention,
    freshness_sla = EXCLUDED.freshness_sla, updated_at = now();

INSERT INTO core.data_asset_columns (asset, name, classification, description, masked_in_api) VALUES
    ('core.audit_log', 'actor_sub', 'pii', 'Định danh người thực hiện', false),
    ('core.audit_log', 'detail', 'sensitive', 'Chi tiết sự kiện, không chứa CCCD', false),
    ('core.files', 'owner_sub', 'pii', 'Định danh người tải lên', false),
    ('core.users_directory', 'email', 'pii', 'Thư điện tử', true),
    ('core.users_directory', 'full_name', 'pii', 'Họ tên', false)
ON CONFLICT (asset, name) DO UPDATE
SET classification = EXCLUDED.classification, description = EXCLUDED.description, masked_in_api = EXCLUDED.masked_in_api;

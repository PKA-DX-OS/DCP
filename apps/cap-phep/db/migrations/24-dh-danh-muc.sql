-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 24-dh-danh-muc.sql — gói cấp phép khai báo tài sản dữ liệu của mình vào danh mục lõi
-- (D-GOV-01, D-GOV-02, D-CAT-01): mô tả, chủ quản, phân loại, thời hạn lưu trữ, cột cá nhân.
-- Chạy sau core/postgres/20-data-governance.sql và 23-catalog-lineage.sql; lõi chưa có danh mục
-- thì bỏ qua. Idempotent.

DO $$
BEGIN
    IF to_regclass('core.data_assets') IS NULL THEN
        RAISE NOTICE 'Chưa có core.data_assets, bỏ qua khai báo danh mục';
        RETURN;
    END IF;

    INSERT INTO core.data_assets (asset, domain, description, owner, steward, classification, retention, freshness_sla) VALUES
        ('app_cap_phep.ho_so', 'ho_so', 'Hồ sơ đề nghị cấp giấy phép xây dựng nhà ở riêng lẻ', 'Bộ phận một cửa', 'dx:data-steward', 'pii', 'vinh_vien', 'realtime'),
        ('app_cap_phep.ho_so_lich_su', 'ho_so', 'Ảnh chụp hồ sơ sau mỗi lần thay đổi', 'Bộ phận một cửa', 'dx:data-steward', 'pii', 'vinh_vien', 'realtime'),
        ('app_cap_phep.ho_so_tep', 'giay_to', 'Tệp giấy tờ gắn với hồ sơ', 'Bộ phận một cửa', 'dx:data-steward', 'pii', 'vinh_vien', 'realtime'),
        ('app_cap_phep.giay_phep', 'giay_phep', 'Giấy phép đã cấp, số giấy phép, quy mô được cấp', 'Lãnh đạo phường', 'dx:data-steward', 'internal', 'vinh_vien', 'realtime'),
        ('app_cap_phep.cong_trinh', 'cong_trinh', 'Công trình được cấp phép, trạng thái thi công', 'Bộ phận trật tự xây dựng', 'dx:data-steward', 'internal', 'vinh_vien', 'realtime'),
        ('app_cap_phep.phieu_kiem_tra', 'kiem_tra', 'Phiếu kiểm tra hiện trường (hậu kiểm)', 'Bộ phận trật tự xây dựng', 'dx:data-steward', 'internal', '10_nam', 'realtime'),
        ('app_construction.ket_qua_kiem_tra_quy_hoach', 'kiem_tra', 'Kết quả kiểm tra quy hoạch theo hồ sơ', 'Bộ phận thẩm định', 'dx:data-steward', 'internal', 'vinh_vien', 'realtime'),
        ('app_construction.moc_nghiem_thu', 'kiem_tra', 'Mốc nghiệm thu móng, kết cấu, hoàn thiện, hoàn công', 'Bộ phận thẩm định', 'dx:data-steward', 'internal', 'vinh_vien', 'realtime'),
        ('app_construction.thua_dat', 'thua_dat', 'Thửa đất phục vụ kiểm tra quy hoạch', 'Bộ phận thẩm định', 'dx:data-steward', 'internal', 'vinh_vien', '1d'),
        ('app_construction.bien_lai_phi', 'tai_chinh', 'Biên lai phí, lệ phí cấp phép', 'Bộ phận một cửa', 'dx:data-steward', 'pii', '10_nam', 'realtime')
    ON CONFLICT (asset) DO UPDATE
    SET domain = EXCLUDED.domain, description = EXCLUDED.description, owner = EXCLUDED.owner,
        steward = EXCLUDED.steward, classification = EXCLUDED.classification, retention = EXCLUDED.retention,
        freshness_sla = EXCLUDED.freshness_sla, updated_at = now();

    -- Cột cá nhân (D-GOV-02): CCCD và điện thoại chỉ trả dạng che qua API
    INSERT INTO core.data_asset_columns (asset, name, classification, description, masked_in_api) VALUES
        ('app_cap_phep.ho_so', 'cccd', 'sensitive', 'Số CCCD người nộp; API chỉ trả dạng che, tìm bằng HMAC', true),
        ('app_cap_phep.ho_so', 'ho_ten', 'pii', 'Họ tên người nộp', false),
        ('app_cap_phep.ho_so', 'dien_thoai', 'pii', 'Số điện thoại người nộp', true),
        ('app_cap_phep.ho_so', 'dia_chi_cong_trinh', 'pii', 'Địa chỉ công trình', false),
        ('app_cap_phep.ho_so', 'thua_dat', 'internal', 'Số thửa, tờ bản đồ', false),
        ('app_cap_phep.ho_so', 'ma_dinh_danh_dia_diem', 'internal', 'Mã định danh địa điểm 12 chữ số', false),
        ('app_cap_phep.ho_so_lich_su', 'snapshot', 'pii', 'Ảnh chụp đầy đủ hồ sơ', true),
        ('app_cap_phep.giay_phep', 'so_giay_phep', 'public', 'Số giấy phép in trên văn bản', false),
        ('app_cap_phep.cong_trinh', 'dia_chi', 'pii', 'Địa chỉ công trình', false)
    ON CONFLICT (asset, name) DO UPDATE
    SET classification = EXCLUDED.classification, description = EXCLUDED.description, masked_in_api = EXCLUDED.masked_in_api;

    IF to_regclass('core.data_contracts') IS NOT NULL THEN
        INSERT INTO core.data_contracts (asset, version, json_schema, sla, consumers) VALUES
        ('app_cap_phep.ho_so', '1',
         '{"type": "object", "required": ["id", "tenant", "ma_ho_so", "trang_thai", "created_at"],
           "properties": {"id": {"type": "string", "format": "uuid"}, "tenant": {"type": "string"},
                          "ma_ho_so": {"type": "string"}, "trang_thai": {"type": "string"},
                          "so_tang": {"type": "integer", "minimum": 1}, "dien_tich_san_m2": {"type": "number", "exclusiveMinimum": 0},
                          "ma_dinh_danh_dia_diem": {"type": ["string", "null"], "pattern": "^[0-9]{12}$"},
                          "created_at": {"type": "string", "format": "date-time"}}}'::jsonb,
         '{"freshness": "realtime", "availability_pct": 99.5}'::jsonb,
         ARRAY['cap-phep web', 'construction /api/v1/mdm', 'metrics-api']),
        ('app_cap_phep.giay_phep', '1',
         '{"type": "object", "required": ["id", "tenant", "ho_so_id", "so_giay_phep", "signed_doc_id", "trang_thai", "ngay_cap"],
           "properties": {"id": {"type": "string", "format": "uuid"}, "so_giay_phep": {"type": "string"},
                          "trang_thai": {"type": "string"}, "ngay_cap": {"type": "string", "format": "date-time"},
                          "so_tang": {"type": ["integer", "null"]}, "dien_tich_san_m2": {"type": ["number", "null"]}}}'::jsonb,
         '{"freshness": "realtime", "availability_pct": 99.5}'::jsonb,
         ARRAY['doc-sign', 'construction /api/v1/mdm', 'metrics-api'])
        ON CONFLICT (asset, version) DO UPDATE
        SET json_schema = EXCLUDED.json_schema, sla = EXCLUDED.sla, consumers = EXCLUDED.consumers;
    END IF;
END $$;

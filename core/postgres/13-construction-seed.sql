-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 13-construction-seed.sql — dữ liệu tổng hợp phục vụ demo Track A.
-- Dữ liệu quy hoạch là dữ liệu tổng hợp, KHÔNG phải dữ liệu quy hoạch thật.
-- Idempotent: ON CONFLICT DO UPDATE theo khóa nghiệp vụ.

--------------------------------------------------------------------------------
-- 1. Thửa đất và vùng quy hoạch (phuong-a)
--------------------------------------------------------------------------------
INSERT INTO app_construction.quy_hoach_zone
    (id, tenant, ma_zone, ten, loai_zone, mo_ta, dien_tich_ha, geom, status, created_by)
VALUES
    ('11111111-1111-4111-8111-111111111111', 'phuong-a', 'QH-A1', 'Ô đô thị trung tâm phường A',
     'o_do_thi', 'Dữ liệu tổng hợp phục vụ demo, không phải quy hoạch thật.', 12.5,
     '{"type":"Polygon","coordinates":[[[106.7000,10.7700],[106.7060,10.7700],[106.7060,10.7760],[106.7000,10.7760],[106.7000,10.7700]]]}'::jsonb,
     'hieu_luc', 'seed')
ON CONFLICT (tenant, ma_zone) DO UPDATE
SET ten = EXCLUDED.ten, loai_zone = EXCLUDED.loai_zone, geom = EXCLUDED.geom,
    dien_tich_ha = EXCLUDED.dien_tich_ha, updated_at = now();

INSERT INTO app_construction.quy_hoach_zone
    (id, tenant, ma_zone, ten, loai_zone, mo_ta, dien_tich_ha, geom, status, created_by)
VALUES
    ('11111111-1111-4111-8111-222222222222', 'phuong-a', 'QH-A2', 'Hành lang giao thông phường A',
     'hanh_lang_giao_thong', 'Dữ liệu tổng hợp phục vụ demo, không phải quy hoạch thật.', 3.2,
     '{"type":"Polygon","coordinates":[[[106.7060,10.7700],[106.7100,10.7700],[106.7100,10.7760],[106.7060,10.7760],[106.7060,10.7700]]]}'::jsonb,
     'hieu_luc', 'seed')
ON CONFLICT (tenant, ma_zone) DO UPDATE
SET ten = EXCLUDED.ten, loai_zone = EXCLUDED.loai_zone, geom = EXCLUDED.geom,
    dien_tich_ha = EXCLUDED.dien_tich_ha, updated_at = now();

INSERT INTO app_construction.thua_dat
    (tenant, ma_thua_dat, so_thua, to_ban_do, dia_chi, dien_tich_m2, loai_dat,
     ma_dinh_danh_dia_diem, geom, status, created_by)
VALUES
    ('phuong-a', 'TD-A-01', '12', 'Tờ 34', 'Số 18 Đường Hòa Bình, phường A', 180.0, 'dat_o',
     '790101000001', '{"type":"Point","coordinates":[106.7025,10.7725]}'::jsonb, 'hieu_luc', 'seed'),
    ('phuong-a', 'TD-A-02', '13', 'Tờ 34', 'Số 20 Đường Hòa Bình, phường A', 420.0, 'dat_o',
     '790101000002', '{"type":"Point","coordinates":[106.7045,10.7745]}'::jsonb, 'hieu_luc', 'seed'),
    ('phuong-a', 'TD-A-03', '21', 'Tờ 35', 'Số 02 Đường Vành đai, phường A', 120.0, 'dat_o',
     '790101000003', '{"type":"Point","coordinates":[106.7080,10.7725]}'::jsonb, 'hieu_luc', 'seed')
ON CONFLICT (tenant, ma_thua_dat) DO UPDATE
SET so_thua = EXCLUDED.so_thua, to_ban_do = EXCLUDED.to_ban_do, dia_chi = EXCLUDED.dia_chi,
    dien_tich_m2 = EXCLUDED.dien_tich_m2, loai_dat = EXCLUDED.loai_dat,
    ma_dinh_danh_dia_diem = EXCLUDED.ma_dinh_danh_dia_diem, geom = EXCLUDED.geom,
    updated_at = now();

INSERT INTO app_construction.quy_hoach_van_ban
    (tenant, ma_van_ban, ten, co_quan_ban_hanh, ngay_ban_hanh, ngay_hieu_luc,
     status, created_by)
VALUES
    ('phuong-a', 'QH-A-2026-01', 'Đồ án quy hoạch phân khu phường A (dữ liệu tổng hợp)',
     'UBND phường A (dữ liệu demo)', '2026-01-15', '2026-02-01', 'hieu_luc', 'seed'),
    ('phuong-a', 'QH-A-2026-02', 'Điều chỉnh cục bộ đồ án quy hoạch phường A (dữ liệu tổng hợp)',
     'UBND phường A (dữ liệu demo)', '2026-06-10', '2026-07-01', 'hieu_luc', 'seed')
ON CONFLICT (tenant, ma_van_ban) DO UPDATE
SET ten = EXCLUDED.ten, co_quan_ban_hanh = EXCLUDED.co_quan_ban_hanh,
    ngay_ban_hanh = EXCLUDED.ngay_ban_hanh, ngay_hieu_luc = EXCLUDED.ngay_hieu_luc,
    updated_at = now();

-- Chỉ tiêu vùng QH-A1
WITH z AS (
    SELECT id FROM app_construction.quy_hoach_zone
    WHERE tenant = 'phuong-a' AND ma_zone = 'QH-A1'
)
INSERT INTO app_construction.chi_tieu_quy_hoach
    (tenant, zone_id, chi_tieu, ten, gia_tri_min, gia_tri_max, don_vi, bat_buoc, legal_citation_key, created_by)
SELECT 'phuong-a', z.id, v.chi_tieu, v.ten, v.gia_tri_min, v.gia_tri_max, v.don_vi, true, v.citation, 'seed'
FROM z, (VALUES
    ('max_height_m', 'Chiều cao tối đa', NULL::double precision, 12.0::double precision, 'm', 'LQH47-TOANVAN'),
    ('max_floors', 'Số tầng tối đa', NULL::double precision, 3.0::double precision, 'tầng', 'LQH47-TOANVAN'),
    ('max_density_pct', 'Mật độ xây dựng tối đa', NULL::double precision, 70.0::double precision, '%', 'LQH47-TOANVAN'),
    ('max_far', 'Hệ số sử dụng đất tối đa', NULL::double precision, 2.0::double precision, 'lần', 'LQH47-TOANVAN'),
    ('setback_front_m', 'Khoảng lùi trước tối thiểu', 3.0::double precision, NULL::double precision, 'm', 'LQH47-TOANVAN'),
    ('setback_side_m', 'Khoảng lùi hông tối thiểu', 1.0::double precision, NULL::double precision, 'm', 'LQH47-TOANVAN'),
    ('setback_back_m', 'Khoảng lùi sau tối thiểu', 1.0::double precision, NULL::double precision, 'm', 'LQH47-TOANVAN'),
    ('land_use', 'Mục đích sử dụng đất được phép', NULL::double precision, NULL::double precision, 'dat_o', 'LQH47-TOANVAN')
) AS v(chi_tieu, ten, gia_tri_min, gia_tri_max, don_vi, citation)
ON CONFLICT (tenant, zone_id, chi_tieu) DO UPDATE
SET ten = EXCLUDED.ten, gia_tri_min = EXCLUDED.gia_tri_min, gia_tri_max = EXCLUDED.gia_tri_max,
    don_vi = EXCLUDED.don_vi, legal_citation_key = EXCLUDED.legal_citation_key, updated_at = now();

--------------------------------------------------------------------------------
-- 2. Dữ liệu tối thiểu cho phuong-b (kiểm thử cách ly địa bàn)
--------------------------------------------------------------------------------
INSERT INTO app_construction.quy_hoach_zone
    (id, tenant, ma_zone, ten, loai_zone, mo_ta, dien_tich_ha, geom, status, created_by)
VALUES
    ('22222222-2222-4222-8222-111111111111', 'phuong-b', 'QH-B1', 'Ô đô thị trung tâm phường B',
     'o_do_thi', 'Dữ liệu tổng hợp phục vụ demo, không phải quy hoạch thật.', 8.0,
     '{"type":"Polygon","coordinates":[[[106.7200,10.7800],[106.7260,10.7800],[106.7260,10.7860],[106.7200,10.7860],[106.7200,10.7800]]]}'::jsonb,
     'hieu_luc', 'seed')
ON CONFLICT (tenant, ma_zone) DO UPDATE
SET ten = EXCLUDED.ten, geom = EXCLUDED.geom, updated_at = now();

INSERT INTO app_construction.thua_dat
    (tenant, ma_thua_dat, so_thua, to_ban_do, dia_chi, dien_tich_m2, loai_dat,
     ma_dinh_danh_dia_diem, geom, status, created_by)
VALUES
    ('phuong-b', 'TD-B-01', '05', 'Tờ 12', 'Số 09 Đường Bình Minh, phường B', 210.0, 'dat_o',
     '790102000001', '{"type":"Point","coordinates":[106.7230,10.7830]}'::jsonb, 'hieu_luc', 'seed')
ON CONFLICT (tenant, ma_thua_dat) DO UPDATE
SET dia_chi = EXCLUDED.dia_chi, geom = EXCLUDED.geom, updated_at = now();

WITH z AS (
    SELECT id FROM app_construction.quy_hoach_zone
    WHERE tenant = 'phuong-b' AND ma_zone = 'QH-B1'
)
INSERT INTO app_construction.chi_tieu_quy_hoach
    (tenant, zone_id, chi_tieu, ten, gia_tri_min, gia_tri_max, don_vi, bat_buoc, legal_citation_key, created_by)
SELECT 'phuong-b', z.id, v.chi_tieu, v.ten, v.gia_tri_min, v.gia_tri_max, v.don_vi, true, v.citation, 'seed'
FROM z, (VALUES
    ('max_height_m', 'Chiều cao tối đa', NULL::double precision, 10.0::double precision, 'm', 'LQH47-TOANVAN'),
    ('max_floors', 'Số tầng tối đa', NULL::double precision, 3.0::double precision, 'tầng', 'LQH47-TOANVAN'),
    ('max_density_pct', 'Mật độ xây dựng tối đa', NULL::double precision, 65.0::double precision, '%', 'LQH47-TOANVAN'),
    ('max_far', 'Hệ số sử dụng đất tối đa', NULL::double precision, 1.8::double precision, 'lần', 'LQH47-TOANVAN'),
    ('setback_front_m', 'Khoảng lùi trước tối thiểu', 2.5::double precision, NULL::double precision, 'm', 'LQH47-TOANVAN'),
    ('setback_side_m', 'Khoảng lùi hông tối thiểu', 1.0::double precision, NULL::double precision, 'm', 'LQH47-TOANVAN'),
    ('setback_back_m', 'Khoảng lùi sau tối thiểu', 1.0::double precision, NULL::double precision, 'm', 'LQH47-TOANVAN'),
    ('land_use', 'Mục đích sử dụng đất được phép', NULL::double precision, NULL::double precision, 'dat_o', 'LQH47-TOANVAN')
) AS v(chi_tieu, ten, gia_tri_min, gia_tri_max, don_vi, citation)
ON CONFLICT (tenant, zone_id, chi_tieu) DO UPDATE
SET ten = EXCLUDED.ten, gia_tri_min = EXCLUDED.gia_tri_min, gia_tri_max = EXCLUDED.gia_tri_max,
    don_vi = EXCLUDED.don_vi, legal_citation_key = EXCLUDED.legal_citation_key, updated_at = now();

--------------------------------------------------------------------------------
-- 3. Danh mục định danh địa điểm tổng hợp (A-LEGAL-05)
--------------------------------------------------------------------------------
INSERT INTO app_construction.dia_diem_dinh_danh
    (ma_dinh_danh_dia_diem, tenant, dia_chi, so_thua, to_ban_do, dien_tich_m2, loai_dat,
     nguon, da_kiem_chung)
VALUES
    ('790101000001', 'phuong-a', 'Số 18 Đường Hòa Bình, phường A', '12', 'Tờ 34', 180.0, 'dat_o', 'demo_tong_hop', false),
    ('790101000002', 'phuong-a', 'Số 20 Đường Hòa Bình, phường A', '13', 'Tờ 34', 420.0, 'dat_o', 'demo_tong_hop', false),
    ('790101000003', 'phuong-a', 'Số 02 Đường Vành đai, phường A', '21', 'Tờ 35', 120.0, 'dat_o', 'demo_tong_hop', false),
    ('790102000001', 'phuong-b', 'Số 09 Đường Bình Minh, phường B', '05', 'Tờ 12', 210.0, 'dat_o', 'demo_tong_hop', false)
ON CONFLICT (ma_dinh_danh_dia_diem) DO UPDATE
SET dia_chi = EXCLUDED.dia_chi, so_thua = EXCLUDED.so_thua, to_ban_do = EXCLUDED.to_ban_do,
    dien_tich_m2 = EXCLUDED.dien_tich_m2, loai_dat = EXCLUDED.loai_dat;

--------------------------------------------------------------------------------
-- 4. Ma trận thẩm quyền (A-LEGAL-04)
--------------------------------------------------------------------------------
INSERT INTO app_construction.tham_quyen_cap_phep
    (id, loai_cong_trinh, cap_cong_trinh, doi_tuong, trong_kcn, cap_hanh_chinh,
     co_quan_cap, nguoi_ky, legal_citation_key, uu_tien, status)
VALUES
    ('33333333-3333-4333-8333-000000000001', 'nha_o_rieng_le', NULL, 'ho_gia_dinh_ca_nhan', false, NULL,
     'UBND cấp xã', 'Chủ tịch UBND cấp xã hoặc người được ủy quyền', 'ND217-D53-K1', 1, 'hieu_luc'),
    ('33333333-3333-4333-8333-000000000002', 'nha_o_rieng_le', NULL, 'to_chuc', false, NULL,
     'Sở Xây dựng', 'Giám đốc Sở Xây dựng hoặc người được ủy quyền', 'ND217-D53-K3', 10, 'hieu_luc'),
    ('33333333-3333-4333-8333-000000000003', 'cong_trinh', 'III', 'tat_ca', false, NULL,
     'UBND cấp xã', 'Chủ tịch UBND cấp xã hoặc người được ủy quyền', 'ND217-D53-K1', 20, 'hieu_luc'),
    ('33333333-3333-4333-8333-000000000004', 'cong_trinh', 'IV', 'tat_ca', false, NULL,
     'UBND cấp xã', 'Chủ tịch UBND cấp xã hoặc người được ủy quyền', 'ND217-D53-K1', 20, 'hieu_luc'),
    ('33333333-3333-4333-8333-000000000005', 'cong_trinh', 'I', 'tat_ca', false, NULL,
     'Sở Xây dựng', 'Giám đốc Sở Xây dựng hoặc người được ủy quyền', 'ND217-D53-K3', 30, 'hieu_luc'),
    ('33333333-3333-4333-8333-000000000006', 'cong_trinh', 'II', 'tat_ca', false, NULL,
     'Sở Xây dựng', 'Giám đốc Sở Xây dựng hoặc người được ủy quyền', 'ND217-D53-K3', 30, 'hieu_luc'),
    ('33333333-3333-4333-8333-000000000007', 'tat_ca', NULL, 'tat_ca', true, NULL,
     'Ban quản lý KCN, khu chế xuất, khu công nghệ cao, khu kinh tế',
     'Trưởng Ban quản lý hoặc người được ủy quyền', 'ND217-D53-K2', 5, 'hieu_luc')
ON CONFLICT (id) DO UPDATE
SET loai_cong_trinh = EXCLUDED.loai_cong_trinh, cap_cong_trinh = EXCLUDED.cap_cong_trinh,
    doi_tuong = EXCLUDED.doi_tuong, trong_kcn = EXCLUDED.trong_kcn,
    co_quan_cap = EXCLUDED.co_quan_cap, nguoi_ky = EXCLUDED.nguoi_ky,
    legal_citation_key = EXCLUDED.legal_citation_key, uu_tien = EXCLUDED.uu_tien,
    updated_at = now();

--------------------------------------------------------------------------------
-- 5. Khung phí và lưu trữ (chờ văn bản địa phương)
--------------------------------------------------------------------------------
INSERT INTO app_construction.bieu_phi_dia_phuong
    (id, tenant, ten_thu_tuc, don_vi_tinh, muc_phi, don_vi_tien, can_cu, hieu_luc_tu, status)
VALUES
    ('44444444-4444-4444-8444-000000000001', 'phuong-a', 'Cấp giấy phép xây dựng nhà ở riêng lẻ', 'hồ sơ', 50000, 'VND',
     'Nghị quyết HĐND cấp tỉnh (chưa có số hiệu trong bộ tài liệu; chờ văn bản địa phương)', NULL,
     'cho_van_ban_dia_phuong'),
    ('44444444-4444-4444-8444-000000000002', 'phuong-b', 'Cấp giấy phép xây dựng nhà ở riêng lẻ', 'hồ sơ', 50000, 'VND',
     'Nghị quyết HĐND cấp tỉnh (chưa có số hiệu trong bộ tài liệu; chờ văn bản địa phương)', NULL,
     'cho_van_ban_dia_phuong')
ON CONFLICT (id) DO UPDATE
SET muc_phi = EXCLUDED.muc_phi, can_cu = EXCLUDED.can_cu, updated_at = now();

INSERT INTO app_construction.chinh_sach_luu_tru
    (tenant, nhom_ho_so, thoi_han_nam, hinh_thuc_luu_tru, can_cu, status)
VALUES
    ('phuong-a', 'cap_phep_xay_dung', NULL, 'dien_tu', 'Luật Lưu trữ 33/2024/QH15', 'cho_van_ban_dia_phuong'),
    ('phuong-b', 'cap_phep_xay_dung', NULL, 'dien_tu', 'Luật Lưu trữ 33/2024/QH15', 'cho_van_ban_dia_phuong')
ON CONFLICT (tenant, nhom_ho_so) DO UPDATE
SET can_cu = EXCLUDED.can_cu, updated_at = now();

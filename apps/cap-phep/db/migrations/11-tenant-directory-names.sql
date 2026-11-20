-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 11-tenant-directory-names.sql — tên hiển thị địa bàn mẫu cho danh mục nền tảng.
-- Lõi chỉ giữ mã tenant; lớp ứng dụng cấp phép bổ sung tên tiếng Việt và mã ĐVHC.

DO $$
BEGIN
    IF to_regclass('core.tenants') IS NOT NULL THEN
        UPDATE core.tenants SET ten = 'Phường A', ma_dvhc = '790101' WHERE tenant = 'phuong-a';
        UPDATE core.tenants SET ten = 'Phường B', ma_dvhc = '790102' WHERE tenant = 'phuong-b';
        UPDATE core.tenants SET ten = 'Quản trị toàn cục' WHERE tenant = 'global';
    END IF;
END $$;

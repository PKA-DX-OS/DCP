-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

-- FIX-V11-15: migration 18 cho trật tự xây dựng mở hồ sơ đã cấp phép qua mo_ho_so, nhưng dịch vụ
-- nghiệm thu (services/construction) đọc app_cap_phep.ho_so trực tiếp dưới RLS nên mục Nghiệm thu
-- vẫn báo "Không tìm thấy hồ sơ trong địa bàn". Đưa cùng điều kiện vào chính sách SELECT:
-- vai trat-tu-xd xem hồ sơ cùng phường khi trang_thai = 'DA_CAP'. Các điều kiện cũ giữ nguyên.
-- Migration 01 tạo lại chính sách mỗi lần cài nên tệp này phải chạy sau 01. Idempotent.

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
            -- Trật tự xây dựng giám sát thi công, nghiệm thu: chỉ hồ sơ đã cấp phép
            OR (core.has_role('app:cap-phep:trat-tu-xd') AND trang_thai = 'DA_CAP')
        )
    );

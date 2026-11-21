-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

-- Tên hiển thị theo mã người dùng (sub) cho các bảng của cán bộ: yêu cầu dữ liệu cá nhân, nhật ký.
-- Trước đây giao diện chỉ có `subject_sub` (UUID) nên hiện mã thay cho tên.
-- Chỉ cán bộ, kiểm toán, quản trị và DPO trong cùng phường đọc được (RLS của users_directory vẫn áp
-- dụng vì view chạy theo quyền người gọi); chủ đầu tư không đọc được danh bạ.
-- Idempotent: chạy lại thay view.

CREATE OR REPLACE VIEW app_cap_phep.v_ten_nguoi_dung
WITH (security_invoker = true) AS
SELECT u.id::text AS sub, u.username, u.full_name
FROM core.users_directory u
WHERE u.tenant = core.jwt_tenant()
  AND (
    core.has_role('app:cap-phep:mot-cua')
    OR core.has_role('app:cap-phep:tham-dinh')
    OR core.has_role('app:cap-phep:lanh-dao')
    OR core.has_role('app:cap-phep:trat-tu-xd')
    OR core.has_role('dx:auditor')
    OR core.has_role('dx:dpo')
    OR core.has_role('dx:tenant-admin')
    OR core.has_role('dx:platform-admin')
  );

REVOKE ALL ON app_cap_phep.v_ten_nguoi_dung FROM PUBLIC, anon, web_user;
GRANT SELECT ON app_cap_phep.v_ten_nguoi_dung TO web_user;

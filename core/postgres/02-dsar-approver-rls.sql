-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

-- Cho phép vai trò được khai báo trong dsar_policies xem/xử lý DSAR của tenant.
-- Trước đây RLS chỉ cho chủ thể, dx:dpo, tenant-admin và platform-admin.
DROP POLICY IF EXISTS rls_dsar_requests_tenant ON core.dsar_requests;
CREATE POLICY rls_dsar_requests_tenant ON core.dsar_requests
    FOR ALL TO web_user
    USING (
        tenant = core.jwt_tenant()
        AND (
            subject_sub = core.jwt_sub()
            OR core.has_role('dx:dpo')
            OR core.has_role('dx:tenant-admin')
            OR core.has_role('dx:platform-admin')
            OR EXISTS (
                SELECT 1
                FROM core.app_policies ap
                CROSS JOIN LATERAL jsonb_array_elements_text(ap.policy_data->'approver_roles') AS r(role_name)
                WHERE ap.policy_type IN ('break_glass', 'dsar_policies')
                  AND core.has_role(r.role_name)
            )
        )
    );

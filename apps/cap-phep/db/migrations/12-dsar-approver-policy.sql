-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

-- Cho phép lãnh đạo địa bàn xử lý yêu cầu dữ liệu cá nhân (DSAR) của tenant.
-- core_api.dsar_requests và core_api.xu_ly_dsar đọc approver_roles từ policy này.
INSERT INTO core.app_policies (app_code, policy_type, policy_key, policy_data)
VALUES (
    'cap-phep',
    'dsar_policies',
    'default',
    '{"approver_roles": ["app:cap-phep:lanh-dao", "dx:tenant-admin", "dx:platform-admin"]}'::jsonb
)
ON CONFLICT (app_code, policy_type, policy_key)
DO UPDATE SET policy_data = EXCLUDED.policy_data;

-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

-- Tệp tải lên trước khi hồ sơ được tạo có object_type = 'draft.ho_so'.
-- Sau khi hồ sơ tồn tại, quyền đọc tệp phải dùng cùng hàm kiểm tra quyền hồ sơ.
INSERT INTO core.app_policies (app_code, policy_type, policy_key, policy_data)
VALUES (
    'cap-phep',
    'object_access',
    'draft.ho_so',
    '{"function_name": "app_cap_phep_private.can_access_ho_so"}'::jsonb
)
ON CONFLICT (app_code, policy_type, policy_key)
DO UPDATE SET policy_data = EXCLUDED.policy_data;

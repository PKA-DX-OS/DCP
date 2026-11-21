-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

-- FIX-V11-10: sync_flow_state đã ghi kết luận phiếu hậu kiểm (người kiểm tra từ JWT, ghiChu,
-- nhật ký kiểm toán) nên lớp bọc sync_trang_thai của migration 16 là thừa và ghi đè
-- "Đạt tiêu chuẩn" thành "Đạt". app.yaml trở lại dùng sync_flow_state.
-- Giữ tên hàm (chỉ chuyển tiếp) để chính sách cũ còn trỏ tới nó trong lúc nâng cấp không lỗi;
-- bỏ hẳn ở bản sau. Idempotent.

CREATE OR REPLACE FUNCTION app_cap_phep_private.sync_trang_thai(
    p_process_id text,
    p_task_def text,
    p_variables jsonb DEFAULT '{}'::jsonb
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
BEGIN
    PERFORM app_cap_phep_private.sync_flow_state(p_process_id, p_task_def, p_variables);
END;
$$;

COMMENT ON FUNCTION app_cap_phep_private.sync_trang_thai(text, text, jsonb) IS
    'Không dùng nữa (FIX-V11-10): chuyển tiếp tới sync_flow_state';

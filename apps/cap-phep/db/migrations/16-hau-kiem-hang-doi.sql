-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later

-- Hậu kiểm vào hàng đợi (FIX-V11-08).
-- Trước đây phiếu lập tay (lap_phieu_kiem_tra) không mở quy trình hau-kiem nên không có việc, và
-- kết luận ở bước kiểm tra hiện trường không được ghi lại vào phiếu.
-- - sync_hau_kiem_state: khi giao diện mở quy trình hau-kiem cho phiếu (business_key = id phiếu),
--   gắn process_instance_id vào phiếu cùng phường, chỉ khi phiếu chưa có quy trình.
-- - sync_trang_thai: hàm đồng bộ chung của app (flow_policies.sync_state_sql); giữ nguyên
--   sync_flow_state cho hồ sơ rồi ghi kết luận phiếu khi xong taskKiemTraHienTruong/taskXuLyViPham.
-- Idempotent: chỉ CREATE OR REPLACE.

CREATE OR REPLACE FUNCTION app_cap_phep_private.sync_hau_kiem_state(
    p_process_id text,
    p_event text,
    p_variables jsonb DEFAULT '{}'::jsonb
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_phieu_id uuid;
BEGIN
    IF p_event NOT IN ('process_started', 'start') THEN
        RETURN;
    END IF;

    BEGIN
        v_phieu_id := COALESCE(p_variables->>'phieu_id', p_variables->>'business_key')::uuid;
    EXCEPTION WHEN invalid_text_representation THEN
        RETURN;
    END;

    -- _tenant do dịch vụ flow ghi từ JWT người mở quy trình, không lấy từ biến client gửi
    UPDATE app_cap_phep.phieu_kiem_tra
    SET process_instance_id = p_process_id
    WHERE id = v_phieu_id
      AND process_instance_id IS NULL
      AND tenant = p_variables->>'_tenant';
END;
$$;

REVOKE ALL ON FUNCTION app_cap_phep_private.sync_hau_kiem_state(text, text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.sync_hau_kiem_state(text, text, jsonb) TO svc, dxos_svc, dxos_owner;

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
DECLARE
    v_dat boolean := lower(COALESCE(p_variables->>'ketLuan', '')) = 'dat';
BEGIN
    PERFORM app_cap_phep_private.sync_flow_state(p_process_id, p_task_def, p_variables);

    IF p_task_def = 'taskKiemTraHienTruong' THEN
        -- Không có kết luận thì quy trình đi nhánh vi phạm (mặc định của BPMN), phiếu ghi như vậy
        UPDATE app_cap_phep.phieu_kiem_tra
        SET trang_thai = CASE WHEN v_dat THEN 'DA_XU_LY' ELSE 'DANG_KIEM_TRA' END,
            ket_luan = CASE WHEN v_dat THEN 'Đạt' ELSE 'Có vi phạm' END,
            ghi_chu = COALESCE(NULLIF(p_variables->>'ghi_chu', ''), ghi_chu)
        WHERE process_instance_id = p_process_id;
    ELSIF p_task_def = 'taskXuLyViPham' THEN
        UPDATE app_cap_phep.phieu_kiem_tra
        SET trang_thai = 'DA_XU_LY',
            ghi_chu = COALESCE(NULLIF(p_variables->>'ghi_chu', ''), ghi_chu)
        WHERE process_instance_id = p_process_id;
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION app_cap_phep_private.sync_trang_thai(text, text, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.sync_trang_thai(text, text, jsonb) TO svc, dxos_svc, dxos_owner;

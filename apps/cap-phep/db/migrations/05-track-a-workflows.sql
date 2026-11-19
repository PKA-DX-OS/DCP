-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 05-track-a-workflows.sql — nối quy hoạch/nghiệm thu vào work list mà không
-- ghi đè process chính của hồ sơ.
-- Idempotent. Chạy sau 04-authority-guard.sql.

ALTER TABLE app_cap_phep.ho_so
    ADD COLUMN IF NOT EXISTS quy_hoach_process_id text,
    ADD COLUMN IF NOT EXISTS nghiem_thu_process_id text;

CREATE INDEX IF NOT EXISTS idx_ho_so_quy_hoach_process
    ON app_cap_phep.ho_so (quy_hoach_process_id)
    WHERE quy_hoach_process_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ho_so_nghiem_thu_process
    ON app_cap_phep.ho_so (nghiem_thu_process_id)
    WHERE nghiem_thu_process_id IS NOT NULL;

CREATE OR REPLACE FUNCTION app_cap_phep_private.sync_quy_hoach_state(
    p_process_id text,
    p_task_def text,
    p_variables jsonb DEFAULT '{}'::jsonb
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    v_ho_so_id uuid;
BEGIN
    BEGIN
        v_ho_so_id := NULLIF(p_variables->>'ho_so_id', '')::uuid;
    EXCEPTION WHEN OTHERS THEN
        v_ho_so_id := NULL;
    END;

    IF p_task_def = 'process_started' THEN
        UPDATE app_cap_phep.ho_so
        SET quy_hoach_process_id = p_process_id, updated_at = now()
        WHERE tenant = core.jwt_tenant()
          AND (
              (v_ho_so_id IS NOT NULL AND id = v_ho_so_id)
              OR (NULLIF(p_variables->>'ma_ho_so', '') IS NOT NULL AND ma_ho_so = p_variables->>'ma_ho_so')
              OR (NULLIF(p_variables->>'business_key', '') IS NOT NULL AND ma_ho_so = p_variables->>'business_key')
          );
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep_private.sync_quy_hoach_state(text, text, jsonb)
    TO svc, dxos_svc, dxos_owner;

CREATE OR REPLACE FUNCTION app_cap_phep_private.sync_nghiem_thu_state(
    p_process_id text,
    p_task_def text,
    p_variables jsonb DEFAULT '{}'::jsonb
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, public, pg_temp
AS $$
DECLARE
    v_ho_so_id uuid;
BEGIN
    BEGIN
        v_ho_so_id := NULLIF(p_variables->>'ho_so_id', '')::uuid;
    EXCEPTION WHEN OTHERS THEN
        v_ho_so_id := NULL;
    END;

    IF p_task_def = 'process_started' THEN
        UPDATE app_cap_phep.ho_so
        SET nghiem_thu_process_id = p_process_id, updated_at = now()
        WHERE tenant = core.jwt_tenant()
          AND (
              (v_ho_so_id IS NOT NULL AND id = v_ho_so_id)
              OR (NULLIF(p_variables->>'ma_ho_so', '') IS NOT NULL AND ma_ho_so = p_variables->>'ma_ho_so')
              OR (NULLIF(p_variables->>'business_key', '') IS NOT NULL AND ma_ho_so = p_variables->>'business_key')
          );
    END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep_private.sync_nghiem_thu_state(text, text, jsonb)
    TO svc, dxos_svc, dxos_owner;

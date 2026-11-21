-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 21-ngay-lam-viec.sql — số ngày làm việc giữa hai thời điểm cho chỉ số thời gian xử lý.
-- Cùng quy tắc với scripts/impact_metrics.py: tính theo ngày giờ Việt Nam, đếm thứ Hai
-- đến thứ Sáu sau ngày bắt đầu đến hết ngày kết thúc, không trừ ngày lễ.
-- Idempotent.

CREATE OR REPLACE FUNCTION app_cap_phep.so_ngay_lam_viec(p_tu timestamptz, p_den timestamptz)
RETURNS integer
LANGUAGE sql
IMMUTABLE
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT CASE
        WHEN p_tu IS NULL OR p_den IS NULL THEN NULL
        ELSE (
            SELECT count(*)::int
            FROM generate_series(
                (p_tu AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + 1,
                (p_den AT TIME ZONE 'Asia/Ho_Chi_Minh')::date,
                interval '1 day'
            ) AS d
            WHERE extract(isodow FROM d) < 6
        )
    END;
$$;

GRANT EXECUTE ON FUNCTION app_cap_phep.so_ngay_lam_viec(timestamptz, timestamptz) TO web_user, svc, dxos_svc;

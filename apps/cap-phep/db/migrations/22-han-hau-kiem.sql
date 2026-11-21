-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 22-han-hau-kiem.sql — hạn xử lý cho phiếu kiểm tra hậu kiểm.
-- Phiếu chưa có hạn nên không đo được đúng hạn; việc hậu kiểm trong hàng đợi hiện "Không có hạn".
-- Hạn kiểm tra hiện trường 2 ngày kể từ lúc lập phiếu, khớp SLA taskKiemTraHienTruong (P2D)
-- trong flow_policies.sla của app.yaml. Idempotent.

ALTER TABLE app_cap_phep.phieu_kiem_tra ADD COLUMN IF NOT EXISTS han_xu_ly_at timestamptz;

CREATE OR REPLACE FUNCTION app_cap_phep.thoi_han_hau_kiem()
RETURNS interval
LANGUAGE sql
IMMUTABLE
AS $$ SELECT interval '2 days' $$;

GRANT EXECUTE ON FUNCTION app_cap_phep.thoi_han_hau_kiem() TO web_user, svc, dxos_svc;

CREATE OR REPLACE FUNCTION app_cap_phep_private.dat_han_phieu_kiem_tra()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, pg_catalog
AS $$
BEGIN
    NEW.han_xu_ly_at := COALESCE(NEW.han_xu_ly_at, COALESCE(NEW.created_at, now()) + app_cap_phep.thoi_han_hau_kiem());
    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION app_cap_phep_private.dat_han_phieu_kiem_tra() FROM PUBLIC;

DROP TRIGGER IF EXISTS trg_han_phieu_kiem_tra ON app_cap_phep.phieu_kiem_tra;
CREATE TRIGGER trg_han_phieu_kiem_tra
    BEFORE INSERT ON app_cap_phep.phieu_kiem_tra
    FOR EACH ROW EXECUTE FUNCTION app_cap_phep_private.dat_han_phieu_kiem_tra();

-- Phiếu cũ: hạn tính từ ngày lập
UPDATE app_cap_phep.phieu_kiem_tra
SET han_xu_ly_at = created_at + app_cap_phep.thoi_han_hau_kiem()
WHERE han_xu_ly_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_phieu_kiem_tra_han
    ON app_cap_phep.phieu_kiem_tra (tenant, han_xu_ly_at)
    WHERE trang_thai <> 'DA_XU_LY';

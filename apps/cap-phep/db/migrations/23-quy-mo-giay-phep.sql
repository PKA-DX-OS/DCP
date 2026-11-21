-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 23-quy-mo-giay-phep.sql — giấy phép ghi quy mô đã qua kiểm tra quy hoạch.
-- Trước đây dữ liệu ký và giấy phép lấy so_tang, dien_tich_san_m2 của hồ sơ, bỏ qua quy mô
-- cán bộ đã đối chiếu ở lần kiểm tra quy hoạch đạt gần nhất.
-- - quy_mo_duyet(ho_so): quy mô của lần kiểm tra quy hoạch đạt gần nhất; chưa có thì quy mô hồ sơ.
-- - du_lieu_giay_phep: dữ liệu văn bản ký dùng quy_mo_duyet, thêm nguon_quy_mo.
-- - giay_phep: thêm so_tang, dien_tich_san_m2, nguon_quy_mo; trigger điền khi cấp, điền lại
--   cho giấy phép cũ theo quy mô hồ sơ (chưa có căn cứ khác).
-- Idempotent.

CREATE OR REPLACE FUNCTION app_cap_phep_private.quy_mo_duyet(p_ho_so_id uuid, p_tenant text)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = app_cap_phep, pg_catalog
AS $$
DECLARE
    v_hs app_cap_phep.ho_so%ROWTYPE;
    v_de_xuat jsonb;
    v_so_tang int;
    v_dien_tich double precision;
BEGIN
    SELECT * INTO v_hs FROM app_cap_phep.ho_so WHERE id = p_ho_so_id AND tenant = p_tenant;
    IF v_hs.id IS NULL THEN
        RETURN NULL;
    END IF;

    -- Bảng kết quả quy hoạch thuộc gói xây dựng ở lõi; volume chưa có bảng thì dùng quy mô hồ sơ
    IF to_regclass('app_construction.ket_qua_kiem_tra_quy_hoach') IS NOT NULL THEN
        EXECUTE $q$
            SELECT proposal FROM app_construction.ket_qua_kiem_tra_quy_hoach
            WHERE ho_so_id = $1 AND tenant = $2 AND pass
            ORDER BY created_at DESC
            LIMIT 1
        $q$ INTO v_de_xuat USING p_ho_so_id, p_tenant;
    END IF;

    IF v_de_xuat ->> 'so_tang' ~ '^\d+$' THEN
        v_so_tang := (v_de_xuat ->> 'so_tang')::int;
    END IF;
    IF v_de_xuat ->> 'dien_tich_san_m2' ~ '^\d+(\.\d+)?$' THEN
        v_dien_tich := (v_de_xuat ->> 'dien_tich_san_m2')::double precision;
    END IF;

    RETURN jsonb_build_object(
        'so_tang', COALESCE(v_so_tang, v_hs.so_tang),
        'dien_tich_san_m2', COALESCE(v_dien_tich, v_hs.dien_tich_san_m2),
        'nguon', CASE WHEN v_so_tang IS NOT NULL OR v_dien_tich IS NOT NULL
                      THEN 'kiem_tra_quy_hoach' ELSE 'ho_so' END
    );
END;
$$;

REVOKE ALL ON FUNCTION app_cap_phep_private.quy_mo_duyet(uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.quy_mo_duyet(uuid, text) TO svc, dxos_svc, dxos_owner;

CREATE OR REPLACE FUNCTION app_cap_phep_private.du_lieu_giay_phep(
    p_process_id text,
    p_tenant text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
DECLARE
    v_hs app_cap_phep.ho_so%ROWTYPE;
    v_qm jsonb;
BEGIN
    SELECT * INTO v_hs
    FROM app_cap_phep.ho_so
    WHERE process_instance_id = p_process_id
      AND (p_tenant IS NULL OR tenant = p_tenant)
    LIMIT 1;

    IF v_hs.id IS NULL THEN
        RAISE EXCEPTION 'Không tìm thấy hồ sơ với process_instance_id = %', p_process_id;
    END IF;

    v_qm := app_cap_phep_private.quy_mo_duyet(v_hs.id, v_hs.tenant);

    RETURN jsonb_build_object(
        'ho_so_id', v_hs.id,
        'ma_ho_so', v_hs.ma_ho_so,
        'chu_dau_tu', v_hs.ho_ten,
        'cccd', v_hs.cccd,
        'dia_chi_cong_trinh', v_hs.dia_chi_cong_trinh,
        'thua_dat', v_hs.thua_dat,
        'so_tang', (v_qm->>'so_tang')::int,
        'dien_tich_san_m2', (v_qm->>'dien_tich_san_m2')::double precision,
        'nguon_quy_mo', v_qm->>'nguon',
        'tenant', v_hs.tenant,
        'ngay_cap', to_char(now(), 'DD/MM/YYYY')
    );
END;
$$;
GRANT EXECUTE ON FUNCTION app_cap_phep_private.du_lieu_giay_phep(text, text) TO svc, dxos_svc, dxos_owner;

ALTER TABLE app_cap_phep.giay_phep ADD COLUMN IF NOT EXISTS so_tang integer;
ALTER TABLE app_cap_phep.giay_phep ADD COLUMN IF NOT EXISTS dien_tich_san_m2 double precision;
ALTER TABLE app_cap_phep.giay_phep ADD COLUMN IF NOT EXISTS nguon_quy_mo text;

CREATE OR REPLACE FUNCTION app_cap_phep_private.dien_quy_mo_giay_phep()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, pg_catalog
AS $$
DECLARE
    v_qm jsonb;
BEGIN
    IF NEW.so_tang IS NULL AND NEW.dien_tich_san_m2 IS NULL THEN
        v_qm := app_cap_phep_private.quy_mo_duyet(NEW.ho_so_id, NEW.tenant);
        NEW.so_tang := (v_qm ->> 'so_tang')::int;
        NEW.dien_tich_san_m2 := (v_qm ->> 'dien_tich_san_m2')::double precision;
        NEW.nguon_quy_mo := v_qm ->> 'nguon';
    END IF;
    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION app_cap_phep_private.dien_quy_mo_giay_phep() FROM PUBLIC;

DROP TRIGGER IF EXISTS trg_quy_mo_giay_phep ON app_cap_phep.giay_phep;
CREATE TRIGGER trg_quy_mo_giay_phep
    BEFORE INSERT ON app_cap_phep.giay_phep
    FOR EACH ROW EXECUTE FUNCTION app_cap_phep_private.dien_quy_mo_giay_phep();

-- Giấy phép cấp trước bản sửa: văn bản đã ký theo quy mô hồ sơ, ghi đúng như vậy
UPDATE app_cap_phep.giay_phep g
SET so_tang = h.so_tang, dien_tich_san_m2 = h.dien_tich_san_m2, nguon_quy_mo = 'ho_so'
FROM app_cap_phep.ho_so h
WHERE h.id = g.ho_so_id AND g.so_tang IS NULL AND g.dien_tich_san_m2 IS NULL;

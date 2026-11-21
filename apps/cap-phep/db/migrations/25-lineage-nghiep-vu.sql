-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 25-lineage-nghiep-vu.sql — ghi nhận sự kiện phả hệ OpenLineage theo hồ sơ (D-CAT-02).
-- Kích hoạt khi:
-- 1. Nộp hồ sơ (ho_so.nop) qua trigger trên app_cap_phep.ho_so
-- 2. Cấp giấy phép (giay_phep.cap) qua trigger trên app_cap_phep.giay_phep
-- 3. Kiểm tra quy hoạch và nghiệm thu ghi nhận qua router construction tương ứng
-- 4. Backfill dữ liệu phả hệ cho các bản ghi đã có
-- Ghi vào core.lineage_events với facets.entity = {"type": "...", "id": "..."} và facets.tenant.
-- Tuyệt đối không ghi thông tin định danh cá nhân vào facets.
-- Idempotent.

CREATE SCHEMA IF NOT EXISTS app_cap_phep_private AUTHORIZATION dxos_owner;

-- 1. Trigger khi nộp hồ sơ mới
CREATE OR REPLACE FUNCTION app_cap_phep_private.trg_lineage_nop_ho_so()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
BEGIN
    INSERT INTO core.lineage_events (job, run_id, inputs, outputs, facets)
    VALUES (
        'ho_so.nop',
        gen_random_uuid()::text,
        '[]'::jsonb,
        '[{"name": "app_cap_phep.ho_so"}]'::jsonb,
        jsonb_build_object(
            'tenant', NEW.tenant,
            'entity', jsonb_build_object('type', 'ho_so', 'id', NEW.id::text)
        )
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_lineage_ho_so ON app_cap_phep.ho_so;
CREATE TRIGGER trg_lineage_ho_so
    AFTER INSERT ON app_cap_phep.ho_so
    FOR EACH ROW
    EXECUTE FUNCTION app_cap_phep_private.trg_lineage_nop_ho_so();

-- 2. Trigger khi cấp giấy phép
CREATE OR REPLACE FUNCTION app_cap_phep_private.trg_lineage_cap_giay_phep()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app_cap_phep, core, pg_catalog
AS $$
BEGIN
    IF NEW.ho_so_id IS NOT NULL THEN
        -- Sự kiện phả hệ gắn với hồ sơ
        INSERT INTO core.lineage_events (job, run_id, inputs, outputs, facets)
        VALUES (
            'giay_phep.cap',
            gen_random_uuid()::text,
            '[{"name": "app_cap_phep.ho_so"}]'::jsonb,
            '[{"name": "app_cap_phep.giay_phep"}]'::jsonb,
            jsonb_build_object(
                'tenant', NEW.tenant,
                'entity', jsonb_build_object('type', 'ho_so', 'id', NEW.ho_so_id::text),
                'so_giay_phep', NEW.so_giay_phep
            )
        );

        -- Sự kiện phả hệ gắn với chính giấy phép
        INSERT INTO core.lineage_events (job, run_id, inputs, outputs, facets)
        VALUES (
            'giay_phep.cap',
            gen_random_uuid()::text,
            '[{"name": "app_cap_phep.ho_so"}]'::jsonb,
            '[{"name": "app_cap_phep.giay_phep"}]'::jsonb,
            jsonb_build_object(
                'tenant', NEW.tenant,
                'entity', jsonb_build_object('type', 'giay_phep', 'id', NEW.id::text),
                'so_giay_phep', NEW.so_giay_phep
            )
        );
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_lineage_giay_phep ON app_cap_phep.giay_phep;
CREATE TRIGGER trg_lineage_giay_phep
    AFTER INSERT ON app_cap_phep.giay_phep
    FOR EACH ROW
    EXECUTE FUNCTION app_cap_phep_private.trg_lineage_cap_giay_phep();

-- 3. Backfill cho hồ sơ đã có trong hệ thống (chạy một lần an toàn, không trùng lặp)
INSERT INTO core.lineage_events (event_time, job, run_id, inputs, outputs, facets)
SELECT
    h.created_at,
    'ho_so.nop',
    gen_random_uuid()::text,
    '[]'::jsonb,
    '[{"name": "app_cap_phep.ho_so"}]'::jsonb,
    jsonb_build_object('tenant', h.tenant, 'entity', jsonb_build_object('type', 'ho_so', 'id', h.id::text))
FROM app_cap_phep.ho_so h
WHERE NOT EXISTS (
    SELECT 1 FROM core.lineage_events e
    WHERE e.job = 'ho_so.nop'
      AND e.facets -> 'entity' ->> 'type' = 'ho_so'
      AND e.facets -> 'entity' ->> 'id' = h.id::text
);

DO $$
BEGIN
    IF to_regclass('app_construction.ket_qua_kiem_tra_quy_hoach') IS NOT NULL THEN
        INSERT INTO core.lineage_events (event_time, job, run_id, inputs, outputs, facets)
        SELECT
            k.created_at,
            'quy_hoach.kiem_tra',
            gen_random_uuid()::text,
            '[{"name": "app_cap_phep.ho_so"}, {"name": "app_construction.thua_dat"}]'::jsonb,
            '[{"name": "app_construction.ket_qua_kiem_tra_quy_hoach"}]'::jsonb,
            jsonb_build_object('tenant', k.tenant, 'entity', jsonb_build_object('type', 'ho_so', 'id', k.ho_so_id::text), 'pass', k.pass)
        FROM app_construction.ket_qua_kiem_tra_quy_hoach k
        WHERE k.ho_so_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM core.lineage_events e
            WHERE e.job = 'quy_hoach.kiem_tra'
              AND e.facets -> 'entity' ->> 'type' = 'ho_so'
              AND e.facets -> 'entity' ->> 'id' = k.ho_so_id::text
          );
    END IF;
END $$;

INSERT INTO core.lineage_events (event_time, job, run_id, inputs, outputs, facets)
SELECT
    g.ngay_cap,
    'giay_phep.cap',
    gen_random_uuid()::text,
    '[{"name": "app_cap_phep.ho_so"}]'::jsonb,
    '[{"name": "app_cap_phep.giay_phep"}]'::jsonb,
    jsonb_build_object('tenant', g.tenant, 'entity', jsonb_build_object('type', 'ho_so', 'id', g.ho_so_id::text), 'so_giay_phep', g.so_giay_phep)
FROM app_cap_phep.giay_phep g
WHERE g.ho_so_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM core.lineage_events e
    WHERE e.job = 'giay_phep.cap'
      AND e.facets -> 'entity' ->> 'type' = 'ho_so'
      AND e.facets -> 'entity' ->> 'id' = g.ho_so_id::text
  );

DO $$
BEGIN
    IF to_regclass('app_construction.moc_nghiem_thu') IS NOT NULL THEN
        INSERT INTO core.lineage_events (event_time, job, run_id, inputs, outputs, facets)
        SELECT
            m.created_at,
            'nghiem_thu.moc',
            gen_random_uuid()::text,
            '[{"name": "app_cap_phep.giay_phep"}, {"name": "app_cap_phep.ho_so"}]'::jsonb,
            '[{"name": "app_construction.moc_nghiem_thu"}]'::jsonb,
            jsonb_build_object('tenant', m.tenant, 'entity', jsonb_build_object('type', 'ho_so', 'id', m.ho_so_id::text), 'loai_moc', m.loai_moc, 'ket_qua', m.ket_qua)
        FROM app_construction.moc_nghiem_thu m
        WHERE m.ho_so_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM core.lineage_events e
            WHERE e.job = 'nghiem_thu.moc'
              AND e.facets -> 'entity' ->> 'type' = 'ho_so'
              AND e.facets -> 'entity' ->> 'id' = m.ho_so_id::text
          );
    END IF;
END $$;

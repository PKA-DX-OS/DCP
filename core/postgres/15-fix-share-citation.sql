-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
-- SPDX-License-Identifier: AGPL-3.0-or-later
--
-- 15-fix-share-citation.sql — sửa căn cứ chia sẻ dữ liệu sang NĐ 278/2025.
-- Idempotent.

ALTER TABLE app_construction.chia_se_du_lieu_log
    ALTER COLUMN can_cu_phap_ly SET DEFAULT 'ND-278/2025/ND-CP';

UPDATE app_construction.chia_se_du_lieu_log
SET can_cu_phap_ly = 'ND-278/2025/ND-CP'
WHERE can_cu_phap_ly IN ('ND-49/2025/ND-CP', 'ND-47/2020/ND-CP');

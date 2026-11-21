// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiJson } from "./client";
import type { LienKetMDM } from "../features/link/types";

export interface KetQuaLienKetMDM {
  data: LienKetMDM | null;
  source: "api" | "khong_co";
}

/**
 * Liên kết MDM của hồ sơ. D chưa triển khai API này (404 JSON), nên panel
 * hiển thị ghi chú thay vì coi là lỗi chặn.
 */
export async function fetchDossierLinks(token: string, dossierId: string): Promise<KetQuaLienKetMDM> {
  if (!token || !dossierId) return { data: null, source: "khong_co" };
  try {
    const data = await apiJson<LienKetMDM>(
      `/mdm/dossiers/${encodeURIComponent(dossierId)}/links`,
      { token, retries: 0 },
      "Lỗi tải liên kết dữ liệu",
    );
    return { data, source: "api" };
  } catch {
    return { data: null, source: "khong_co" };
  }
}

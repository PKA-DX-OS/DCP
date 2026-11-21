// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiJson } from "./client";
import type { LienKetMDM } from "../features/link/types";

export type MdmSearchType = "subject" | "parcel" | "construction" | "permit" | "organization";
export type MdmLinkType = "subject" | "parcel" | "construction" | "permit";

export interface MdmEntitySummary {
  type: MdmSearchType;
  id: string;
  nhan: string;
  ma?: string | null;
  confidence?: number;
  source?: string;
}

export interface MdmSearchResponse {
  items: MdmEntitySummary[];
  page: number;
  page_size: number;
  total: number;
}

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

/** Tìm thực thể dữ liệu chủ để liên kết thủ công với hồ sơ. */
export async function searchMdmEntities(
  token: string,
  query: string,
  type: MdmSearchType,
  page = 1,
  pageSize = 10,
): Promise<MdmSearchResponse> {
  const qs = new URLSearchParams({
    q: query.trim(),
    type,
    page: String(page),
    page_size: String(pageSize),
  });
  return apiJson<MdmSearchResponse>(
    `/mdm/search?${qs.toString()}`,
    { token, retries: 0 },
    "Lỗi tìm dữ liệu chủ",
  );
}

/** Tạo liên kết thủ công; backend ghi audit `mdm.entity.linked`. */
export async function createMdmLink(
  token: string,
  payload: { dossier_id: string; entity_type: MdmLinkType; entity_id: string; ghi_chu?: string },
): Promise<LienKetMDM> {
  const khoa =
    globalThis.crypto?.randomUUID?.() ||
    `mdm-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return apiJson<LienKetMDM>(
    "/mdm/links",
    {
      token,
      method: "POST",
      body: payload,
      headers: { "Idempotency-Key": khoa },
      retries: 0,
    },
    "Lỗi liên kết dữ liệu chủ",
  );
}

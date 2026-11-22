// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiGet } from "../api";

export type PhanLoaiDuLieu = "public" | "internal" | "pii" | "sensitive";

export interface TaiSanDuLieu {
  asset: string;
  domain: string;
  description: string;
  owner: string;
  steward: string | null;
  classification: PhanLoaiDuLieu;
  retention: string | null;
  freshness_sla: string | null;
  last_updated: string | null;
  version: string;
  dq_score: number | null;
}

export interface CotDuLieu {
  name: string;
  type: string;
  classification: PhanLoaiDuLieu;
  description: string | null;
  masked_in_api: boolean;
}

export interface TaiSanChiTiet extends TaiSanDuLieu {
  columns: CotDuLieu[];
}

export interface HopDongDuLieu {
  asset: string;
  version: string;
  json_schema: Record<string, unknown>;
  sla: { freshness?: string; availability_pct?: number };
  consumers: string[];
  effective_from: string;
}

export async function fetchCatalogAssets(params: {
  domain?: string;
  classification?: PhanLoaiDuLieu | "";
} = {}): Promise<TaiSanDuLieu[]> {
  const qs = new URLSearchParams();
  if (params.domain) qs.set("domain", params.domain);
  if (params.classification) qs.set("classification", params.classification);
  return apiGet<TaiSanDuLieu[]>(`/catalog/assets${qs.size ? `?${qs}` : ""}`);
}

export async function fetchCatalogAsset(asset: string): Promise<TaiSanChiTiet> {
  return apiGet<TaiSanChiTiet>(`/catalog/assets/${encodeURIComponent(asset)}`);
}

export async function fetchCatalogContracts(asset?: string): Promise<HopDongDuLieu[]> {
  const qs = new URLSearchParams();
  if (asset) qs.set("asset", asset);
  return apiGet<HopDongDuLieu[]>(`/catalog/contracts${qs.size ? `?${qs}` : ""}`);
}

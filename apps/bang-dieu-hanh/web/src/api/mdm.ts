// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiGet, apiPost } from "../api";

export type LoaiThucThe = "subject" | "parcel" | "construction" | "permit" | "organization";

export interface ThucTheTomTat {
  type: LoaiThucThe;
  id: string;
  nhan: string;
  ma: string | null;
  confidence: number;
  source?: string;
}

export interface TrangThucThe {
  items: ThucTheTomTat[];
  page: number;
  page_size: number;
  total: number;
}

export interface HoSoLienKet {
  dossier_id: string;
  ma_ho_so: string;
  trang_thai: string;
}

export interface ThamChieuNgoai {
  system: string;
  external_id: string;
  confidence: number;
  last_synced_at: string | null;
}

export interface ThucTheChiTiet extends ThucTheTomTat {
  merged_into: string | null;
  thuoc_tinh: Record<string, unknown>;
  ho_so: HoSoLienKet[];
  external_refs: ThamChieuNgoai[];
}

export interface UngVienTrung {
  ung_vien: ThucTheTomTat;
  confidence: number;
  ly_do: string[];
}

export interface KetQuaGop {
  merge_id: string;
  entity_type: LoaiThucThe;
  giu_id: string;
  gop_ids: string[];
  trang_thai: "da_gop" | "da_hoan_tac";
  thuc_hien_luc: string;
}

function maIdempotency(): string {
  return globalThis.crypto?.randomUUID?.() || `mdm-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function fetchMdmSearch(
  type: LoaiThucThe,
  q: string,
  page = 1,
  page_size = 10,
): Promise<TrangThucThe> {
  const qs = new URLSearchParams({ type, q, page: String(page), page_size: String(page_size) });
  return apiGet<TrangThucThe>(`/mdm/search?${qs.toString()}`);
}

export async function fetchMdmEntity(type: LoaiThucThe, id: string): Promise<ThucTheChiTiet> {
  return apiGet<ThucTheChiTiet>(`/mdm/entities/${type}/${encodeURIComponent(id)}`);
}

export async function fetchMdmCandidates(type: LoaiThucThe, id: string): Promise<UngVienTrung[]> {
  const qs = new URLSearchParams({ entity_type: type, entity_id: id });
  return apiGet<UngVienTrung[]>(`/mdm/candidates?${qs.toString()}`);
}

/** Gộp bản ghi trùng; backend ghi audit `mdm.entity.merged`. */
export async function mergeMdmEntities(payload: {
  entity_type: LoaiThucThe;
  giu_id: string;
  gop_ids: string[];
  ly_do: string;
}): Promise<KetQuaGop> {
  return apiPost<KetQuaGop>("/mdm/merge", payload, { "Idempotency-Key": maIdempotency() });
}

/** Hoàn tác một lần gộp; backend ghi audit `mdm.entity.merge_undone`. */
export async function undoMdmMerge(mergeId: string): Promise<KetQuaGop> {
  return apiPost<KetQuaGop>(
    `/mdm/merge/${encodeURIComponent(mergeId)}/undo`,
    {},
    { "Idempotency-Key": maIdempotency() },
  );
}

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiGet, apiPost } from "../api";

export type MienDuLieu =
  | "cong_dan"
  | "thua_dat"
  | "ho_so"
  | "giay_phep"
  | "cong_trinh"
  | "giay_to"
  | "kiem_tra"
  | "tai_chinh"
  | "audit";

export type MucDoDq = "info" | "warn" | "critical";
export type TrangThaiDq = "open" | "in_progress" | "resolved" | "ignored";

export interface DiemMien {
  domain: MienDuLieu;
  score: number | null;
  rules: number;
  failed_rules: number;
  open_issues: number;
}

export interface TongQuanDq {
  run_id: string | null;
  computed_at: string | null;
  overall_score: number | null;
  domains: DiemMien[];
}

export interface RuleDq {
  code: string;
  domain: MienDuLieu;
  dimension: string;
  severity: MucDoDq;
  description: string;
  owner: string;
  enabled: boolean;
  last_result: { total: number; failed: number; score: number } | null;
}

export interface VanDeDq {
  id: string;
  rule_code: string;
  domain: MienDuLieu;
  entity_type: string;
  entity_id: string;
  field: string | null;
  severity: MucDoDq;
  status: TrangThaiDq;
  assigned_to: string | null;
  note: string | null;
  created_at: string;
  resolved_at: string | null;
  dossier_id: string | null;
}

export interface TrangVanDeDq {
  items: VanDeDq[];
  page: number;
  page_size: number;
  total: number;
}

export interface ThamSoVanDeDq {
  domain?: MienDuLieu | "";
  severity?: MucDoDq | "";
  status?: TrangThaiDq | "";
  page?: number;
  page_size?: number;
}

export async function fetchDqSummary(): Promise<TongQuanDq> {
  return apiGet<TongQuanDq>("/data-quality/summary");
}

export async function fetchDqRules(domain?: MienDuLieu | "", severity?: MucDoDq | ""): Promise<RuleDq[]> {
  const qs = new URLSearchParams();
  if (domain) qs.set("domain", domain);
  if (severity) qs.set("severity", severity);
  return apiGet<RuleDq[]>(`/data-quality/rules${qs.size ? `?${qs}` : ""}`);
}

export async function fetchDqIssues(params: ThamSoVanDeDq = {}): Promise<TrangVanDeDq> {
  const qs = new URLSearchParams();
  if (params.domain) qs.set("domain", params.domain);
  if (params.severity) qs.set("severity", params.severity);
  if (params.status) qs.set("status", params.status);
  qs.set("page", String(params.page || 1));
  qs.set("page_size", String(params.page_size || 20));
  return apiGet<TrangVanDeDq>(`/data-quality/issues?${qs.toString()}`);
}

function maIdempotency(): string {
  return globalThis.crypto?.randomUUID?.() || `dq-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Đóng (`resolved`) hoặc bỏ qua (`ignored`) một vấn đề; backend ghi audit. */
export async function resolveDqIssue(
  id: string,
  status: "resolved" | "ignored",
  note: string,
): Promise<VanDeDq> {
  return apiPost<VanDeDq>(
    `/data-quality/issues/${encodeURIComponent(id)}/resolve`,
    { status, note },
    { "Idempotency-Key": maIdempotency() },
  );
}

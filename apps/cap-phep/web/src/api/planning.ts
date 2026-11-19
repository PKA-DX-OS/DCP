// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiJson } from "./client";

export interface PlanningCheckBody {
  ho_so_id?: string;
  thua_dat_id?: string;
  proposal: Record<string, any>;
}

export async function fetchPlanningParcels(token: string): Promise<any[]> {
  return apiJson<any[]>("/planning/parcels", { token }, "Lỗi tải thửa đất quy hoạch");
}

export async function fetchPlanningZones(token: string): Promise<any[]> {
  return apiJson<any[]>("/planning/zones", { token }, "Lỗi tải vùng quy hoạch");
}

export async function fetchPlanningDocuments(token: string): Promise<any[]> {
  return apiJson<any[]>("/planning/documents", { token }, "Lỗi tải văn bản quy hoạch");
}

export async function fetchPlanningResults(token: string, hoSoId: string): Promise<any[]> {
  return apiJson<any[]>(`/planning/results/${encodeURIComponent(hoSoId)}`, { token }, "Lỗi tải kết quả quy hoạch");
}

export async function checkPlanning(token: string, body: PlanningCheckBody): Promise<any> {
  return apiJson("/planning/check", { token, method: "POST", body }, "Lỗi kiểm tra quy hoạch");
}

export async function fetchLegalCitations(token: string, topic: string): Promise<any[]> {
  return apiJson<any[]>(`/planning/legal/citations?topic=${encodeURIComponent(topic)}`, { token }, "Lỗi tải trích dẫn pháp lý");
}

export async function askAssistant(token: string, question: string): Promise<any> {
  return apiJson("/assistant/ask", { token, method: "POST", body: { question, app: "cap-phep" } }, "Lỗi hỏi trợ lý");
}

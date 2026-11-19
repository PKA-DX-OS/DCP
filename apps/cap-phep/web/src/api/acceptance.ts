// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiJson } from "./client";

export async function fetchAcceptance(token: string, hoSoId: string): Promise<any> {
  return apiJson(`/acceptance/${encodeURIComponent(hoSoId)}`, { token }, "Lỗi tải nghiệm thu");
}

export async function createMilestone(token: string, hoSoId: string, body: Record<string, any>): Promise<any> {
  return apiJson(`/acceptance/${encodeURIComponent(hoSoId)}/milestones`, { token, method: "POST", body }, "Lỗi tạo mốc nghiệm thu");
}

export async function submitAcceptanceRecord(token: string, mocId: string, body: Record<string, any>): Promise<any> {
  return apiJson(`/acceptance/milestones/${encodeURIComponent(mocId)}/records`, { token, method: "POST", body }, "Lỗi nộp biên bản");
}

export async function submitAsBuilt(token: string, hoSoId: string, body: Record<string, any>): Promise<any> {
  return apiJson(`/acceptance/${encodeURIComponent(hoSoId)}/as-built`, { token, method: "POST", body }, "Lỗi nộp bản vẽ hoàn công");
}

export async function fetchAcceptanceHistory(token: string, hoSoId: string): Promise<any[]> {
  return apiJson<any[]>(`/acceptance/${encodeURIComponent(hoSoId)}/history`, { token }, "Lỗi tải lịch sử nghiệm thu");
}

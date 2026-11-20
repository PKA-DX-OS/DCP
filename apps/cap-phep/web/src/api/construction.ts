// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiJson } from "./client";

/** Đọc view che dấu trước; không có view thì đọc bảng gốc; lỗi thì trả danh sách rỗng. */
async function listWithFallback(token: string, view: string, table: string, label: string): Promise<any[]> {
  try {
    return await apiJson<any[]>(`/rest/${view}?order=created_at.desc`, { token }, label);
  } catch {
    try {
      return await apiJson<any[]>(`/rest/${table}?order=created_at.desc`, { token }, label);
    } catch {
      return [];
    }
  }
}

export async function fetchCongTrinh(token: string): Promise<any[]> {
  return listWithFallback(token, "v_cong_trinh", "cong_trinh", "Lỗi tải công trình");
}

export async function fetchPhieuKiemTra(token: string): Promise<any[]> {
  return listWithFallback(token, "v_phieu_kiem_tra", "phieu_kiem_tra", "Lỗi tải phiếu kiểm tra");
}

export async function createInspection(token: string, congTrinhId: string, ghiChu?: string): Promise<any> {
  return apiJson(
    "/rest/rpc/lap_phieu_kiem_tra",
    {
      token,
      method: "POST",
      body: { p_cong_trinh_id: congTrinhId, p_ghi_chu: ghiChu || "Kiểm tra chủ động hiện trường" },
    },
    "Lỗi lập phiếu kiểm tra",
  );
}

export async function triggerDemoSensor(token: string, maCongTrinh: string, laeqDba: number = 86.5): Promise<any> {
  return apiJson(
    "/ingest/demo-sensor",
    { token, method: "POST", body: { site_id: maCongTrinh, metric: "laeq_dba", value: laeqDba } },
    "Lỗi gửi số liệu cảm biến mẫu",
  );
}

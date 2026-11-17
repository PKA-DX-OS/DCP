// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiJson } from "./client";

/** Danh sách yêu cầu truy cập khẩn đang chờ; không có quyền xem thì trả danh sách rỗng. */
export async function fetchPendingBreakGlass(token: string): Promise<any[]> {
  try {
    return await apiJson<any[]>(
      "/rest/rpc/ds_truy_cap_khan",
      { token, method: "POST", body: { p_trang_thai: "pending" }, retries: 2 },
      "Lỗi tải truy cập khẩn",
    );
  } catch {
    return [];
  }
}

export async function requestBreakGlass(token: string, hoSoId: string, reason: string): Promise<any> {
  return apiJson(
    "/rest/rpc/xin_truy_cap_khan",
    { token, method: "POST", body: { p_ho_so_id: hoSoId, p_ly_do: reason } },
    "Lỗi xin truy cập khẩn",
  );
}

export async function approveBreakGlass(token: string, hoSoId: string, userSub: string, approve: boolean): Promise<any> {
  return apiJson(
    "/rest/rpc/duyet_truy_cap_khan",
    { token, method: "POST", body: { p_ho_so_id: hoSoId, p_user_sub: userSub, p_dong_y: approve } },
    "Lỗi duyệt truy cập khẩn",
  );
}

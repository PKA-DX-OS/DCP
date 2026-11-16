// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

export async function fetchPendingBreakGlass(token: string): Promise<any[]> {
  const resp = await fetch("/api/v1/rest/rpc/ds_truy_cap_khan", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ p_trang_thai: "pending" }),
  });
  if (!resp.ok) {
    return [];
  }
  return await resp.json();
}

export async function requestBreakGlass(token: string, hoSoId: string, reason: string): Promise<any> {
  const resp = await fetch("/api/v1/rest/rpc/xin_truy_cap_khan", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ p_ho_so_id: hoSoId, p_ly_do: reason }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.message || `Lỗi xin truy cập khẩn: HTTP ${resp.status}`);
  }
  return await resp.json();
}

export async function approveBreakGlass(token: string, hoSoId: string, userSub: string, approve: boolean): Promise<any> {
  const resp = await fetch("/api/v1/rest/rpc/duyet_truy_cap_khan", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ p_ho_so_id: hoSoId, p_user_sub: userSub, p_dong_y: approve }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.message || `Lỗi duyệt truy cập khẩn: HTTP ${resp.status}`);
  }
  return await resp.json();
}

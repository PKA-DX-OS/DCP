// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { clearSession, getValidToken, login } from "./auth";

const API_BASE = (import.meta.env.VITE_API_BASE || "/api/v1").replace(/\/+$/, "");
const TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

/** Gọi GET có token. Ứng dụng chỉ đọc: không có hàm ghi nghiệp vụ. */
export async function apiGet<T>(path: string): Promise<T> {
  const token = await getValidToken();
  if (!token) {
    await login();
    throw new ApiError(401, "CHUA_DANG_NHAP", "Cần đăng nhập");
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      signal: controller.signal,
    });
  } catch {
    throw new ApiError(0, "MANG", "Không kết nối được máy chủ hoặc quá thời gian chờ");
  } finally {
    clearTimeout(timer);
  }

  if (resp.status === 401) {
    await clearSession();
    throw new ApiError(401, "HET_PHIEN", "Phiên đăng nhập đã hết hạn");
  }
  if (resp.status === 403) {
    throw new ApiError(403, "KHONG_DU_QUYEN", "Bạn không có quyền xem bảng điều hành");
  }
  if (!resp.ok) {
    throw new ApiError(resp.status, "LOI_MAY_CHU", `Lỗi máy chủ (${resp.status})`);
  }
  return (await resp.json()) as T;
}
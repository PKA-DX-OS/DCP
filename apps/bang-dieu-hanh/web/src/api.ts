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

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const token = await getValidToken();
  if (!token) {
    await login();
    throw new ApiError(401, "CHUA_DANG_NHAP", "Cần đăng nhập");
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const headers: Record<string, string> = { Authorization: `Bearer ${token}`, Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
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

  let chiTiet = "";
  if (!resp.ok) {
    try {
      const loi = (await resp.json()) as { detail?: string | { loi?: string } };
      chiTiet = typeof loi?.detail === "string" ? loi.detail : (loi?.detail?.loi ?? "");
    } catch {
      /* body không phải JSON: dùng thông báo mặc định */
    }
  }
  if (resp.status === 403) {
    throw new ApiError(403, "KHONG_DU_QUYEN", chiTiet || "Bạn không có quyền xem nội dung này");
  }
  if (!resp.ok) {
    throw new ApiError(resp.status, "LOI_MAY_CHU", chiTiet || `Lỗi máy chủ (${resp.status})`);
  }
  return (await resp.json()) as T;
}

/** Chỉ đọc chỉ số và phả hệ. */
export function apiGet<T>(path: string): Promise<T> {
  return request<T>("GET", path);
}

/** Chỉ dùng cho hỏi đáp trợ lý; không ghi dữ liệu nghiệp vụ. */
export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>("POST", path, body);
}

/** Tải tệp xuất (Excel/PDF) kèm token, trả Blob để trình duyệt lưu. */
export async function apiDownload(path: string): Promise<Blob> {
  const token = await getValidToken();
  if (!token) {
    await login();
    throw new ApiError(401, "CHUA_DANG_NHAP", "Cần đăng nhập");
  }
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "*/*" },
  });
  if (!resp.ok) throw new ApiError(resp.status, "LOI_TAI_TEP", `Không tải được tệp (${resp.status})`);
  return await resp.blob();
}

/** Lưu Blob thành tệp trên máy người dùng. */
export function luuBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
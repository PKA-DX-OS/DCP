// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Client HTTP dùng chung cho mọi lời gọi API của web cấp phép:
 * gốc API từ cấu hình, timeout, thử lại có giới hạn (chỉ với lời gọi đọc),
 * xử lý 401 và lỗi mạng thống nhất.
 */
import { API_BASE } from "../config";

export class ApiError extends Error {
  status: number;
  data: any;
  docErrors?: any[];

  constructor(message: string, status: number, data: any = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export interface RequestOptions {
  token?: string;
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  /** Thân JSON; bỏ qua khi có `form`. */
  body?: unknown;
  form?: FormData;
  accept?: string;
  /** Mặc định 15 giây; tải tệp nên đặt dài hơn. */
  timeoutMs?: number;
  /** Số lần thử lại khi lỗi mạng/timeout/5xx. Mặc định 2 cho GET, 0 cho lời gọi ghi. */
  retries?: number;
  /** Header bổ sung (ví dụ Idempotency-Key); không ghi đè Authorization/Accept. */
  headers?: Record<string, string>;
}

const DEFAULT_TIMEOUT_MS = 15_000;
const SESSION_EXPIRED = "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.";
const NETWORK_ERROR = "Không kết nối được máy chủ. Kiểm tra mạng và thử lại.";

/** Ghép đường dẫn tương đối ("/rest/...") với gốc API; giữ nguyên URL tuyệt đối. */
export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Gửi yêu cầu, trả Response gốc (dùng cho tải tệp). Lỗi mạng ném ApiError(status 0). */
export async function apiRequest(path: string, opts: RequestOptions = {}): Promise<Response> {
  const method = opts.method || "GET";
  const retries = opts.retries ?? (method === "GET" ? 2 : 0);
  const headers: Record<string, string> = { Accept: opts.accept || "application/json" };
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;
  if (opts.headers) {
    for (const [ten, giaTri] of Object.entries(opts.headers)) {
      if (ten.toLowerCase() !== "authorization" && ten.toLowerCase() !== "accept") headers[ten] = giaTri;
    }
  }
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  for (let attempt = 0; ; attempt++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? DEFAULT_TIMEOUT_MS);
    try {
      const resp = await fetch(apiUrl(path), { method, headers, body, signal: ctrl.signal });
      if (resp.status >= 500 && attempt < retries) {
        await sleep(300 * 2 ** attempt);
        continue;
      }
      return resp;
    } catch {
      if (attempt < retries) {
        await sleep(300 * 2 ** attempt);
        continue;
      }
      throw new ApiError(NETWORK_ERROR, 0);
    } finally {
      clearTimeout(timer);
    }
  }
}

/** Đọc lỗi từ phản hồi (PostgREST: message; FastAPI: detail.loi) thành ApiError. */
export async function toApiError(resp: Response, fallback: string): Promise<ApiError> {
  const text = await resp.text().catch(() => "");
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  const detail = data?.detail;
  const message =
    resp.status === 401
      ? SESSION_EXPIRED
      : data?.message ||
        data?.loi ||
        (typeof detail === "string" ? detail : detail?.loi) ||
        (data === null && text && text.length < 300 ? text : "") ||
        `${fallback}: HTTP ${resp.status}`;
  return new ApiError(message, resp.status, data ?? text);
}

/** Gửi yêu cầu và trả JSON; phản hồi lỗi ném ApiError với thông điệp thống nhất. */
export async function apiJson<T = any>(path: string, opts: RequestOptions, fallback: string): Promise<T> {
  const resp = await apiRequest(path, opts);
  if (!resp.ok) throw await toApiError(resp, fallback);
  if (resp.status === 204) return null as T;
  const text = await resp.text();
  return (text ? JSON.parse(text) : null) as T;
}

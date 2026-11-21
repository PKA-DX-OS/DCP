// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { ApiError, apiJson } from "./client";

export type LoaiGiayTo = "cccd" | "giay_chung_nhan_qsdd" | "don_de_nghi_cap_phep";
export type TrangThaiTrichXuat = "queued" | "processing" | "needs_review" | "confirmed" | "rejected" | "failed";

export interface TrichXuatTomTat {
  id: string;
  file_id: string;
  dossier_id: string | null;
  doc_type: LoaiGiayTo;
  status: TrangThaiTrichXuat;
  confidence: number | null;
  created_at: string;
}

export interface TruongTrichXuat {
  name: string;
  value: string | null;
  confidence: number;
  page?: number;
  bbox?: number[] | null;
  edited?: boolean;
}

export interface TrichXuat extends TrichXuatTomTat {
  fields: TruongTrichXuat[];
  reviewed_by: string | null;
  reviewed_at: string | null;
  reject_reason: string | null;
  error?: string | null;
}

export interface TrangTrichXuat {
  items: TrichXuatTomTat[];
  page: number;
  page_size: number;
  total: number;
}

export interface ThamSoHangCho {
  status?: TrangThaiTrichXuat;
  doc_type?: LoaiGiayTo;
  max_confidence?: number;
  dossier_id?: string;
  page?: number;
  page_size?: number;
}

export interface KetQuaOcr<T> {
  data: T;
  source: "api" | "mock";
}

const OCR_TIMEOUT_MS = 6_000;

function maIdempotency(): string {
  return globalThis.crypto?.randomUUID?.() || `ocr-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** Hàng chờ duyệt; API chưa có thì trả dữ liệu mẫu của hợp đồng, có nhãn ở giao diện. */
export async function fetchOcrQueue(token: string, params: ThamSoHangCho = {}): Promise<KetQuaOcr<TrangTrichXuat>> {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.doc_type) qs.set("doc_type", params.doc_type);
  if (params.max_confidence !== undefined) qs.set("max_confidence", String(params.max_confidence));
  if (params.dossier_id) qs.set("dossier_id", params.dossier_id);
  qs.set("page", String(params.page || 1));
  qs.set("page_size", String(params.page_size || 20));
  try {
    const data = await apiJson<TrangTrichXuat>(
      `/ocr?${qs.toString()}`,
      { token, timeoutMs: OCR_TIMEOUT_MS, retries: 0 },
      "Lỗi tải hàng chờ OCR",
    );
    return { data, source: "api" };
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) throw e;
    return { data: locMockOcr(params), source: "mock" };
  }
}

/** Chi tiết trích xuất kèm giá trị trường; chỉ fallback mock khi hàng chờ cũng đang mock. */
export async function fetchOcrDetail(
  token: string,
  id: string,
  choPhepMock = true,
): Promise<KetQuaOcr<TrichXuat>> {
  try {
    const data = await apiJson<TrichXuat>(
      `/ocr/${encodeURIComponent(id)}`,
      { token, timeoutMs: OCR_TIMEOUT_MS, retries: 0 },
      "Lỗi tải chi tiết OCR",
    );
    return { data, source: "api" };
  } catch (e) {
    if (!choPhepMock || (e instanceof ApiError && (e.status === 401 || e.status === 403))) throw e;
    const detail = MOCK_CHI_TIET[id];
    if (!detail) throw e;
    return { data: banSao(detail), source: "mock" };
  }
}

/** Cán bộ xác nhận; có thể sửa giá trị trường. Không tự ghi vào hồ sơ. */
export async function confirmOcr(
  token: string,
  id: string,
  fields: { name: string; value: string | null }[],
): Promise<TrichXuat> {
  return apiJson<TrichXuat>(
    `/ocr/${encodeURIComponent(id)}/confirm`,
    {
      token,
      method: "POST",
      body: { fields },
      headers: { "Idempotency-Key": maIdempotency() },
      timeoutMs: OCR_TIMEOUT_MS,
      retries: 0,
    },
    "Lỗi xác nhận OCR",
  );
}

/** Cán bộ từ chối trích xuất; lý do bắt buộc. */
export async function rejectOcr(token: string, id: string, reason: string): Promise<TrichXuat> {
  return apiJson<TrichXuat>(
    `/ocr/${encodeURIComponent(id)}/reject`,
    {
      token,
      method: "POST",
      body: { reason },
      headers: { "Idempotency-Key": maIdempotency() },
      timeoutMs: OCR_TIMEOUT_MS,
      retries: 0,
    },
    "Lỗi từ chối OCR",
  );
}

/** Xác nhận trên bản mô phỏng; không gửi máy chủ, không ghi vào hồ sơ thật. */
export function mockConfirmOcr(id: string, fields: { name: string; value: string | null }[]): TrichXuat {
  const detail = MOCK_CHI_TIET[id];
  if (!detail) throw new Error("Không có trích xuất mẫu");
  const theoTen = new Map(fields.map((f) => [f.name, f.value]));
  detail.fields = detail.fields.map((f) => {
    if (!theoTen.has(f.name)) return f;
    const giaTri = theoTen.get(f.name) ?? null;
    return { ...f, value: giaTri, edited: f.edited || giaTri !== f.value };
  });
  detail.status = "confirmed";
  detail.reviewed_by = "demo.mot-cua";
  detail.reviewed_at = new Date().toISOString();
  detail.reject_reason = null;
  capNhatTomTat(detail);
  return banSao(detail);
}

/** Từ chối trên bản mô phỏng; không gửi máy chủ. */
export function mockRejectOcr(id: string, reason: string): TrichXuat {
  const detail = MOCK_CHI_TIET[id];
  if (!detail) throw new Error("Không có trích xuất mẫu");
  detail.status = "rejected";
  detail.reviewed_by = "demo.mot-cua";
  detail.reviewed_at = new Date().toISOString();
  detail.reject_reason = reason;
  capNhatTomTat(detail);
  return banSao(detail);
}

function capNhatTomTat(detail: TrichXuat): void {
  const item = MOCK_HANG_CHO.find((x) => x.id === detail.id);
  if (!item) return;
  item.status = detail.status;
  item.confidence = detail.confidence;
}

function locMockOcr(params: ThamSoHangCho): TrangTrichXuat {
  const page = Math.max(1, Number(params.page) || 1);
  const pageSize = Math.min(100, Math.max(1, Number(params.page_size) || 20));
  const ds = MOCK_HANG_CHO.filter((x) => {
    if (params.status && x.status !== params.status) return false;
    if (params.doc_type && x.doc_type !== params.doc_type) return false;
    if (params.dossier_id && x.dossier_id !== params.dossier_id) return false;
    if (params.max_confidence !== undefined) {
      if (x.confidence === null || x.confidence > params.max_confidence) return false;
    }
    return true;
  });
  return {
    items: banSao(ds.slice((page - 1) * pageSize, page * pageSize)),
    page,
    page_size: pageSize,
    total: ds.length,
  };
}

function banSao<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

const MOCK_CHI_TIET: Record<string, TrichXuat> = {
  "00000000-0000-4000-8000-000000001001": {
    id: "00000000-0000-4000-8000-000000001001",
    file_id: "00000000-0000-4000-8000-000000001101",
    dossier_id: "00000000-0000-4000-8000-000000000101",
    doc_type: "giay_chung_nhan_qsdd",
    status: "needs_review",
    confidence: 0.71,
    created_at: "2026-11-20T09:00:00+07:00",
    fields: [
      { name: "so_thua", value: "125", confidence: 0.94, page: 1, bbox: [0.12, 0.31, 0.08, 0.03], edited: false },
      { name: "to_ban_do", value: "18", confidence: 0.91, page: 1, bbox: [0.32, 0.31, 0.06, 0.03], edited: false },
      { name: "dien_tich_m2", value: "82,5", confidence: 0.48, page: 1, bbox: [0.12, 0.36, 0.1, 0.03], edited: false },
    ],
    reviewed_by: null,
    reviewed_at: null,
    reject_reason: null,
    error: null,
  },
  "00000000-0000-4000-8000-000000001002": {
    id: "00000000-0000-4000-8000-000000001002",
    file_id: "00000000-0000-4000-8000-000000001102",
    dossier_id: "00000000-0000-4000-8000-000000000102",
    doc_type: "cccd",
    status: "needs_review",
    confidence: 0.42,
    created_at: "2026-11-20T10:15:00+07:00",
    fields: [
      { name: "ho_ten", value: "Nguyễn Văn Mẫu", confidence: 0.55, page: 1, bbox: [0.18, 0.22, 0.28, 0.05], edited: false },
      { name: "so_cccd", value: "001099123459", confidence: 0.43, page: 1, bbox: [0.18, 0.3, 0.22, 0.04], edited: false },
      { name: "dia_chi", value: "12 Đường Mẫu, Phường Mẫu", confidence: 0.36, page: 1, bbox: [0.18, 0.39, 0.44, 0.05], edited: false },
    ],
    reviewed_by: null,
    reviewed_at: null,
    reject_reason: null,
    error: null,
  },
  "00000000-0000-4000-8000-000000001003": {
    id: "00000000-0000-4000-8000-000000001003",
    file_id: "00000000-0000-4000-8000-000000001103",
    dossier_id: "00000000-0000-4000-8000-000000000103",
    doc_type: "don_de_nghi_cap_phep",
    status: "confirmed",
    confidence: 0.93,
    created_at: "2026-11-19T14:00:00+07:00",
    fields: [
      { name: "ho_ten", value: "Trần Thị Mẫu", confidence: 0.97, page: 1, edited: false },
      { name: "so_thua", value: "88", confidence: 0.9, page: 1, edited: true },
      { name: "dien_tich_m2", value: "120", confidence: 0.88, page: 1, edited: false },
    ],
    reviewed_by: "mot-cua.mau",
    reviewed_at: "2026-11-19T14:10:00+07:00",
    reject_reason: null,
    error: null,
  },
  "00000000-0000-4000-8000-000000001004": {
    id: "00000000-0000-4000-8000-000000001004",
    file_id: "00000000-0000-4000-8000-000000001104",
    dossier_id: null,
    doc_type: "cccd",
    status: "queued",
    confidence: null,
    created_at: "2026-11-20T11:00:00+07:00",
    fields: [],
    reviewed_by: null,
    reviewed_at: null,
    reject_reason: null,
    error: null,
  },
  "00000000-0000-4000-8000-000000001005": {
    id: "00000000-0000-4000-8000-000000001005",
    file_id: "00000000-0000-4000-8000-000000001105",
    dossier_id: "00000000-0000-4000-8000-000000000105",
    doc_type: "don_de_nghi_cap_phep",
    status: "rejected",
    confidence: 0.38,
    created_at: "2026-11-18T08:30:00+07:00",
    fields: [{ name: "ho_ten", value: "Lê Văn Mẫu", confidence: 0.31, page: 1, edited: false }],
    reviewed_by: "mot-cua.mau",
    reviewed_at: "2026-11-18T08:40:00+07:00",
    reject_reason: "Ảnh mờ, không đọc được họ tên",
    error: null,
  },
};

const MOCK_HANG_CHO: TrichXuatTomTat[] = Object.values(MOCK_CHI_TIET).map((x) => ({
  id: x.id,
  file_id: x.file_id,
  dossier_id: x.dossier_id,
  doc_type: x.doc_type,
  status: x.status,
  confidence: x.confidence,
  created_at: x.created_at,
}));

const MOCK_CHI_TIET_GOC = banSao(MOCK_CHI_TIET);
const MOCK_HANG_CHO_GOC = banSao(MOCK_HANG_CHO);

/** Dùng cho test hoặc khi cần trả dữ liệu mẫu về trạng thái ban đầu. */
export function datLaiMockOcr(): void {
  for (const key of Object.keys(MOCK_CHI_TIET)) delete MOCK_CHI_TIET[key];
  Object.assign(MOCK_CHI_TIET, banSao(MOCK_CHI_TIET_GOC));
  MOCK_HANG_CHO.splice(0, MOCK_HANG_CHO.length, ...banSao(MOCK_HANG_CHO_GOC));
}

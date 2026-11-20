// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiJson } from "./client";

export interface AuthorityResult {
  xac_dinh_duoc?: boolean;
  co_quan_cap?: string;
  nguoi_ky?: string;
  doi_tuong?: string;
  trong_kcn?: boolean;
  cap_cong_trinh?: string | null;
  legal_citation_key?: string;
  [key: string]: any;
}

export interface LocationResult {
  found: boolean;
  ma_dinh_danh: string;
  can_reuse: boolean;
  source?: string;
  da_kiem_chung?: boolean;
  data?: Record<string, any>;
  message?: string;
}

export async function fetchDossierAuthority(token: string, hoSoId: string): Promise<AuthorityResult> {
  return apiJson(`/planning/authority/${encodeURIComponent(hoSoId)}`, { token }, "Lỗi kiểm tra thẩm quyền");
}

export async function lookupLocation(token: string, maDinhDanh: string): Promise<LocationResult> {
  return apiJson(`/planning/location/${encodeURIComponent(maDinhDanh)}`, { token }, "Lỗi tra cứu địa điểm");
}

export async function attachDossierLocation(token: string, hoSoId: string, maDinhDanh: string): Promise<any> {
  return apiJson(
    `/planning/location/ho-so/${encodeURIComponent(hoSoId)}`,
    { token, method: "POST", body: { ma_dinh_danh: maDinhDanh } },
    "Lỗi gắn mã định danh địa điểm",
  );
}

export async function fetchFees(token: string): Promise<any[]> {
  return apiJson("/planning/fees", { token }, "Lỗi tải biểu phí");
}

export async function createFee(token: string, body: Record<string, any>): Promise<any> {
  return apiJson("/planning/fees", { token, method: "POST", body }, "Lỗi tạo biểu phí");
}

export async function fetchReceipts(token: string): Promise<any[]> {
  return apiJson("/planning/bien-lai", { token }, "Lỗi tải biên lai");
}

export async function createReceipt(token: string, body: Record<string, any>): Promise<any> {
  return apiJson("/planning/bien-lai", { token, method: "POST", body }, "Lỗi tạo biên lai");
}

export async function updateReceiptStatus(
  token: string,
  receiptId: string,
  status: "da_doi_soat" | "hoan_phi" | "huy",
  note = "",
): Promise<any> {
  return apiJson(
    `/planning/bien-lai/${encodeURIComponent(receiptId)}/status`,
    { token, method: "POST", body: { trang_thai: status, ghi_chu: note || null } },
    "Lỗi cập nhật biên lai",
  );
}

export async function fetchArchive(token: string): Promise<any[]> {
  return apiJson("/planning/archive", { token }, "Lỗi tải danh sách lưu trữ");
}

export async function createArchive(token: string, hoSoId: string, body: Record<string, any>): Promise<any> {
  return apiJson(
    `/planning/archive/${encodeURIComponent(hoSoId)}`,
    { token, method: "POST", body },
    "Lỗi tạo bản ghi lưu trữ",
  );
}

export async function updateArchiveStatus(
  token: string,
  archiveId: string,
  status: "dang_luu_tru" | "chuyen_giao" | "tieu_huy" | "het_han",
  note = "",
): Promise<any> {
  return apiJson(
    `/planning/archive/${encodeURIComponent(archiveId)}/status`,
    { token, method: "POST", body: { trang_thai: status, ghi_chu: note || null } },
    "Lỗi cập nhật lưu trữ",
  );
}

export async function shareDossierData(token: string, body: Record<string, any>): Promise<any> {
  return apiJson("/planning/share/export", { token, method: "POST", body }, "Lỗi tạo bản ghi chia sẻ dữ liệu");
}

export async function fetchShareLogs(token: string): Promise<any[]> {
  return apiJson("/planning/share/logs?limit=200", { token }, "Lỗi tải nhật ký chia sẻ");
}

export async function fetchSharePayload(token: string, hoSoId: string): Promise<any> {
  return apiJson(
    `/planning/share/payload/${encodeURIComponent(hoSoId)}`,
    { token },
    "Lỗi tạo payload chia sẻ",
  );
}

export interface LegalDocument {
  document_id: string;
  code: string;
  title: string;
  doc_type: string;
  issuer: string;
  issued_date?: string | null;
  effective_date?: string | null;
  status: string;
  status_detail?: string | null;
  group_name?: string | null;
  source_url?: string | null;
  sha256?: string | null;
  file_name?: string | null;
  notes?: string | null;
  tags?: string | string[] | null;
}

export interface LegalCitation {
  citation_key: string;
  document_id: string;
  document_code?: string;
  document_title?: string;
  article?: string | null;
  clause?: string | null;
  point?: string | null;
  topic?: string | null;
  summary?: string | null;
  effective_date?: string | null;
  status?: string | null;
  source_url?: string | null;
  sha256?: string | null;
  can_doi_chieu?: boolean;
}

export async function fetchLegalDocuments(token: string, q = ""): Promise<LegalDocument[]> {
  const query = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : "";
  return apiJson<LegalDocument[]>(`/planning/legal/documents${query}`, { token }, "Lỗi tải danh mục văn bản pháp luật");
}

export async function fetchLegalDocument(token: string, documentId: string): Promise<LegalDocument & { citations: LegalCitation[] }> {
  return apiJson(
    `/planning/legal/documents/${encodeURIComponent(documentId)}`,
    { token },
    "Lỗi tải chi tiết văn bản pháp luật",
  );
}

export async function fetchLegalCitationList(
  token: string,
  topic = "",
  documentId = "",
): Promise<LegalCitation[]> {
  const params = new URLSearchParams();
  if (topic.trim()) params.set("topic", topic.trim());
  if (documentId) params.set("document_id", documentId);
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiJson<LegalCitation[]>(`/planning/legal/citations${query}`, { token }, "Lỗi tải trích dẫn pháp lý");
}

export async function checkAuthority(token: string, body: Record<string, any>): Promise<AuthorityResult> {
  return apiJson("/planning/authority/check", { token, method: "POST", body }, "Lỗi kiểm tra thẩm quyền");
}

export async function revokeSignedDocument(token: string, docId: string, reason: string): Promise<any> {
  return apiJson(
    `/docs/${encodeURIComponent(docId)}/revoke`,
    { token, method: "POST", body: { ly_do: reason } },
    "Lỗi thu hồi văn bản đã ký",
  );
}

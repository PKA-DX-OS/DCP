// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiJson } from "./client";

/** Đồng ý thu thập dữ liệu của chính người dùng; lỗi thì trả danh sách rỗng. */
export async function fetchConsents(token: string): Promise<any[]> {
  try {
    return await apiJson<any[]>("/rest/consents?order=granted_at.desc", { token }, "Lỗi tải đồng ý dữ liệu");
  } catch {
    return [];
  }
}

export async function fetchDsarRequests(token: string): Promise<any[]> {
  try {
    return await apiJson<any[]>("/rest/dsar_requests?order=received_at.desc", { token }, "Lỗi tải yêu cầu dữ liệu");
  } catch {
    return [];
  }
}

export async function grantConsent(token: string, purpose: string, textVersion = "v1.0"): Promise<any> {
  return apiJson(
    "/rest/rpc/dong_y_du_lieu",
    { token, method: "POST", body: { p_purpose: purpose, p_text_version: textVersion } },
    "Lỗi đồng ý dữ liệu",
  );
}

export async function withdrawConsent(token: string, purpose: string): Promise<any> {
  return apiJson(
    "/rest/rpc/rut_dong_y_du_lieu",
    { token, method: "POST", body: { p_purpose: purpose } },
    "Lỗi rút đồng thuận",
  );
}

/** Gửi yêu cầu về dữ liệu cá nhân (truy cập/xuất, xóa...) theo DSAR. */
export async function submitDsarRequest(token: string, type: string, note = ""): Promise<any> {
  return apiJson(
    "/rest/rpc/gui_yeu_cau_dsar",
    { token, method: "POST", body: { p_type: type, p_legal_basis_note: note } },
    "Lỗi gửi yêu cầu DSAR",
  );
}

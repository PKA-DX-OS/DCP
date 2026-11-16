// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

export async function fetchConsents(token: string): Promise<any[]> {
  const resp = await fetch("/api/v1/rest/consents?order=granted_at.desc", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!resp.ok) {
    return [];
  }
  return await resp.json();
}

export async function fetchDsarRequests(token: string): Promise<any[]> {
  const resp = await fetch("/api/v1/rest/dsar_requests?order=received_at.desc", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!resp.ok) {
    return [];
  }
  return await resp.json();
}

export async function grantConsent(token: string, purpose: string, textVersion = "v1.0"): Promise<any> {
  const resp = await fetch("/api/v1/rest/rpc/dong_y_du_lieu", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ p_purpose: purpose, p_text_version: textVersion }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.message || `Lỗi đồng ý dữ liệu: HTTP ${resp.status}`);
  }
  return await resp.json();
}

export async function withdrawConsent(token: string, purpose: string): Promise<any> {
  const resp = await fetch("/api/v1/rest/rpc/rut_dong_y_du_lieu", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ p_purpose: purpose }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.message || `Lỗi rút đồng thuận: HTTP ${resp.status}`);
  }
  return await resp.json();
}

export async function submitDsarRequest(token: string, type: string, note = ""): Promise<any> {
  const resp = await fetch("/api/v1/rest/rpc/gui_yeu_cau_dsar", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ p_type: type, p_legal_basis_note: note }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.message || `Lỗi gửi yêu cầu DSAR: HTTP ${resp.status}`);
  }
  return await resp.json();
}

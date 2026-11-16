// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { DocError, DocPayload, DocRequirement, HoSo, HoSoDetail, NopHoSoPayload } from "../types";

export async function fetchHoSo(token: string): Promise<HoSo[]> {
  const resp = await fetch("/api/v1/rest/v_ho_so?order=created_at.desc&limit=100", {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });
  if (!resp.ok) {
    if (resp.status === 401) {
      throw new Error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
    }
    throw new Error(`Lỗi tải danh sách hồ sơ: HTTP ${resp.status}`);
  }
  return await resp.json();
}

export async function fetchHoSoDetail(token: string, id: string): Promise<HoSoDetail> {
  const resp = await fetch(`/api/v1/rest/v_ho_so?id=eq.${id}&select=*,ho_so_tep(*)`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.pgrst.object+json",
    },
  });
  if (!resp.ok) {
    throw new Error(`Lỗi tải chi tiết hồ sơ: HTTP ${resp.status}`);
  }
  return await resp.json();
}

export async function fetchDocumentRequirements(token: string): Promise<DocRequirement[]> {
  const resp = await fetch("/api/v1/rest/document_requirements?order=thu_tu.asc", {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });
  if (!resp.ok) {
    throw new Error(`Lỗi tải manifest giấy tờ: HTTP ${resp.status}`);
  }
  return await resp.json();
}

export async function nopHoSo(
  token: string,
  payload: NopHoSoPayload,
  hoSoId: string,
  tep: DocPayload[],
): Promise<any> {
  const resp = await fetch("/api/v1/rest/rpc/nop_ho_so", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ho_ten: payload.ho_ten,
      cccd: payload.cccd,
      dien_thoai: payload.dien_thoai,
      dia_chi_cong_trinh: payload.dia_chi_cong_trinh,
      thua_dat: payload.thua_dat,
      so_tang: Number(payload.so_tang) || 1,
      dien_tich_san_m2: Number(payload.dien_tich_san_m2) || 100.0,
      khu_quan_ly_kien_truc: Boolean(payload.khu_quan_ly_kien_truc),
      p_ho_so_id: hoSoId,
      p_tep: tep,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    const error: any = new Error(err.message || `Lỗi nộp hồ sơ: HTTP ${resp.status}`);
    error.status = resp.status;
    if (typeof err.details === "string") {
      try {
        const parsed = JSON.parse(err.details);
        if (Array.isArray(parsed)) {
          error.docErrors = parsed as DocError[];
        }
      } catch {
        // details không phải JSON: giữ nguyên message
      }
    }
    throw error;
  }
  return await resp.json();
}

export async function reviewDossierFile(
  token: string,
  tepId: string,
  trangThai: "dat" | "khong_dat",
  lyDo = "",
): Promise<any> {
  const resp = await fetch("/api/v1/rest/rpc/danh_gia_tep", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      p_tep_id: tepId,
      p_trang_thai: trangThai,
      p_ly_do: lyDo || null,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.message || `Lỗi đánh giá tệp: HTTP ${resp.status}`);
  }
  return await resp.json();
}

export async function supplementHoSo(token: string, payload: any): Promise<any> {
  const resp = await fetch("/api/v1/rest/rpc/bo_sung_ho_so", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.message || `Lỗi bổ sung hồ sơ: HTTP ${resp.status}`);
  }
  return await resp.json();
}

export async function openHoSo(token: string, idOrCode: string): Promise<any> {
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(idOrCode.trim());
  const body = isUuid ? { p_id: idOrCode.trim() } : { p_ma_ho_so: idOrCode.trim() };
  const resp = await fetch("/api/v1/rest/rpc/mo_ho_so", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    const error: any = new Error(err.message || err.loi || `HTTP ${resp.status}`);
    error.status = resp.status;
    error.data = err;
    throw error;
  }
  const data = await resp.json();
  if (data && data.can_xin_truy_cap_khan) {
    const error: any = new Error(data.loi || "Không có quyền truy cập");
    error.status = 403;
    error.data = data;
    throw error;
  }
  return data;
}

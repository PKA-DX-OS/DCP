// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { AuditLogEntry, DocError, DocPayload, DocRequirement, HoSo, NopHoSoPayload } from "../types";
import { ApiError, apiJson } from "./client";

export async function fetchHoSo(token: string): Promise<HoSo[]> {
  return apiJson<HoSo[]>("/rest/v_ho_so?order=created_at.desc&limit=100", { token }, "Lỗi tải danh sách hồ sơ");
}

/** Tệp đính kèm của một hồ sơ (mới nhất trước). */
export async function fetchDossierFiles(token: string, hoSoId: string): Promise<any[]> {
  return apiJson<any[]>(
    `/rest/v_ho_so_tep?ho_so_id=eq.${encodeURIComponent(hoSoId)}&order=created_at.desc`,
    { token },
    "Lỗi tải tệp hồ sơ",
  );
}

/** Nhật ký xử lý của hồ sơ, theo thứ tự thời gian từ RPC lay_nhat_ky_ho_so. */
export async function fetchDossierHistory(token: string, hoSoId: string): Promise<AuditLogEntry[]> {
  return apiJson<AuditLogEntry[]>(
    "/rest/rpc/lay_nhat_ky_ho_so",
    { token, method: "POST", body: { p_ho_so_id: hoSoId } },
    "Lỗi tải lịch sử xử lý",
  );
}

/** Thông tin giấy phép đã cấp của hồ sơ (RPC thong_tin_giay_phep). */
export async function fetchPermitInfo(token: string, hoSoId: string): Promise<any> {
  return apiJson<any>(
    "/rest/rpc/thong_tin_giay_phep",
    { token, method: "POST", body: { p_ho_so_id: hoSoId } },
    "Lỗi tải thông tin giấy phép",
  );
}

export async function fetchDocumentRequirements(token: string): Promise<DocRequirement[]> {
  return apiJson<DocRequirement[]>("/rest/document_requirements?order=thu_tu.asc", { token }, "Lỗi tải manifest giấy tờ");
}

export async function nopHoSo(
  token: string,
  payload: NopHoSoPayload,
  hoSoId: string,
  tep: DocPayload[],
): Promise<any> {
  try {
    return await apiJson(
      "/rest/rpc/nop_ho_so",
      {
        token,
        method: "POST",
        body: {
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
        },
      },
      "Lỗi nộp hồ sơ",
    );
  } catch (e) {
    // PostgREST trả danh sách lỗi giấy tờ (JSON) trong `details`
    if (e instanceof ApiError && typeof e.data?.details === "string") {
      try {
        const parsed = JSON.parse(e.data.details);
        if (Array.isArray(parsed)) e.docErrors = parsed as DocError[];
      } catch {
        // details không phải JSON: giữ nguyên message
      }
    }
    throw e;
  }
}

export async function reviewDossierFile(
  token: string,
  tepId: string,
  trangThai: "dat" | "khong_dat",
  lyDo = "",
): Promise<any> {
  return apiJson(
    "/rest/rpc/danh_gia_tep",
    { token, method: "POST", body: { p_tep_id: tepId, p_trang_thai: trangThai, p_ly_do: lyDo || null } },
    "Lỗi đánh giá tệp",
  );
}

export async function supplementHoSo(token: string, payload: any): Promise<any> {
  return apiJson("/rest/rpc/bo_sung_ho_so", { token, method: "POST", body: payload }, "Lỗi bổ sung hồ sơ");
}

export async function updateSubjectAuthority(
  token: string,
  hoSoId: string,
  payload: { doi_tuong?: string; trong_kcn?: boolean; cap_hanh_chinh?: string },
): Promise<any> {
  return apiJson(
    "/rest/rpc/cap_nhat_thong_tin_tham_quyen",
    {
      token,
      method: "POST",
      body: {
        p_ho_so_id: hoSoId,
        p_doi_tuong: payload.doi_tuong || null,
        p_loai_cong_trinh: "nha_o_rieng_le",
        p_cap_cong_trinh: null,
        p_trong_kcn: payload.trong_kcn ?? null,
        p_cap_hanh_chinh: payload.cap_hanh_chinh || null,
      },
    },
    "Lỗi cập nhật thông tin thẩm quyền",
  );
}

export async function openHoSo(token: string, idOrCode: string): Promise<any> {
  const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(idOrCode.trim());
  const body = isUuid ? { p_id: idOrCode.trim() } : { p_ma_ho_so: idOrCode.trim() };
  const data = await apiJson<any>("/rest/rpc/mo_ho_so", { token, method: "POST", body }, "Lỗi mở hồ sơ");
  if (data && data.can_xin_truy_cap_khan) {
    throw new ApiError(data.loi || "Không có quyền truy cập", 403, data);
  }
  return data;
}

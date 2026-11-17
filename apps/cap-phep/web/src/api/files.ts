// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiJson, apiRequest, toApiError } from "./client";

/** Tải tệp lên dịch vụ files (quét virus, cách ly); cho phép tới 2 phút. */
export async function uploadFile(token: string, file: File, objectType: string, objectId: string): Promise<any> {
  const form = new FormData();
  form.append("file", file);
  form.append("object_type", objectType);
  form.append("object_id", objectId);
  return apiJson("/files", { token, method: "POST", form, timeoutMs: 120_000 }, "Lỗi tải tệp");
}

/** Tải nội dung một tệp (giấy phép, tài liệu) dưới dạng Blob. */
export async function downloadFile(token: string, pathOrUrl: string): Promise<Blob> {
  const resp = await apiRequest(pathOrUrl, { token, accept: "*/*", timeoutMs: 120_000 });
  if (!resp.ok) throw await toApiError(resp, "Lỗi tải tệp");
  return await resp.blob();
}

export async function linkDossierFile(
  token: string,
  hoSoId: string,
  fileId: string,
  loaiTep = "tai_lieu_bo_sung",
  ngayCap?: string,
  ngayHetHan?: string,
  thongTin?: Record<string, string>,
): Promise<any> {
  return apiJson(
    "/rest/rpc/dinh_kem_tep",
    {
      token,
      method: "POST",
      body: {
        p_ho_so_id: hoSoId,
        p_file_id: fileId,
        p_loai: loaiTep,
        p_ngay_cap: ngayCap || null,
        p_ngay_het_han: ngayHetHan || null,
        p_thong_tin: thongTin || {},
      },
    },
    "Lỗi liên kết tệp",
  );
}

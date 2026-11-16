// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

export async function uploadFile(token: string, file: File, objectType: string, objectId: string): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("object_type", objectType);
  formData.append("object_id", objectId);
  const resp = await fetch("/api/v1/files", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.message || err.detail?.loi || `Lỗi tải tệp: HTTP ${resp.status}`);
  }
  return await resp.json();
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
  const resp = await fetch("/api/v1/rest/rpc/dinh_kem_tep", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      p_ho_so_id: hoSoId,
      p_file_id: fileId,
      p_loai: loaiTep,
      p_ngay_cap: ngayCap || null,
      p_ngay_het_han: ngayHetHan || null,
      p_thong_tin: thongTin || {},
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.message || `Lỗi liên kết tệp: HTTP ${resp.status}`);
  }
  return await resp.json();
}

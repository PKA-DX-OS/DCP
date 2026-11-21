// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

export type NguonLienNganh = "dan_cu" | "dat_dai" | "thue" | "pccc";

export type TrangThaiDoiChieu = "khop" | "khong_khop" | "khong_thay";

export interface TruongDuLieu {
  nhan: string;
  gia_tri: string;
}

export interface KetQuaTraCuu {
  nguon: NguonLienNganh;
  he_thong: string;
  trang_thai: TrangThaiDoiChieu;
  do_tin_cay: number;
  mo_ta: string;
  truong: TruongDuLieu[];
  /** UUID giả lập để sẵn sàng gửi API liên kết MDM khi D triển khai. */
  mdm_id: string;
}

export interface LienKetMDM {
  dossier_id: string;
  subject: { type: string; id: string; nhan: string; confidence: number } | null;
  parcel: { type: string; id: string; nhan: string; confidence: number } | null;
  construction: { type: string; id: string; nhan: string; confidence: number } | null;
  permit: { type: string; id: string; nhan: string; confidence: number } | null;
}

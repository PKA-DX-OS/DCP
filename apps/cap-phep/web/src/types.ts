// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

export type TrangThaiHoSo =
  | "MOI_TAO"
  | "DA_NOP"
  | "TIEP_NHAN"
  | "CAN_BO_SUNG"
  | "DUOC_PHAN_CONG"
  | "DANG_THAM_DINH"
  | "YEU_CAU_BO_SUNG"
  | "CHO_DUYET"
  | "CHO_PHE_DUYET"
  | "CHO_KY"
  | "DA_CAP"
  | "DA_CAP_PHEP"
  | "TU_CHOI";

export interface User {
  sub: string;
  name?: string;
  email?: string;
  preferred_username?: string;
  roles: string[];
  tenant: string;
  access_token?: string;
}

export interface HoSo {
  id: string;
  ma_ho_so: string;
  tenant: string;
  tenant_id?: string;
  chu_dau_tu_sub?: string;
  chu_dau_tu_id?: string;
  ho_ten: string;
  ten_chu_dau_tu?: string;
  cccd: string;
  so_cccd?: string;
  dien_thoai: string;
  dia_chi_cong_trinh: string;
  dia_chi_thua_dat?: string;
  thua_dat: string;
  so_tang: number;
  dien_tich_san_m2: number;
  dien_tich_xay_dung?: number;
  khu_quan_ly_kien_truc?: boolean;
  chieu_cao_cong_trinh?: number;
  he_so_su_dung_dat?: number;
  khoang_lui_truoc?: number;
  trang_thai: TrangThaiHoSo;
  buoc?: string;
  han_buoc_at?: string;
  qua_han?: boolean;
  han_tong_at?: string;
  process_instance_id?: string;
  ly_do_bo_sung?: string;
  nguoi_tiep_nhan?: string;
  nguoi_tham_dinh?: string;
  nguoi_phe_duyet?: string;
  created_at: string;
  updated_at: string;
  han_xu_ly?: string;
}

export interface NopHoSoPayload {
  ho_ten: string;
  cccd: string;
  dien_thoai: string;
  dia_chi_cong_trinh: string;
  thua_dat: string;
  so_tang?: number;
  dien_tich_san_m2?: number;
  khu_quan_ly_kien_truc?: boolean;
  doi_tuong?: "ho_gia_dinh_ca_nhan" | "to_chuc";
  trong_kcn?: boolean;
  cap_hanh_chinh?: "xa" | "tinh" | "";
}

export interface DocRequirement {
  loai: string;
  ten: string;
  bat_buoc: boolean;
  yeu_cau_hieu_luc: boolean;
  thong_tin: string[];
  mo_ta?: string | null;
  thu_tu: number;
}

export interface DocEntry {
  loai: string;
  file: File | null;
  ngay_cap: string;
  ngay_het_han: string;
  thong_tin: Record<string, string>;
}

export interface DocPayload {
  file_id: string;
  loai: string;
  ngay_cap?: string | null;
  ngay_het_han?: string | null;
  thong_tin?: Record<string, string>;
}

export interface DocError {
  field: string;
  loai_giay?: string | null;
  reason: string;
  action?: string;
}

export interface AuditLogEntry {
  id: string;
  event_time?: string;
  created_at?: string;
  actor_id?: string;
  actor_sub?: string;
  actor_type?: string;
  actor_role?: string;
  action: string;
  entity_type?: string;
  object_type?: string;
  entity_id?: string;
  object_id?: string;
  payload_hash?: string;
  prev_hash?: string;
  current_hash?: string;
  detail?: any;
}

/** Việc quy trình trả từ /flow/tasks (trường chính của Flowable; trường khác giữ nguyên). */
export interface FlowTask {
  id: string;
  name?: string;
  taskDefinitionKey?: string;
  processInstanceId?: string;
  businessKey?: string;
  assignee?: string | null;
  createTime?: string;
  dueDate?: string | null;
  variables?: Record<string, any>;
  [key: string]: any;
}

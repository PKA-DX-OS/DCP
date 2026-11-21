// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { ApiError, apiJson } from "./client";
import { fetchHoSo } from "./dossiers";

/** D? li?u 360 theo h?p d?ng contracts/dh/mdm.yaml. */
export interface HoSo360 {
  ho_so: {
    id: string;
    ma_ho_so: string;
    trang_thai: string;
    buoc: string;
    created_at: string;
    han_tong_at?: string | null;
    qua_han?: boolean;
  };
  chu_dau_tu: {
    subject_id: string;
    ho_ten: string;
    cccd_mask: string;
    dien_thoai_mask?: string | null;
    so_ho_so_khac?: number;
  } | null;
  thua_dat: {
    parcel_id: string;
    so_thua?: string | null;
    to_ban_do?: string | null;
    ma_dinh_danh_dia_diem?: string | null;
    dien_tich_m2?: number | null;
  } | null;
  cong_trinh: {
    construction_id: string;
    ma_cong_trinh: string;
    dia_chi?: string | null;
  } | null;
  giay_phep: {
    permit_id: string;
    so_giay_phep: string;
    public_code?: string | null;
    trang_thai: string;
    ngay_cap?: string | null;
  } | null;
  kiem_tra: { loai: string; ket_qua: string; thoi_diem: string; mo_ta?: string | null }[];
  tai_chinh: { loai: string; so_tien: number; trang_thai: string }[];
  canh_bao: { nguon: string; code: string; severity: string; message: string; field?: string | null }[];
  audit: { so_su_kien: number; gan_nhat?: string | null };
}

export interface MucTimKiem {
  type: string;
  id: string;
  nhan: string;
  phu: string | null;
  khop: "exact" | "prefix" | "fuzzy";
  diem: number;
  dossier_id: string | null;
}

export interface NhomTimKiem {
  type: string;
  total: number;
  items: MucTimKiem[];
}

export interface KetQuaTimKiem {
  groups: NhomTimKiem[];
  took_ms: number;
}

/** Nguồn dữ liệu H: API thật, tìm trong danh sách hồ sơ đang có, hoặc mock có nhãn. */
export type NguonDuLieu = "api" | "cuc-bo" | "mock";

export interface KetQuaApi<T> {
  data: T;
  source: NguonDuLieu;
}

const H_TIMEOUT_MS = 5_000;

/** Gọi API thật; lỗi/404 thì trả null để UI dùng dữ liệu hồ sơ hiện có. */
export async function fetchDossier360(token: string, hoSoId: string): Promise<HoSo360 | null> {
  try {
    return await apiJson<HoSo360>(
      `/mdm/dossiers/${encodeURIComponent(hoSoId)}/360`,
      { token, timeoutMs: H_TIMEOUT_MS, retries: 0 },
      "Lỗi tải dữ liệu 360 hồ sơ",
    );
  } catch {
    return null;
  }
}

/** Tìm toàn cục; nếu API chưa có thì tìm trong danh sách hồ sơ hiện có. */
export async function timKiemToanCuc(token: string, q: string): Promise<KetQuaApi<KetQuaTimKiem>> {
  const tuKhoa = q.trim();
  if (tuKhoa.length < 2) return { data: { groups: [], took_ms: 0 }, source: "cuc-bo" };
  try {
    const data = await apiJson<KetQuaTimKiem>(
      `/search?q=${encodeURIComponent(tuKhoa)}&limit=8`,
      { token, timeoutMs: H_TIMEOUT_MS, retries: 0 },
      "Lỗi tìm kiếm",
    );
    return { data, source: "api" };
  } catch (e) {
    // Hết phiên thì báo lỗi để người dùng đăng nhập lại; các lỗi khác mới dùng danh sách hiện có.
    if (e instanceof ApiError && e.status === 401) throw e;
    return { data: await timTrongDanhSach(token, tuKhoa), source: "cuc-bo" };
  }
}

async function timTrongDanhSach(token: string, q: string): Promise<KetQuaTimKiem> {
  const batDau = performance.now();
  let ds: any[] = [];
  try {
    ds = await fetchHoSo(token);
  } catch {
    ds = [];
  }
  const lower = q.toLocaleLowerCase("vi");
  const laCccd = /^\d{12}$/.test(q);
  const laDienThoai = /^\d{9,}$/.test(q);
  const muc: MucTimKiem[] = [];
  for (const h of ds) {
    const ma = String(h.ma_ho_so || "");
    const ten = String(h.ho_ten || "");
    const diaChi = String(h.dia_chi_cong_trinh || "");
    const cccd = String(h.cccd || "");
    const dienThoai = String(h.dien_thoai || "");
    const thua = String(h.thua_dat || "");
    const fields = [ma, ten, diaChi, cccd, dienThoai, thua];
    if (!fields.some((x) => x.toLocaleLowerCase("vi").includes(lower))) continue;
    if (laCccd) {
      if (cccd !== q) continue;
    } else if (laDienThoai && !dienThoai.includes(q)) {
      continue;
    }
    const exact = fields.some((x) => x.toLocaleLowerCase("vi") === lower);
    const prefix = fields.some((x) => x.toLocaleLowerCase("vi").startsWith(lower));
    muc.push({
      type: "ho_so",
      id: String(h.id),
      nhan: ma || ten || "Hồ sơ",
      phu: [ten, String(h.trang_thai || ""), diaChi].filter(Boolean).join(" · ") || null,
      khop: exact ? "exact" : prefix ? "prefix" : "fuzzy",
      diem: exact ? 1 : prefix ? 0.8 : 0.5,
      dossier_id: h.id ? String(h.id) : null,
    });
  }
  muc.sort((a, b) => b.diem - a.diem);
  return {
    groups: muc.length ? [{ type: "ho_so", total: muc.length, items: muc.slice(0, 8) }] : [],
    took_ms: Math.max(0, Math.round(performance.now() - batDau)),
  };
}

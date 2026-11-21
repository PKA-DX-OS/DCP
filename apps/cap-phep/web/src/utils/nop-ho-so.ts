// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { HoSo, NopHoSoPayload } from "../types";
import { chuanHoaCccd, chuanHoaDienThoai, loiDienThoai } from "./validation";

/** Bản nháp form nộp hồ sơ: chỉ lưu trên trình duyệt, không gửi lên máy chủ. */
const TTL_MS = 24 * 60 * 60 * 1000;
const KHOA_GOC = "dxos-nhap-ho-so-v1";

export interface BanNhapForm {
  at: number;
  form: NopHoSoPayload;
}

export interface KetQuaDienTuHoSo {
  form: NopHoSoPayload;
  soO: number;
}

export function formNopTrong(): NopHoSoPayload {
  return {
    ho_ten: "",
    cccd: "",
    dien_thoai: "",
    dia_chi_cong_trinh: "",
    thua_dat: "",
    so_tang: 1,
    dien_tich_san_m2: 100.0,
    khu_quan_ly_kien_truc: true,
    doi_tuong: "ho_gia_dinh_ca_nhan",
    trong_kcn: false,
    cap_hanh_chinh: "xa",
  };
}

export function formNopCoDuLieu(form: Partial<NopHoSoPayload> | null | undefined): boolean {
  if (!form) return false;
  const mac = formNopTrong();
  return Boolean(
    String(form.ho_ten ?? "").trim() ||
      String(form.cccd ?? "").trim() ||
      String(form.dien_thoai ?? "").trim() ||
      String(form.dia_chi_cong_trinh ?? "").trim() ||
      String(form.thua_dat ?? "").trim() ||
      Number(form.so_tang) !== Number(mac.so_tang) ||
      Number(form.dien_tich_san_m2) !== Number(mac.dien_tich_san_m2) ||
      form.doi_tuong === "to_chuc" ||
      form.trong_kcn === true ||
      form.cap_hanh_chinh === "tinh" ||
      form.khu_quan_ly_kien_truc === false,
  );
}

/** Ghép bản nháp đã lưu với giá trị mặc định; bỏ giá trị lạ hoặc sai kiểu. */
export function hopNhatFormNop(saved: Partial<NopHoSoPayload> | null | undefined): NopHoSoPayload {
  const mac = formNopTrong();
  if (!saved) return mac;
  const soTang = Number(saved.so_tang);
  const dienTich = Number(saved.dien_tich_san_m2);
  return {
    ...mac,
    ho_ten: String(saved.ho_ten ?? mac.ho_ten).trim().slice(0, 120),
    cccd: chuanHoaCccd(String(saved.cccd ?? mac.cccd)).slice(0, 12),
    dien_thoai: chuanHoaDienThoai(String(saved.dien_thoai ?? mac.dien_thoai)).slice(0, 20),
    dia_chi_cong_trinh: String(saved.dia_chi_cong_trinh ?? mac.dia_chi_cong_trinh).trim().slice(0, 255),
    thua_dat: String(saved.thua_dat ?? mac.thua_dat).trim().slice(0, 100),
    so_tang: Number.isInteger(soTang) && soTang > 0 ? soTang : mac.so_tang,
    dien_tich_san_m2: Number.isFinite(dienTich) && dienTich > 0 ? dienTich : mac.dien_tich_san_m2,
    khu_quan_ly_kien_truc: saved.khu_quan_ly_kien_truc ?? mac.khu_quan_ly_kien_truc,
    doi_tuong: saved.doi_tuong === "to_chuc" ? "to_chuc" : "ho_gia_dinh_ca_nhan",
    trong_kcn: Boolean(saved.trong_kcn),
    cap_hanh_chinh: saved.cap_hanh_chinh === "tinh" ? "tinh" : "xa",
  };
}

export function khoaBanNhap(nguoiDungId?: string | null): string {
  return `${KHOA_GOC}:${nguoiDungId || "khach"}`;
}

/** Đọc bản nháp còn hạn; dữ liệu hỏng hoặc quá 24 giờ thì xóa. */
export function docBanNhap(storage: Storage, key: string, now = Date.now()): BanNhapForm | null {
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const obj = JSON.parse(raw) as Partial<BanNhapForm> | null;
    if (!obj || typeof obj.at !== "number" || !obj.form) {
      storage.removeItem(key);
      return null;
    }
    if (now - obj.at > TTL_MS || obj.at > now + 5 * 60 * 1000) {
      storage.removeItem(key);
      return null;
    }
    return { at: obj.at, form: hopNhatFormNop(obj.form) };
  } catch {
    return null;
  }
}

/** Lưu bản nháp; form trống thì xóa bản nháp cũ. */
export function luuBanNhap(storage: Storage, key: string, form: NopHoSoPayload, now = Date.now()): boolean {
  if (!formNopCoDuLieu(form)) {
    xoaBanNhap(storage, key);
    return false;
  }
  try {
    storage.setItem(key, JSON.stringify({ at: now, form }));
    return true;
  } catch {
    return false;
  }
}

export function xoaBanNhap(storage: Storage, key: string): void {
  try {
    storage.removeItem(key);
  } catch {
    /* trình duyệt chặn storage: bỏ qua */
  }
}

/**
 * Điền từ hồ sơ cũ vào các ô đang trống. Không ghi đè dữ liệu người dùng đã nhập.
 * Số tầng/diện tích còn ở giá trị mặc định cũng được coi là ô trống.
 */
export function dienTuHoSo(form: NopHoSoPayload, hoSo: HoSo, ghiDe = false): KetQuaDienTuHoSo {
  const next: NopHoSoPayload = { ...form };
  const mac = formNopTrong();
  let soO = 0;

  const dienChuoi = (key: "ho_ten" | "cccd" | "dien_thoai" | "dia_chi_cong_trinh" | "thua_dat", value: unknown) => {
    const hienTai = String(next[key] ?? "").trim();
    const moi = String(value ?? "").trim();
    if (!moi || (!ghiDe && hienTai)) return;
    if (moi === hienTai) return;
    next[key] = moi;
    soO += 1;
  };

  dienChuoi("ho_ten", hoSo.ho_ten);
  // Không điền CCCD đã bị che hoặc dữ liệu rác.
  if (/^\d{12}$/.test(chuanHoaCccd(hoSo.cccd))) dienChuoi("cccd", chuanHoaCccd(hoSo.cccd));
  const dienThoai = chuanHoaDienThoai(hoSo.dien_thoai);
  if (!loiDienThoai(dienThoai)) dienChuoi("dien_thoai", dienThoai);
  dienChuoi("dia_chi_cong_trinh", hoSo.dia_chi_cong_trinh);
  dienChuoi("thua_dat", hoSo.thua_dat);

  if (hoSo.so_tang && (ghiDe || Number(next.so_tang) === Number(mac.so_tang))) {
    if (Number(next.so_tang) !== Number(hoSo.so_tang)) {
      next.so_tang = Number(hoSo.so_tang);
      soO += 1;
    }
  }
  if (hoSo.dien_tich_san_m2 && (ghiDe || Number(next.dien_tich_san_m2) === Number(mac.dien_tich_san_m2))) {
    if (Number(next.dien_tich_san_m2) !== Number(hoSo.dien_tich_san_m2)) {
      next.dien_tich_san_m2 = Number(hoSo.dien_tich_san_m2);
      soO += 1;
    }
  }

  return { form: next, soO };
}

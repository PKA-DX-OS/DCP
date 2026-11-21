// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Chuẩn hóa và kiểm tra dữ liệu form nộp hồ sơ ở phía giao diện. */

export function chuanHoaCccd(value: string | null | undefined): string {
  return String(value ?? "").replace(/\s+/g, "");
}

export function loiCccd(value: string | null | undefined): string {
  const s = chuanHoaCccd(value);
  if (!s) return "Nhập số CCCD.";
  if (!/^\d{12}$/.test(s)) return "CCCD phải gồm đúng 12 chữ số.";
  if (s.startsWith("000")) return "Mã tỉnh trong CCCD không hợp lệ.";
  if (/^(\d)\1{11}$/.test(s)) return "Số CCCD không hợp lệ.";
  return "";
}

export function chuanHoaDienThoai(value: string | null | undefined): string {
  return String(value ?? "")
    .replace(/[\s.\-()]/g, "")
    .replace(/^\+?84/, "0");
}

export function loiDienThoai(value: string | null | undefined): string {
  const s = chuanHoaDienThoai(value);
  if (!s) return "Nhập số điện thoại.";
  if (!/^0(2\d{8,9}|(3|5|7|8|9)\d{8})$/.test(s)) {
    return "Số điện thoại phải bắt đầu bằng 02, 03, 05, 07, 08 hoặc 09 và có 10–11 chữ số.";
  }
  return "";
}

export function loiHoTen(value: string | null | undefined): string {
  const s = String(value ?? "").trim();
  if (!s) return "Nhập họ và tên.";
  if (s.length < 3) return "Họ và tên phải có ít nhất 3 ký tự.";
  if (/\d/.test(s)) return "Họ và tên không được chứa chữ số.";
  return "";
}

export function loiDiaChi(value: string | null | undefined): string {
  const s = String(value ?? "").trim();
  if (!s) return "Nhập địa chỉ công trình.";
  if (s.length < 5) return "Địa chỉ công trình phải có ít nhất 5 ký tự.";
  return "";
}

export function loiThuaDat(value: string | null | undefined): string {
  const s = String(value ?? "").trim();
  if (!s) return "Nhập thửa đất, tờ bản đồ.";
  if (s.length < 3) return "Thửa đất, tờ bản đồ quá ngắn.";
  if (!/\d/.test(s)) return "Thửa đất, tờ bản đồ cần có số.";
  return "";
}

export function loiSoTang(value: number | string | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n) || !Number.isInteger(n)) return "Số tầng phải là số nguyên.";
  if (n < 1 || n > 5) return "Số tầng phải từ 1 đến 5.";
  return "";
}

export function loiDienTich(value: number | string | null | undefined): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "Diện tích sàn phải là số.";
  if (n <= 0) return "Diện tích sàn phải lớn hơn 0.";
  if (n > 100_000) return "Diện tích sàn vượt quá giới hạn 100.000 m².";
  return "";
}

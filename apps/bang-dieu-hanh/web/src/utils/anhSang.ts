// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

export type CheDoGiaoDien = "sang" | "toi" | "he-thong";

const KHOA_LUU = "dxos-bdh-theme";
const CHE_DO_HOP_LE: CheDoGiaoDien[] = ["sang", "toi", "he-thong"];

export function layCheDoLuu(): CheDoGiaoDien {
  try {
    const v = window.localStorage.getItem(KHOA_LUU);
    return CHE_DO_HOP_LE.includes(v as CheDoGiaoDien) ? (v as CheDoGiaoDien) : "he-thong";
  } catch {
    return "he-thong";
  }
}

export function luuCheDo(che: CheDoGiaoDien): void {
  try {
    window.localStorage.setItem(KHOA_LUU, che);
  } catch {
    /* bộ nhớ bị chặn: vẫn đổi giao diện trong phiên này */
  }
}

export function heThongDangToi(): boolean {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

/** Gắn data-theme lên thẻ html; style.css dùng thuộc tính này. */
export function apDungTheme(che: CheDoGiaoDien): void {
  const toi = che === "toi" || (che === "he-thong" && heThongDangToi());
  const goc = document.documentElement;
  goc.dataset.theme = toi ? "dark" : "light";
  goc.style.colorScheme = toi ? "dark" : "light";
}

/** Gọi trước khi ứng dụng được gắn vào DOM để trang không nhấp nháy. */
export function khoiTaoSomTheme(): void {
  apDungTheme(layCheDoLuu());
}
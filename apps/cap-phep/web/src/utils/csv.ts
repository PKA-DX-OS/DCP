// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

export type OCSV = string | number | boolean | null | undefined;

function o(value: OCSV): string {
  const s = String(value ?? "");
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Tạo CSV có BOM để Excel đọc đúng tiếng Việt. */
export function taoCsv(headers: string[], rows: OCSV[][]): string {
  const dong = [headers, ...rows].map((r) => r.map(o).join(","));
  return `\uFEFF${dong.join("\r\n")}`;
}

/** Tải CSV trên máy người dùng; không gửi dữ liệu lên máy chủ. */
export function taiCsv(tenFile: string, headers: string[], rows: OCSV[][]): void {
  const blob = new Blob([taoCsv(headers, rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = tenFile;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

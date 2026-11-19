// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Kiểm tệp phía giao diện trước khi tải lên. Server vẫn kiểm lại (ClamAV, loại, kích thước). */

export interface FileRule {
  /** Đuôi tệp (".pdf") hoặc kiểu MIME ("application/pdf", "image/*") */
  accept?: string[];
  maxBytes?: number;
}

export function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "—";
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${Math.round(v * 10) / 10} ${units[i]}`.replace(".", ",");
}

function matches(file: { name: string; type: string }, rule: string): boolean {
  const r = rule.trim().toLowerCase();
  if (!r) return false;
  if (r.startsWith(".")) return file.name.toLowerCase().endsWith(r);
  if (r.endsWith("/*")) return file.type.toLowerCase().startsWith(r.slice(0, -1));
  return file.type.toLowerCase() === r;
}

/** Trả về lời giải thích lỗi, hoặc null nếu tệp hợp lệ. */
export function checkFile(file: { name: string; type: string; size: number }, rule: FileRule): string | null {
  if (rule.accept?.length && !rule.accept.some((a) => matches(file, a))) {
    return `Tệp "${file.name}" không đúng loại. Chỉ nhận: ${rule.accept.join(", ")}.`;
  }
  if (rule.maxBytes && file.size > rule.maxBytes) {
    return `Tệp "${file.name}" (${formatBytes(file.size)}) vượt giới hạn ${formatBytes(rule.maxBytes)}.`;
  }
  if (file.size === 0) return `Tệp "${file.name}" rỗng.`;
  return null;
}

/** Chuyển ngày ISO (yyyy-mm-dd) sang dd/mm/yyyy; chuỗi không hợp lệ thì trả rỗng. */
export function isoToVn(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Lớp CSS theo variant/size của component. Tách khỏi .vue để test được không cần DOM.
 * Mọi màu đều lấy từ nhóm `ds` của tailwind.config.js (token trong tokens.css).
 */

export type Size = "sm" | "md" | "lg";
export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info" | "gold";

const BUTTON_BASE =
  "ds-focus inline-flex items-center justify-center gap-2 font-semibold transition-colors " +
  "disabled:cursor-not-allowed disabled:opacity-50";

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  /* Như .btn-chinh, .btn, .btn-nguy trong style.css */
  primary: "bg-ds-primary text-ds-on-primary hover:bg-ds-primary/90",
  secondary: "border border-ds-border bg-transparent text-ds-text hover:bg-ds-surface-2",
  ghost: "text-ds-text hover:bg-ds-surface-2",
  danger: "border border-ds-danger/45 bg-transparent text-ds-danger hover:bg-ds-danger/10",
};

/** Vùng chạm tối thiểu 44px ở size md/lg (B-UX-06); sm dùng trong bảng. */
const BUTTON_SIZE: Record<Size, string> = {
  sm: "h-8 rounded-ds-sm px-3 text-ds-sm",
  md: "h-11 rounded-ds-sm px-4 text-ds-base",
  lg: "h-12 rounded-ds-md px-5 text-ds-md",
};

export function buttonClasses(variant: ButtonVariant = "primary", size: Size = "md", block = false): string {
  return [BUTTON_BASE, BUTTON_VARIANT[variant], BUTTON_SIZE[size], block ? "w-full" : ""].filter(Boolean).join(" ");
}

const FIELD_SIZE: Record<Size, string> = {
  sm: "h-8 px-2 text-ds-sm",
  md: "h-11 px-3 text-ds-base",
  lg: "h-12 px-4 text-ds-md",
};

/** Ô nhập, ô chọn: viền đỏ khi có lỗi. */
export function fieldClasses(size: Size = "md", invalid = false): string {
  return [
    "ds-focus w-full rounded-ds-sm border bg-transparent text-ds-text placeholder:text-ds-muted",
    "disabled:cursor-not-allowed disabled:opacity-60",
    invalid ? "border-ds-danger" : "border-ds-border",
    FIELD_SIZE[size],
  ].join(" ");
}

const TONE: Record<Tone, string> = {
  // Bảng màu kính + champagne của bản cũ; các lớp nền đã có trong style.css.
  neutral: "bg-mat-2 text-phu",
  brand: "bg-cham/15 text-cham",
  success: "bg-xanh-nen text-xanh",
  warning: "bg-vang-nen text-vang",
  danger: "bg-do-nen text-son",
  info: "bg-lam-nen text-lam",
  gold: "bg-cham/20 text-cham",
};

export function badgeClasses(tone: Tone = "neutral", size: "sm" | "md" = "md"): string {
  const s = size === "sm" ? "px-2 py-0.5 text-ds-xs" : "px-2.5 py-0.5 text-ds-sm";
  return `inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-medium ${s} ${TONE[tone]}`;
}

const STATUS_TONE: Array<[string[], Tone]> = [
  [["tu_choi", "bi_tu_choi", "qua_han", "loi", "that_bai", "khong_dat", "fail", "failed", "rejected", "overdue", "error"], "danger"],
  [["da_cap", "hoan_thanh", "da_duyet", "dat", "pass", "passed", "approved", "done", "success", "da_xu_ly"], "success"],
  [["can_bo_sung", "bo_sung", "cho_ky", "tam_dung", "pending", "waiting", "draft", "nhap", "mo", "open"], "warning"],
  [["da_nop", "cho_tiep_nhan", "tiep_nhan", "duoc_phan_cong", "dang_tham_dinh", "tham_dinh", "cho_duyet", "dang_xu_ly",
    "xu_ly", "processing", "in_progress", "submitted"], "info"],
];

/**
 * Nhóm trạng thái chung: thành công (xanh lá), chờ (vàng), quá hạn/từ chối (đỏ), đang xử lý (xanh dương).
 * So khớp nguyên mã (không phân biệt hoa thường); mã không biết thì trung tính.
 */
export function statusTone(status: string | null | undefined): Tone {
  const s = (status || "").trim().toLowerCase().replace(/[-\s]+/g, "_");
  if (!s) return "neutral";
  for (const [codes, tone] of STATUS_TONE) if (codes.includes(s)) return tone;
  return "neutral";
}

/** Vai Keycloak dạng `app:<ma-app>:<vai>` hoặc `dx:<vai>`; vai nền tảng tô vàng (gold). */
export function roleTone(role: string): Tone {
  return role.startsWith("dx:") ? "gold" : "brand";
}

export function roleLabel(role: string): string {
  const parts = role.split(":");
  return parts[parts.length - 1].replace(/-/g, " ");
}

/**
 * Các trang cần hiện ở bộ phân trang: luôn có trang đầu, cuối và `quanh` trang mỗi bên trang hiện tại;
 * khoảng bị bỏ thay bằng "…".
 */
export function pageItems(total: number, pageSize: number, page: number, quanh = 1): Array<number | "…"> {
  const pages = Math.max(1, Math.ceil(Math.max(0, total) / Math.max(1, pageSize)));
  const cur = Math.min(Math.max(1, page), pages);
  const keep = new Set<number>([1, pages]);
  for (let p = cur - quanh; p <= cur + quanh; p++) if (p >= 1 && p <= pages) keep.add(p);
  const sorted = [...keep].sort((a, b) => a - b);
  const out: Array<number | "…"> = [];
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push(p - sorted[i - 1] === 2 ? p - 1 : "…");
    out.push(p);
  });
  return out;
}

export function pageCount(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(Math.max(0, total) / Math.max(1, pageSize)));
}

/** Xu hướng của thẻ chỉ số: % thay đổi so với kỳ trước, null khi không so được. */
export function trendPercent(current: number | null | undefined, previous: number | null | undefined): number | null {
  if (current == null || previous == null || !Number.isFinite(current) || !Number.isFinite(previous)) return null;
  if (previous === 0) return current === 0 ? 0 : null;
  return Math.round(((current - previous) / Math.abs(previous)) * 1000) / 10;
}

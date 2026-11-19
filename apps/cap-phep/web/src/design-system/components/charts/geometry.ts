// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Tính hình học cho biểu đồ SVG tự vẽ; hàm thuần để test không cần DOM. */

export const CHART_COLORS = [1, 2, 3, 4, 5].map((i) => `rgb(var(--ds-chart-${i}))`);

export function chartColor(i: number): string {
  return CHART_COLORS[((i % CHART_COLORS.length) + CHART_COLORS.length) % CHART_COLORS.length];
}

export interface Arc {
  index: number;
  value: number;
  fraction: number;
  path: string;
}

function polar(cx: number, cy: number, r: number, angle: number): [number, number] {
  // 0 rad ở đỉnh, quay theo chiều kim đồng hồ
  return [cx + r * Math.sin(angle), cy - r * Math.cos(angle)];
}

const r4 = (n: number) => Math.round(n * 1e4) / 1e4;

/** Cung vành khăn cho biểu đồ donut. Giá trị âm hoặc không hợp lệ coi là 0; tổng 0 thì không có cung. */
export function donutArcs(values: number[], cx = 50, cy = 50, outer = 48, inner = 30): Arc[] {
  const clean = values.map((v) => (Number.isFinite(v) && v > 0 ? v : 0));
  const total = clean.reduce((a, b) => a + b, 0);
  if (total <= 0) return [];
  const out: Arc[] = [];
  let start = 0;
  clean.forEach((v, index) => {
    if (v <= 0) return;
    const fraction = v / total;
    // Một phần chiếm trọn vòng: vẽ gần trọn để SVG không bỏ cung
    const sweep = Math.min(fraction * 2 * Math.PI, 2 * Math.PI - 1e-4);
    const end = start + sweep;
    const large = sweep > Math.PI ? 1 : 0;
    const [x1, y1] = polar(cx, cy, outer, start);
    const [x2, y2] = polar(cx, cy, outer, end);
    const [x3, y3] = polar(cx, cy, inner, end);
    const [x4, y4] = polar(cx, cy, inner, start);
    const path =
      `M${r4(x1)} ${r4(y1)} A${outer} ${outer} 0 ${large} 1 ${r4(x2)} ${r4(y2)} ` +
      `L${r4(x3)} ${r4(y3)} A${inner} ${inner} 0 ${large} 0 ${r4(x4)} ${r4(y4)} Z`;
    out.push({ index, value: v, fraction, path });
    start = end;
  });
  return out;
}

/** Giá trị trục đẹp (bội của 1, 2, 5 × 10^n) phủ được max. */
export function niceMax(max: number): number {
  if (!Number.isFinite(max) || max <= 0) return 1;
  const exp = Math.floor(Math.log10(max));
  const base = 10 ** exp;
  for (const m of [1, 2, 5, 10]) if (m * base >= max) return m * base;
  return 10 * base;
}

export function ticks(max: number, count = 4): number[] {
  const top = niceMax(max);
  return Array.from({ length: count + 1 }, (_, i) => r4((top / count) * i));
}

export interface Box {
  width: number;
  height: number;
  padLeft: number;
  padRight: number;
  padTop: number;
  padBottom: number;
}

export const DEFAULT_BOX: Box = { width: 600, height: 240, padLeft: 40, padRight: 12, padTop: 12, padBottom: 28 };

/** Toạ độ điểm của một đường; giá trị null tạo khoảng trống (không nối qua dữ liệu thiếu). */
export function linePoints(values: Array<number | null>, max: number, box: Box = DEFAULT_BOX) {
  const w = box.width - box.padLeft - box.padRight;
  const h = box.height - box.padTop - box.padBottom;
  const top = niceMax(max);
  const step = values.length > 1 ? w / (values.length - 1) : 0;
  return values.map((v, i) => ({
    x: r4(box.padLeft + (values.length > 1 ? i * step : w / 2)),
    y: v === null || !Number.isFinite(v) ? null : r4(box.padTop + h - (Math.max(0, v) / top) * h),
    value: v,
  }));
}

export function linePath(points: Array<{ x: number; y: number | null }>): string {
  let d = "";
  let pen = false;
  for (const p of points) {
    if (p.y === null) {
      pen = false;
      continue;
    }
    d += `${pen ? "L" : "M"}${p.x} ${p.y} `;
    pen = true;
  }
  return d.trim();
}

/** Cột dọc chia đều bề ngang; mỗi cột chiếm `ratio` khe của nó. */
export function barRects(values: number[], max: number, box: Box = DEFAULT_BOX, ratio = 0.6) {
  const w = box.width - box.padLeft - box.padRight;
  const h = box.height - box.padTop - box.padBottom;
  const top = niceMax(max);
  const slot = values.length ? w / values.length : 0;
  return values.map((v, i) => {
    const val = Number.isFinite(v) && v > 0 ? v : 0;
    const height = r4((val / top) * h);
    return {
      x: r4(box.padLeft + i * slot + (slot * (1 - ratio)) / 2),
      y: r4(box.padTop + h - height),
      width: r4(slot * ratio),
      height,
      value: v,
    };
  });
}

/** Đường nhỏ (sparkline) trong khung w×h. */
export function sparkPath(values: number[], w = 80, h = 24): string {
  const clean = values.filter((v) => Number.isFinite(v));
  if (clean.length < 2) return "";
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = max - min || 1;
  return clean
    .map((v, i) => `${i ? "L" : "M"}${r4((i / (clean.length - 1)) * w)} ${r4(h - ((v - min) / span) * h)}`)
    .join(" ");
}

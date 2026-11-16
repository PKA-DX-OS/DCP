// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Tinh ty le dung han theo phan tram
 */
export function calculateSlaRate(total, onTime) {
  if (!total || total <= 0) return 100.0;
  if (!onTime || onTime < 0) return 0.0;
  const rate = (onTime / total) * 100.0;
  return Math.min(100.0, Math.max(0.0, Number(rate.toFixed(1))));
}

/**
 * Dinh dang gia tri chi so kem don vi theo vi-VN
 */
export function formatMetricValue(val, unit = "") {
  if (val === null || val === undefined || isNaN(val)) return `0 ${unit}`.trim();
  const formatted = new Intl.NumberFormat("vi-VN", {
    maximumFractionDigits: 1
  }).format(val);
  return `${formatted} ${unit}`.trim();
}

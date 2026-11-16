// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { ref } from "vue";

export type Theme = "light" | "dark";
const KEY = "dxos-giao-dien";

function readSaved(): Theme | null {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}


// Thiết kế ưu tiên nền đêm; người dùng tự chuyển sang sáng nếu muốn.
const theme = ref<Theme>(readSaved() || "dark");

function apply(t: Theme) {
  document.documentElement.dataset.theme = t;
}

/** Gọi một lần trước khi mount để tránh nháy màu. */
export function initTheme() {
  apply(theme.value);
}

export function useTheme() {
  function toggle() {
    theme.value = theme.value === "dark" ? "light" : "dark";
    apply(theme.value);
    try {
      window.localStorage.setItem(KEY, theme.value);
    } catch {
      /* chế độ riêng tư: chỉ đổi trong phiên */
    }
  }
  return { theme, toggle };
}

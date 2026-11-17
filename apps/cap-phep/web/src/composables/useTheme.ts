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

const media = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;

/** Chưa chọn thì theo cài đặt hệ thống; hệ thống không nói gì thì dùng nền đêm như thiết kế. */
function systemTheme(): Theme {
  return media?.matches ? "light" : "dark";
}

const saved = readSaved();
const theme = ref<Theme>(saved || systemTheme());
let theoHeThong = saved === null;

function apply(t: Theme) {
  document.documentElement.dataset.theme = t;
  document.documentElement.style.colorScheme = t;
}

/** Gọi một lần trước khi mount để tránh nháy màu. */
export function initTheme() {
  apply(theme.value);
  // Người dùng chưa tự chọn: đổi theo hệ thống khi hệ thống đổi
  media?.addEventListener?.("change", () => {
    if (!theoHeThong) return;
    theme.value = systemTheme();
    apply(theme.value);
  });
}

export function useTheme() {
  /** Chỉ đổi thuộc tính giao diện trên <html>, không đụng trạng thái màn hình đang mở. */
  function toggle() {
    theme.value = theme.value === "dark" ? "light" : "dark";
    theoHeThong = false;
    apply(theme.value);
    try {
      window.localStorage.setItem(KEY, theme.value);
    } catch {
      /* chế độ riêng tư: chỉ đổi trong phiên */
    }
  }
  return { theme, toggle };
}

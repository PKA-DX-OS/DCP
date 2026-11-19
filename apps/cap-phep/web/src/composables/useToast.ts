// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { ref } from "vue";

/** ok = thành công, loi = lỗi, canh_bao = cảnh báo, tin = thông tin. */
export type ToastKind = "ok" | "loi" | "canh_bao" | "tin";
export interface Toast {
  id: number;
  kind: ToastKind;
  text: string;
}

/** Số thông báo hiện cùng lúc; thông báo cũ nhất bị đẩy ra khi vượt. */
const TOI_DA = 4;
const toasts = ref<Toast[]>([]);
const timers = new Map<number, number>();
let seq = 0;

/** Thông báo ngắn ở góc màn hình, thay cho hộp alert của trình duyệt; tự đóng sau `ms`. */
export function notify(text: string, kind: ToastKind = "ok", ms = 5000) {
  const id = ++seq;
  toasts.value.push({ id, kind, text });
  while (toasts.value.length > TOI_DA) dismiss(toasts.value[0].id);
  // Lỗi và cảnh báo hiện lâu hơn để kịp đọc
  const thoiGian = kind === "loi" || kind === "canh_bao" ? ms + 3000 : ms;
  timers.set(id, window.setTimeout(() => dismiss(id), thoiGian));
}

export function dismiss(id: number) {
  const t = timers.get(id);
  if (t !== undefined) {
    window.clearTimeout(t);
    timers.delete(id);
  }
  toasts.value = toasts.value.filter((x) => x.id !== id);
}

export function useToasts() {
  return { toasts, dismiss };
}

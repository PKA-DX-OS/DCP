// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { ref } from "vue";

export type ToastKind = "ok" | "loi" | "tin";
export interface Toast {
  id: number;
  kind: ToastKind;
  text: string;
}

const toasts = ref<Toast[]>([]);
let seq = 0;

/** Thông báo ngắn ở góc màn hình, thay cho hộp alert của trình duyệt. */
export function notify(text: string, kind: ToastKind = "ok", ms = 5000) {
  const id = ++seq;
  toasts.value.push({ id, kind, text });
  window.setTimeout(() => dismiss(id), kind === "loi" ? ms + 3000 : ms);
}

export function dismiss(id: number) {
  toasts.value = toasts.value.filter((t) => t.id !== id);
}

export function useToasts() {
  return { toasts, dismiss };
}

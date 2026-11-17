// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { nextTick, onBeforeUnmount, onMounted, type Ref } from "vue";

/**
 * Hành vi chung cho hộp thoại: ESC để đóng, giữ focus trong hộp (Tab / Shift+Tab vòng lại),
 * focus vào phần tử đầu tiên khi mở và trả focus về chỗ cũ khi đóng.
 * Nhiều hộp chồng nhau thì chỉ hộp trên cùng nhận phím.
 */
const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
const stack: symbol[] = [];

export function useModal(root: Ref<HTMLElement | null>, onClose: () => void) {
  const id = Symbol("modal");
  let previous: HTMLElement | null = null;

  function focusables(): HTMLElement[] {
    if (!root.value) return [];
    return Array.from(root.value.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => !el.hasAttribute("disabled") && el.getClientRects().length > 0,
    );
  }

  function onKey(e: KeyboardEvent) {
    if (stack[stack.length - 1] !== id) return;
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key !== "Tab") return;
    const items = focusables();
    if (!items.length) {
      e.preventDefault();
      root.value?.focus();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && (active === first || !root.value?.contains(active))) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && (active === last || !root.value?.contains(active))) {
      e.preventDefault();
      first.focus();
    }
  }

  onMounted(() => {
    previous = document.activeElement as HTMLElement | null;
    stack.push(id);
    document.addEventListener("keydown", onKey);
    nextTick(() => (focusables()[0] ?? root.value)?.focus());
  });

  onBeforeUnmount(() => {
    document.removeEventListener("keydown", onKey);
    const i = stack.indexOf(id);
    if (i >= 0) stack.splice(i, 1);
    previous?.focus?.();
  });
}

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { nextTick, onBeforeUnmount, watch, type Ref } from "vue";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Hành vi chung của Modal và Drawer: đưa focus vào hộp khi mở, giữ Tab trong hộp,
 * Esc để đóng, khóa cuộn trang và trả focus về chỗ cũ khi đóng.
 */
export function useDialog(open: Ref<boolean>, panel: Ref<HTMLElement | null>, close: () => void) {
  let truoc: HTMLElement | null = null;

  function onKey(e: KeyboardEvent) {
    if (!open.value || !panel.value) return;
    if (e.key === "Escape") {
      e.stopPropagation();
      close();
      return;
    }
    if (e.key !== "Tab") return;
    const items = Array.from(panel.value.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => el.offsetParent !== null);
    if (!items.length) {
      e.preventDefault();
      panel.value.focus();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  watch(
    open,
    async (v) => {
      if (v) {
        truoc = document.activeElement as HTMLElement | null;
        document.addEventListener("keydown", onKey, true);
        document.body.style.overflow = "hidden";
        await nextTick();
        const first = panel.value?.querySelector<HTMLElement>(FOCUSABLE);
        (first || panel.value)?.focus();
      } else {
        document.removeEventListener("keydown", onKey, true);
        document.body.style.overflow = "";
        truoc?.focus?.();
      }
    },
    { immediate: true },
  );

  onBeforeUnmount(() => {
    document.removeEventListener("keydown", onKey, true);
    document.body.style.overflow = "";
  });
}

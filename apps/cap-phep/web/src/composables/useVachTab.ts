// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { ref, watch, nextTick, onMounted, onBeforeUnmount, type Ref } from "vue";

/**
 * Vạch dưới tab trượt tới tab đang mở (tab có aria-current="page").
 * Lần đặt đầu tiên không chạy hiệu ứng để vạch không bay từ mép trái vào.
 */
export function useVachTab(nav: Ref<HTMLElement | null>, tabDangMo: Ref<unknown>) {
  const kieu = ref<Record<string, string>>({ opacity: "0", width: "0px" });
  let daDat = false;
  let doKichThuoc: ResizeObserver | null = null;

  function dat() {
    const el = nav.value?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!el) {
      kieu.value = { opacity: "0", width: "0px" };
      daDat = false;
      return;
    }
    kieu.value = {
      width: `${el.offsetWidth}px`,
      transform: `translateX(${el.offsetLeft}px)`,
      opacity: "1",
      ...(daDat ? {} : { transition: "none" }),
    };
    daDat = true;
  }

  function theoDoi() {
    doKichThuoc?.disconnect();
    if (!nav.value || typeof ResizeObserver === "undefined") return;
    doKichThuoc = new ResizeObserver(() => dat());
    doKichThuoc.observe(nav.value);
    nav.value.querySelectorAll("button, a").forEach((b) => doKichThuoc?.observe(b));
  }

  watch(tabDangMo, () => nextTick(dat));
  watch(nav, () => nextTick(() => { theoDoi(); dat(); }));
  onMounted(() => nextTick(() => { theoDoi(); dat(); }));
  onBeforeUnmount(() => doKichThuoc?.disconnect());

  return kieu;
}

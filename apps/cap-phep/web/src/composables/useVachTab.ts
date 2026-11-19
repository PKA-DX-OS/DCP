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

/**
 * Tab đang chọn đồng bộ với tham số trên URL (mặc định `?tab=`): mở lại trang hoặc gửi liên kết
 * vẫn vào đúng tab; nút Quay lại/Tới của trình duyệt đổi tab theo.
 */
export function useTabTrongUrl<T extends string>(cacTab: readonly T[], macDinh: T, thamSo = "tab"): Ref<T> {
  const doc = (): T => {
    const v = new URLSearchParams(window.location.search).get(thamSo) as T | null;
    return v && cacTab.includes(v) ? v : macDinh;
  };
  const tab = ref(doc()) as Ref<T>;

  watch(tab, (v) => {
    const url = new URL(window.location.href);
    if (v === macDinh) url.searchParams.delete(thamSo);
    else url.searchParams.set(thamSo, v);
    if (url.href !== window.location.href) window.history.pushState(window.history.state, "", url);
  });

  const khiQuayLai = () => {
    tab.value = doc();
  };
  onMounted(() => window.addEventListener("popstate", khiQuayLai));
  onBeforeUnmount(() => window.removeEventListener("popstate", khiQuayLai));

  return tab;
}

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { ref, watch } from "vue";

export type Tab = "chi-so" | "tro-ly";
const DANH_SACH_TAB: Tab[] = ["chi-so", "tro-ly"];
const KHOA_URL = "tab";

/** Tab đồng bộ với ?tab= trên URL; dùng replaceState để không làm dày lịch sử trình duyệt. */
export function useVachTab(macDinh: Tab = "chi-so") {
  const url = new URL(window.location.href);
  const tuUrl = url.searchParams.get(KHOA_URL) as Tab | null;
  const tab = ref<Tab>(tuUrl && DANH_SACH_TAB.includes(tuUrl) ? tuUrl : macDinh);

  watch(tab, (v) => {
    const u = new URL(window.location.href);
    u.searchParams.set(KHOA_URL, v);
    window.history.replaceState(window.history.state, "", u.toString());
  });

  return { tab, DANH_SACH_TAB };
}
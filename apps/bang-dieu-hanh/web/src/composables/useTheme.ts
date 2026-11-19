// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { apDungTheme, CheDoGiaoDien, layCheDoLuu, luuCheDo } from "../utils/anhSang";

export function useTheme() {
  const cheDo = ref<CheDoGiaoDien>(layCheDoLuu());
  const mq = window.matchMedia?.("(prefers-color-scheme: dark)");

  const khiHeThongDoi = () => {
    if (cheDo.value === "he-thong") apDungTheme("he-thong");
  };

  watch(cheDo, (v) => {
    luuCheDo(v);
    apDungTheme(v);
  });

  onMounted(() => mq?.addEventListener("change", khiHeThongDoi));
  onBeforeUnmount(() => mq?.removeEventListener("change", khiHeThongDoi));

  return { cheDo };
}
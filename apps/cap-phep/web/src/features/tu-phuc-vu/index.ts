// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineAsyncComponent } from "vue";
import type { AppFeature } from "../types";
import { laChuDauTu } from "../roles";

export const feature: AppFeature = {
  ma: "tu-phuc-vu",
  ten: "Tự phục vụ",
  thuTu: 15,
  hienThi: laChuDauTu,
  component: defineAsyncComponent(() => import("./SelfServiceTab.vue")),
};

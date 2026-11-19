// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineAsyncComponent } from "vue";
import type { AppFeature } from "../types";
import { laChuDauTu } from "../roles";

export const feature: AppFeature = {
  ma: "ho-so",
  ten: "Hồ sơ của tôi",
  thuTu: 10,
  hienThi: laChuDauTu,
  component: defineAsyncComponent(() => import("./HoSoTab.vue")),
};

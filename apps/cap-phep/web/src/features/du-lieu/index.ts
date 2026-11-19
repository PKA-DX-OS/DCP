// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineAsyncComponent } from "vue";
import type { AppFeature } from "../types";
import { laChuDauTu } from "../roles";

export const feature: AppFeature = {
  ma: "du-lieu",
  ten: "Dữ liệu của tôi",
  thuTu: 20,
  hienThi: laChuDauTu,
  component: defineAsyncComponent(() => import("./DuLieuTab.vue")),
  khiMo: (ctx) => void ctx.cd.taiDuLieuCaNhan(),
};

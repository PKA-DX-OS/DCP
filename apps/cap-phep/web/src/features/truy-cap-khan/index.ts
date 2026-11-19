// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineAsyncComponent } from "vue";
import type { AppFeature } from "../types";
import { VAI, coVai } from "../roles";

export const feature: AppFeature = {
  ma: "truy-cap-khan",
  ten: "Truy cập khẩn",
  thuTu: 50,
  hienThi: (vai) => coVai(vai, VAI.LANH_DAO),
  component: defineAsyncComponent(() => import("../../views/TruyCapKhanView.vue")),
};

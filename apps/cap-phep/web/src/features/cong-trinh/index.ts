// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineAsyncComponent } from "vue";
import type { AppFeature } from "../types";
import { laCanBo } from "../roles";

export const feature: AppFeature = {
  ma: "cong-trinh",
  ten: "Công trình",
  thuTu: 40,
  hienThi: laCanBo,
  component: defineAsyncComponent(() => import("../../views/ConstructionView.vue")),
};

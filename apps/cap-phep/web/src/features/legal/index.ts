// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineAsyncComponent } from "vue";
import type { AppFeature } from "../types";
import { VAI_CAN_BO } from "../roles";

export const feature: AppFeature = {
  ma: "phap-luat",
  ten: "Văn bản pháp luật",
  thuTu: 45,
  hienThi: (vaiTro) => vaiTro.some((r) => VAI_CAN_BO.includes(r)),
  component: defineAsyncComponent(() => import("./LegalLibraryPanel.vue")),
};

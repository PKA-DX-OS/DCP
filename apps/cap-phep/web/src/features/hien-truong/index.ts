// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineAsyncComponent } from "vue";
import type { AppFeature } from "../types";
import { coVai, VAI } from "../roles";

export const feature: AppFeature = {
  ma: "hien-truong",
  ten: "Hiện trường",
  thuTu: 37,
  hienThi: (vaiTro) => coVai(vaiTro, VAI.TRAT_TU_XD, VAI.LANH_DAO),
  component: defineAsyncComponent(() => import("./FieldPwaTab.vue")),
};

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineAsyncComponent } from "vue";
import type { AppFeature } from "../types";
import { coVai, VAI } from "../roles";

export const feature: AppFeature = {
  ma: "duyet-ocr",
  ten: "Duyệt OCR",
  thuTu: 35,
  hienThi: (vaiTro) => coVai(vaiTro, VAI.MOT_CUA, VAI.THAM_DINH, VAI.LANH_DAO),
  component: defineAsyncComponent(() => import("./OcrReviewTab.vue")),
};

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineAsyncComponent } from "vue";
import type { DossierTab } from "../types";

const VAI_DOC = [
  "app:cap-phep:chu-dau-tu",
  "app:cap-phep:tham-dinh",
  "app:cap-phep:mot-cua",
  "app:cap-phep:lanh-dao",
  "app:cap-phep:trat-tu-xd",
  "dx:auditor",
  "dx:platform-admin",
];

/** Tab 5.2 trong chi tiết hồ sơ; đăng ký qua features/registry.ts. */
export const dossierTab: DossierTab = {
  ma: "thiet-ke",
  ten: "Thiết kế",
  thuTu: 40,
  hienThi: (vaiTro) => vaiTro.some((r) => VAI_DOC.includes(r)),
  component: defineAsyncComponent(() => import("./DesignReviewPanel.vue")),
};

export { createDesignReviewApi } from "./api";
export { moTaSoSanh, soSanhPhienBan } from "./compare";

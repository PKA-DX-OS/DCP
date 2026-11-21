// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineAsyncComponent } from "vue";
import type { DossierTab } from "../types";

const VAI_DOC = [
  "app:cap-phep:mot-cua",
  "app:cap-phep:tham-dinh",
  "app:cap-phep:lanh-dao",
  "app:cap-phep:trat-tu-xd",
  "dx:auditor",
  "dx:platform-admin",
];

/** H-LINK: tab đối chiếu liên ngành trong chi tiết hồ sơ. */
export const dossierTab: DossierTab = {
  ma: "lien-nganh",
  ten: "Liên ngành",
  thuTu: 45,
  hienThi: (vaiTro) => vaiTro.some((r) => VAI_DOC.includes(r)),
  component: defineAsyncComponent(() => import("./ExternalLookupPanel.vue")),
};

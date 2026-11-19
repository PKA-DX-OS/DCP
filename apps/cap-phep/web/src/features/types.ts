// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { Component, Ref } from "vue";
import type { HoSo } from "../types";
import type { useCongDan } from "../composables/useCongDan";

/** Những gì App chia sẻ cho các feature (provide/inject), để feature không phải sửa App.vue. */
export interface FeatureContext {
  vaiTro: Ref<string[]>;
  sub: Ref<string | undefined>;
  cd: ReturnType<typeof useCongDan>;
  moHoSo: (idHoacMa: string, ma?: string) => Promise<void>;
  moNopHoSo: () => Promise<void>;
  moBoSung: (d: HoSo) => void;
}

/** Một tab cấp ứng dụng (thanh điều hướng). */
export interface AppFeature {
  /** Mã tab, cũng là giá trị `?tab=` trên URL */
  ma: string;
  ten: string;
  /** Thứ tự trên thanh điều hướng, nhỏ đứng trước */
  thuTu: number;
  /** Vai nào thấy tab này */
  hienThi: (vaiTro: string[]) => boolean;
  /** Nên dùng defineAsyncComponent để feature chỉ tải khi cần */
  component: Component;
  /** Gọi mỗi lần người dùng chuyển sang tab */
  khiMo?: (ctx: FeatureContext) => void;
}

/** Một phần trong chi tiết hồ sơ (ví dụ Quy hoạch, Thiết kế, Nghiệm thu). Component nhận prop `dossier`, `userToken`. */
export interface DossierTab {
  ma: string;
  ten: string;
  thuTu: number;
  hienThi: (vaiTro: string[], hoSo: HoSo) => boolean;
  component: Component;
}

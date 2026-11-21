// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Danh sách feature của giao diện cấp phép. Thêm màn hình mới: tạo thư mục `features/<ma>/`
 * với `index.ts` export `feature` (tab ứng dụng) hoặc `dossierTab` (phần trong chi tiết hồ sơ),
 * rồi thêm một dòng import ở đây. Không cần sửa App.vue hay DetailDossierModal.vue.
 */
import type { HoSo } from "../types";
import type { AppFeature, DossierTab } from "./types";
import { feature as hoSo } from "./ho-so";
import { feature as duLieu } from "./du-lieu";
import { feature as banLamViec } from "./ban-lam-viec";
import { feature as congTrinh } from "./cong-trinh";
import { feature as truyCapKhan } from "./truy-cap-khan";
import { feature as phapLuat } from "./legal";
import { feature as ocrReview } from "./ocr-review";
import { feature as hienTruong } from "./hien-truong";
import { dossierTab as thietKe } from "./design-review";

export const FEATURES: readonly AppFeature[] = [
  hoSo,
  duLieu,
  banLamViec,
  ocrReview,
  hienTruong,
  congTrinh,
  phapLuat,
  truyCapKhan,
];

/** Phần mở rộng của chi tiết hồ sơ; 5.1, 5.2, 5.5 đăng ký ở đây. */
export const DOSSIER_TABS: readonly DossierTab[] = [thietKe];

export function tabsChoVai(vaiTro: string[], ds: readonly AppFeature[] = FEATURES): AppFeature[] {
  return ds.filter((f) => f.hienThi(vaiTro)).sort((a, b) => a.thuTu - b.thuTu);
}

export function dossierTabsChoVai(vaiTro: string[], hoSo: HoSo, ds: readonly DossierTab[] = DOSSIER_TABS): DossierTab[] {
  return ds.filter((t) => t.hienThi(vaiTro, hoSo)).sort((a, b) => a.thuTu - b.thuTu);
}

/** Mã trùng làm hỏng đồng bộ ?tab= trên URL; kiểm khi khởi động và trong test. */
export function maTrung(ds: ReadonlyArray<{ ma: string }>): string[] {
  const seen = new Set<string>();
  const dup = new Set<string>();
  for (const f of ds) (seen.has(f.ma) ? dup : seen).add(f.ma);
  return Array.from(dup);
}

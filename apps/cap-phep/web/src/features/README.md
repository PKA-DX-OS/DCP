<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: CC-BY-4.0
-->

# Feature của giao diện cấp phép

Mỗi màn hình là một thư mục trong `features/`. Thêm màn hình mới không cần sửa `App.vue`
hay `DetailDossierModal.vue`, nên hai track làm song song không đụng chung tệp.

## Thêm một tab ứng dụng

1. Tạo `features/<ma>/index.ts`:

   ```ts
   import { defineAsyncComponent } from "vue";
   import type { AppFeature } from "../types";
   import { laCanBo } from "../roles";

   export const feature: AppFeature = {
     ma: "quy-hoach",          // cũng là giá trị ?tab= trên URL, không trùng mã khác
     ten: "Quy hoạch",
     thuTu: 60,                // thứ tự trên thanh điều hướng
     hienThi: laCanBo,         // vai nào thấy tab
     component: defineAsyncComponent(() => import("./QuyHoachTab.vue")),
     khiMo: (ctx) => {},       // tùy chọn: chạy mỗi lần chuyển sang tab
   };
   ```

2. Thêm một dòng import và đưa `feature` vào `FEATURES` trong `features/registry.ts`.

Component của feature lấy dữ liệu dùng chung bằng `useFeatureContext()` (`features/context.ts`):
vai của người dùng, `cd` (hồ sơ của chủ đầu tư), `moHoSo`, `moNopHoSo`, `moBoSung`.

## Thêm một phần trong chi tiết hồ sơ

Export `dossierTab: DossierTab` từ `index.ts` và đưa vào `DOSSIER_TABS` trong `registry.ts`.
Component nhận prop `dossier` (hồ sơ đang xem) và `userToken`. Phần mới hiện ở cuối hộp chi tiết
và có nút chuyển nhanh trên thanh mục.

```ts
export const dossierTab: DossierTab = {
  ma: "thiet-ke",
  ten: "Thiết kế",
  thuTu: 20,
  hienThi: (vai, hoSo) => laCanBo(vai) || laChuDauTu(vai),
  component: defineAsyncComponent(() => import("./DrawingsTab.vue")),
};
```

## Giao diện

Dùng component và token trong `src/design-system/` (xem trang demo: `npm run dev`, mở
`/?tab=design-system`). Không đặt mã màu riêng trong feature.

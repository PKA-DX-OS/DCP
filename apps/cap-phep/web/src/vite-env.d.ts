// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/// <reference types="vite/client" />

/** Biến môi trường build (chỉ tiền tố VITE_ mới vào bundle; không đặt bí mật ở đây). */
interface ImportMetaEnv {
  /** Gốc API qua APISIX, mặc định "/api/v1". */
  readonly VITE_API_BASE?: string;
  /** client_id OIDC trên Keycloak, mặc định "dxos-web". */
  readonly VITE_OIDC_CLIENT_ID?: string;
  /** Realm Keycloak, mặc định "dxos". */
  readonly VITE_OIDC_REALM?: string;
  /** Liên kết mã nguồn (AGPL-3.0 Mục 13). */
  readonly VITE_SOURCE_URL?: string;
  /** "1" để build kèm trang demo design system (?tab=design-system). */
  readonly VITE_DEMO_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

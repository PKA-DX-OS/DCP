// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Cấu hình đọc từ biến môi trường Vite (xem src/vite-env.d.ts).
 * Mặc định là đường dẫn tương đối cùng origin, không trỏ cứng tới máy chủ nào.
 */
const env = import.meta.env;

/** Gốc API đi qua APISIX. */
export const API_BASE: string = (env.VITE_API_BASE || "/api/v1").replace(/\/+$/, "");

/** Keycloak: client và realm dùng cho đăng nhập OIDC (PKCE). */
export const OIDC_CLIENT_ID: string = env.VITE_OIDC_CLIENT_ID || "dxos-web";
export const OIDC_REALM: string = env.VITE_OIDC_REALM || "dxos";

/** Liên kết "Mã nguồn" ở chân trang (AGPL-3.0 Mục 13); giá trị đặt lúc build trong vite.config.ts. */
export const SOURCE_URL: string = env.VITE_SOURCE_URL || "";
export const APP_VERSION = "1.1";

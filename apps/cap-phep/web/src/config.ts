// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Liên kết "Mã nguồn" ở chân trang (AGPL-3.0 Mục 13). Đặt VITE_SOURCE_URL khi build để trỏ tới kho của bạn. */
export const SOURCE_URL: string = import.meta.env.VITE_SOURCE_URL || "https://github.com/dxos-core/dxos";
export const APP_VERSION = "1.1";

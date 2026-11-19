// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Dev: /api và /auth đi qua APISIX của stack cục bộ (đặt DEV_API_TARGET nếu khác)
  const apiTarget = env.DEV_API_TARGET || "http://localhost:8080";

  return {
    // Bảng điều hành được APISIX phục vụ dưới /dieu-hanh/ (route cắt tiền tố trước khi tới nginx);
    // thiếu base thì trình duyệt tải /assets/... từ cap-phep-web và nhận HTML thay cho JS/CSS
    base: "/dieu-hanh/",
    plugins: [vue()],
    define: {
      // Liên kết mã nguồn (AGPL-3.0 Mục 13)
      "import.meta.env.VITE_SOURCE_URL": JSON.stringify(env.VITE_SOURCE_URL || "https://github.com/PKA-DX-OS/DCP"),
    },
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    server: {
      port: 3001,
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
        "/auth": { target: apiTarget, changeOrigin: true },
      },
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
      sourcemap: false,
      rollupOptions: {
        output: { manualChunks: { vue: ["vue"], oidc: ["oidc-client-ts"] } },
      },
    },
  };
});
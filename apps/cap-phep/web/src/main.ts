// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "./style.css";
import "./design-system/tokens.css";
import { createApp } from "vue";
import App from "./App.vue";
import { initTheme } from "./composables/useTheme";

// Đặt màu nền trước khi mount để trang không nhấp nháy
initTheme();

/* Trang demo design system (?tab=design-system) chỉ có khi chạy dev hoặc build với VITE_DEMO_MODE=1;
   build thường loại bỏ hẳn nhánh này. */
const DEMO_DS = import.meta.env.DEV || import.meta.env.VITE_DEMO_MODE === "1";
if (DEMO_DS && new URLSearchParams(window.location.search).get("tab") === "design-system") {
  import("./design-system/DemoPage.vue").then((m) => createApp(m.default).mount("#app"));
} else {
  createApp(App).mount("#app");
}

// PWA: chỉ đăng ký ở bản build để không giữ cache cũ khi phát triển.
if (!import.meta.env.DEV && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch((err) => {
      console.warn("Không đăng ký được service worker:", err);
    });
  });
}
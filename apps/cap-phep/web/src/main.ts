// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "./style.css";
import { createApp } from "vue";
import App from "./App.vue";
import { initTheme } from "./composables/useTheme";

// Đặt màu nền trước khi mount để trang không nhấp nháy
initTheme();
createApp(App).mount("#app");
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { createApp } from "vue";
import App from "./App.vue";
import "./style.css";
import { initTheme } from "./composables/useTheme";
import { batAnhSang } from "./utils/anhSang";

initTheme();
batAnhSang();
createApp(App).mount("#app");

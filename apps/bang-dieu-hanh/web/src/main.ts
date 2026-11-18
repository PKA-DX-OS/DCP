// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "./styles.css";
import "./style.css";
import { createApp } from "vue";
import App from "./App.vue";
import { khoiTaoSomTheme } from "./utils/anhSang";

khoiTaoSomTheme();
createApp(App).mount("#app");
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class', '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{vue,ts,js}"],
  theme: { extend: {} },
  plugins: [],
};

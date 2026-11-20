// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Màu đặc lấy kênh RGB từ biến CSS (src/style.css); bề mặt kính dùng biến rgba trực tiếp. */
const v = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

/** Token design system (src/design-system/tokens.css), dạng kênh RGB để ghép độ mờ. */
const ds = (name) => `rgb(var(--ds-${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class", '[data-theme="dark"]'],
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        muc: v("muc"),
        "muc-2": v("muc-2"),
        cham: v("cham"),
        son: v("son"),
        giay: v("giay"),
        chu: v("chu"),
        phu: v("phu"),
        xanh: v("xanh"),
        vang: v("vang"),
        lam: v("lam"),
        mat: "var(--mat)",
        "mat-2": "var(--mat-2)",
        "mat-noi": "var(--mat-noi)",
        vien: "var(--vien)",
        "vien-nhat": "var(--vien-nhat)",
        "xanh-nen": "var(--xanh-nen)",
        "vang-nen": "var(--vang-nen)",
        "lam-nen": "var(--lam-nen)",
        "do-nen": "var(--do-nen)",
        "ds-gold": ds("gold"),
        "ds-brand": ds("brand"),
        "ds-on-brand": ds("on-brand"),
        "ds-primary": ds("primary"),
        "ds-on-primary": ds("on-primary"),
        "ds-bg": ds("bg"),
        /* Bề mặt kính trong suốt dùng chung biến với style.css */
        "ds-surface": "var(--mat-2)",
        "ds-surface-2": "var(--mat)",
        "ds-border": "var(--vien)",
        "ds-text": ds("text"),
        "ds-muted": ds("muted"),
        "ds-success": ds("success"),
        "ds-warning": ds("warning"),
        "ds-danger": ds("danger"),
        "ds-info": ds("info"),
      },
      fontSize: {
        "ds-xs": ["var(--ds-text-xs)", { lineHeight: "1.5" }],
        "ds-sm": ["var(--ds-text-sm)", { lineHeight: "1.5" }],
        "ds-base": ["var(--ds-text-base)", { lineHeight: "1.55" }],
        "ds-md": ["var(--ds-text-md)", { lineHeight: "1.5" }],
        "ds-lg": ["var(--ds-text-lg)", { lineHeight: "1.4" }],
        "ds-xl": ["var(--ds-text-xl)", { lineHeight: "1.3" }],
        "ds-2xl": ["var(--ds-text-2xl)", { lineHeight: "1.2" }],
      },
      borderRadius: {
        "ds-sm": "var(--ds-radius-sm)",
        "ds-md": "var(--ds-radius-md)",
        "ds-lg": "var(--ds-radius-lg)",
      },
      boxShadow: {
        ds: "var(--ds-shadow)",
        "ds-lg": "var(--ds-shadow-lg)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Màu đặc lấy kênh RGB từ biến CSS (src/style.css); bề mặt kính dùng biến rgba trực tiếp. */
const v = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
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
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

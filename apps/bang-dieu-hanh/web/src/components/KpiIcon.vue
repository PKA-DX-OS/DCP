<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";

/** Biểu tượng nét cho thẻ chỉ số; vẽ bằng currentColor để theo tông của thẻ ở cả nền sáng và tối. */
const props = defineProps<{ ten?: string }>();

const NET: Record<string, string[]> = {
  // tờ hồ sơ có góc gấp
  ho_so_moi: ["M7 3h7l5 5v13H7z", "M14 3v5h5", "M10 13h6", "M10 17h4"],
  // đồng hồ cát
  ho_so_dang_xu_ly: ["M6 3h12", "M6 21h12", "M8 3v3l4 6-4 6v3", "M16 3v3l-4 6 4 6v3"],
  // tam giác cảnh báo
  ho_so_qua_han: ["M12 4 3 20h18z", "M12 10v4", "M12 17h.01"],
  // đồng hồ
  thoi_gian_xu_ly_tb: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 7v5l3 2"],
  // khiên có gạch chéo
  truy_cap_tu_choi: ["M12 3 5 6v6c0 4 3 7 7 9 4-2 7-5 7-9V6z", "M9.5 9.5l5 5", "M14.5 9.5l-5 5"],
  // bảng kiểm có dấu tích
  phieu_kiem_tra: ["M8 4h8v3H8z", "M6 5H5v16h14V5h-1", "M9 13l2 2 4-4"],
  // tháp tín hiệu cảm biến
  canh_bao_cong_truong: ["M12 12v9", "M9 21h6", "M8.5 8.5a5 5 0 0 1 7 0", "M6 6a8.5 8.5 0 0 1 12 0", "M12 12h.01"],
  // cán cân
  // ghim bản đồ có gạch chéo: không đạt quy hoạch
  ho_so_fail_quy_hoach: ["M12 21s-6-5.5-6-11a6 6 0 0 1 12 0c0 5.5-6 11-6 11z", "M10 8l4 4", "M14 8l-4 4"],
  // khối công trình có móng
  ho_so_dang_nghiem_thu: ["M4 21h16", "M6 21V9l6-4 6 4v12", "M10 21v-5h4v5", "M9 11h6"],
  // vòng tròn có dấu tích
  ty_le_dung_han: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M8 12l3 3 5-6"],
  vi_pham: ["M12 4v16", "M8 20h8", "M5 7h14", "M5 7l-3 6a3 3 0 0 0 6 0z", "M19 7l-3 6a3 3 0 0 0 6 0z"],
};

const duong = computed(() => NET[props.ten || ""] || ["M12 12h.01"]);
</script>

<template>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path v-for="(d, i) in duong" :key="i" :d="d" />
  </svg>
</template>

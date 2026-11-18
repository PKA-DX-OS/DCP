<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import LogoMark from "./LogoMark.vue";
import IconX from "./IconX.vue";
import { useTheme } from "../composables/useTheme";

defineProps<{
  tab: string;
  tabs: { ma: string; ten: string }[];
  tenNguoiDung: string;
  chuaDoc: number;
  trangThaiKetNoi: string;
}>();
const emit = defineEmits<{
  (e: "chuyen-tab", ma: string): void;
  (e: "dang-xuat"): void;
  (e: "da-doc"): void;
}>();
const { theme, toggle } = useTheme();
</script>

<template>
  <header class="the flex flex-wrap items-center gap-3 px-4 py-3">
    <div class="flex items-center gap-2">
      <LogoMark :size="26" />
      <span class="font-semibold">Cấp phép xây dựng</span>
    </div>

    <nav class="flex flex-wrap gap-1" aria-label="Điều hướng">
      <button
        v-for="t in tabs"
        :key="t.ma"
        class="rounded px-3 py-1 text-sm"
        :class="tab === t.ma ? 'nhan-nen font-semibold' : 'text-phu'"
        :aria-current="tab === t.ma ? 'page' : undefined"
        @click="emit('chuyen-tab', t.ma)"
      >
        {{ t.ten }}
      </button>
    </nav>

    <div class="flex-1"></div>

    <span class="goi-y">
      {{ trangThaiKetNoi === "da_ket_noi" ? "Trực tuyến" : trangThaiKetNoi === "mat_ket_noi" ? "Mất kết nối, đang thử lại" : "Đang kết nối" }}
    </span>
    <button class="btn-sm" :aria-label="`Thông báo, ${chuaDoc} chưa đọc`" @click="emit('da-doc')">
      <IconX name="shield" :size="16" />
      <span class="ml-1">{{ chuaDoc }}</span>
    </button>
    <button class="btn-sm" @click="toggle()">{{ theme === "dark" ? "Nền sáng" : "Nền tối" }}</button>
    <span class="goi-y">{{ tenNguoiDung }}</span>
    <button class="btn-sm" @click="emit('dang-xuat')">Đăng xuất</button>
  </header>
</template>
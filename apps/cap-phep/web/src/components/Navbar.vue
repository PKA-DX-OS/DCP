<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { ref } from "vue";
import LogoMark from "./LogoMark.vue";
import { useTheme } from "../composables/useTheme";
import type { ThongBao } from "../composables/useNotifications";

defineProps<{
  tab: string;
  tabs: { ma: string; ten: string }[];
  tenNguoiDung: string;
  chuaDoc: number;
  danhSach: ThongBao[];
  trangThaiKetNoi: string;
}>();
const emit = defineEmits<{
  (e: "chuyen-tab", ma: string): void;
  (e: "dang-xuat"): void;
  (e: "da-doc"): void;
  (e: "doc-mot", id: string): void;
}>();
const { theme, toggle } = useTheme();
const moThongBao = ref(false);
function chonThongBao(item: ThongBao) {
  emit("doc-mot", item.id);
  moThongBao.value = false;
  if (item.link) window.location.href = item.link;
}
function ngayGio(value: string | null): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "";
}
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
    <div class="relative">
      <button
        class="btn-sm"
        :aria-label="`Thông báo, ${chuaDoc} chưa đọc`"
        :aria-expanded="moThongBao"
        aria-haspopup="true"
        @click="moThongBao = !moThongBao"
      >
        <span aria-hidden="true">🔔</span>
        <span class="ml-1">{{ chuaDoc }}</span>
      </button>
      <div v-if="moThongBao" class="fixed inset-0 z-10" aria-hidden="true" @click="moThongBao = false"></div>
      <div v-if="moThongBao" class="absolute right-0 z-20 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-vien bg-mat p-3 shadow-xl">
        <div class="flex items-center justify-between gap-2">
          <b class="text-sm">Thông báo</b>
          <button class="text-xs underline text-phu" @click="emit('da-doc')">Đánh dấu tất cả đã đọc</button>
        </div>
        <ul v-if="danhSach.length" class="mt-2 max-h-80 list-none space-y-1 overflow-y-auto p-0">
          <li v-for="item in danhSach" :key="item.id">
            <button type="button" class="flex w-full gap-2 rounded p-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800" @click="chonThongBao(item)">
              <span class="mt-1.5 h-2 w-2 shrink-0 rounded-full" :class="item.read_at ? 'bg-slate-300' : 'bg-sky-500'" aria-hidden="true"></span>
              <span class="min-w-0">
                <span class="block font-medium">{{ item.title }}</span>
                <span class="block text-xs text-phu">{{ item.body }}</span>
                <span class="block text-[11px] text-phu">{{ ngayGio(item.created_at) }}</span>
              </span>
            </button>
          </li>
        </ul>
        <p v-else class="mt-2 text-sm text-phu">Chưa có thông báo.</p>
      </div>
    </div>
    <button class="btn-sm" @click="toggle()">{{ theme === "dark" ? "Nền sáng" : "Nền tối" }}</button>
    <span class="goi-y">{{ tenNguoiDung }}</span>
    <button class="btn-sm" @click="emit('dang-xuat')">Đăng xuất</button>
  </header>
</template>
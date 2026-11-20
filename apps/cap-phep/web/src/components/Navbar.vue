<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { ref } from "vue";
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
  <div class="w-full">
    <!-- Banner mô phỏng cuộc thi -->
    <div class="bg-amber-400 px-4 py-1.5 text-center text-[11px] font-bold uppercase tracking-wide text-slate-900 shadow-sm">
      Bản mô phỏng phục vụ cuộc thi OLP Tin học Sinh viên PMNM 2026 — Dữ liệu hu cấu (mẫu), giấy phép không có giá trị pháp lý
    </div>

    <!-- Header chính -->
    <header class="sticky top-0 z-30 bg-indigo-900 text-white shadow-md">
      <div class="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-lg border border-indigo-500 bg-indigo-700 text-xl font-bold shadow">
            DX
          </div>
          <div>
            <h1 class="text-lg font-extrabold leading-tight tracking-tight">DX-OS OPEN-CORE</h1>
            <p class="text-xs text-indigo-200">Dịch vụ Cấp phép Xây dựng Nhà ở Riêng lẻ (Tầng 2 - C3)</p>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <span class="hidden text-xs text-indigo-200 sm:inline">
            {{ trangThaiKetNoi === "da_ket_noi" ? "Trực tuyến" : trangThaiKetNoi === "mat_ket_noi" ? "Mất kết nối, đang thử lại" : "Đang kết nối" }}
          </span>

          <div class="relative">
            <button
              id="btn-sse-bell"
              class="relative rounded-lg border border-indigo-600 bg-indigo-800 p-2 text-sm transition hover:bg-indigo-700"
              :aria-label="`Thông báo, ${chuaDoc} chưa đọc`"
              :aria-expanded="moThongBao"
              aria-haspopup="true"
              @click="moThongBao = !moThongBao"
            >
              <span aria-hidden="true">🔔</span>
              <span
                v-if="chuaDoc > 0"
                class="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white shadow"
              >
                {{ chuaDoc }}
              </span>
            </button>

            <div v-if="moThongBao" class="fixed inset-0 z-10" aria-hidden="true" @click="moThongBao = false"></div>
            <div
              v-if="moThongBao"
              class="absolute right-0 z-20 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-xl border border-slate-200 bg-white p-3 text-slate-800 shadow-xl"
            >
              <div class="flex items-center justify-between gap-2 border-b border-slate-200 pb-2">
                <b class="text-sm">Thông báo</b>
                <button class="text-xs font-medium text-indigo-600 underline" @click="emit('da-doc')">Đánh dấu tất cả đã đọc</button>
              </div>
              <ul v-if="danhSach.length" class="mt-2 max-h-80 list-none space-y-1 overflow-y-auto p-0">
                <li v-for="item in danhSach" :key="item.id">
                  <button
                    type="button"
                    class="flex w-full gap-2 rounded-lg p-2 text-left text-sm transition hover:bg-slate-50"
                    @click="chonThongBao(item)"
                  >
                    <span class="mt-1.5 h-2 w-2 shrink-0 rounded-full" :class="item.read_at ? 'bg-slate-300' : 'bg-indigo-500'" aria-hidden="true"></span>
                    <span class="min-w-0">
                      <span class="block font-medium">{{ item.title }}</span>
                      <span class="block text-xs text-slate-500">{{ item.body }}</span>
                      <span class="block text-[11px] text-slate-400">{{ ngayGio(item.created_at) }}</span>
                    </span>
                  </button>
                </li>
              </ul>
              <p v-else class="mt-2 text-sm text-slate-500">Chưa có thông báo.</p>
            </div>
          </div>

          <button
            class="rounded-lg border border-indigo-600 bg-indigo-800 px-3 py-1.5 text-xs transition hover:bg-indigo-700"
            @click="toggle()"
          >
            {{ theme === "dark" ? "Nền sáng" : "Nền tối" }}
          </button>

          <span class="hidden text-right text-xs leading-tight sm:block">
            <span class="block font-semibold">{{ tenNguoiDung }}</span>
            <span class="block text-indigo-300">Tài khoản đã xác thực</span>
          </span>

          <a
            href="/dieu-hanh/"
            class="rounded-lg border border-indigo-600 bg-indigo-800 px-3 py-1.5 text-xs transition hover:bg-indigo-700"
          >
            Bảng điều hành
          </a>
          <button
            class="rounded-lg border border-indigo-600 bg-indigo-800 px-3 py-1.5 text-xs transition hover:bg-indigo-700"
            @click="emit('dang-xuat')"
          >
            Đăng xuất
          </button>
        </div>
      </div>

      <!-- Tab điều hướng -->
      <nav class="border-t border-indigo-800 bg-white" aria-label="Điều hướng">
        <div class="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-4">
          <button
            v-for="t in tabs"
            :key="t.ma"
            class="whitespace-nowrap border-b-2 px-3 py-3 text-sm font-semibold transition"
            :class="
              tab === t.ma
                ? 'border-indigo-600 text-indigo-700'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800'
            "
            :aria-current="tab === t.ma ? 'page' : undefined"
            @click="emit('chuyen-tab', t.ma)"
          >
            {{ t.ten }}
          </button>
        </div>
      </nav>
    </header>
  </div>
</template>

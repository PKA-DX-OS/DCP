<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import LogoMark from "./LogoMark.vue";
import { useTheme } from "../composables/useTheme";
import { useVachTab } from "../composables/useVachTab";
import { vaiChinh } from "../utils/labels";
import type { ThongBao } from "../composables/useNotifications";

const props = withDefaults(
  defineProps<{
    tab: string;
    tabs: { ma: string; ten: string }[];
    tenNguoiDung: string;
    chuaDoc: number;
    danhSach: ThongBao[];
    trangThaiKetNoi: string;
    vaiTro?: string[];
    donVi?: string;
  }>(),
  { vaiTro: () => [], donVi: "Hệ thống cấp phép" },
);
const emit = defineEmits<{
  (e: "chuyen-tab", ma: string): void;
  (e: "dang-xuat"): void;
  (e: "dang-nhap"): void;
  (e: "da-doc"): void;
  (e: "doc-mot", id: string): void;
  (e: "mo-tim-kiem"): void;
}>();

const { theme, toggle } = useTheme();
const moThongBao = ref(false);
const bellWrap = ref<HTMLElement | null>(null);
const tabNav = ref<HTMLElement | null>(null);
const tabDangMo = computed(() => props.tab);
const vachKieu = useVachTab(tabNav, tabDangMo);

const daDangNhap = computed(() => Boolean(props.tenNguoiDung));
const vai = computed(() => vaiChinh(props.vaiTro));
const initials = computed(() => {
  const ten = props.tenNguoiDung.trim();
  if (!ten) return "U";
  const parts = ten.split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
});
const xemDieuHanh = computed(() =>
  (props.vaiTro || []).some((r) =>
    ["app:cap-phep:lanh-dao", "dx:tenant-admin", "dx:platform-admin", "dx:auditor"].includes(r),
  ),
);

function chonThongBao(item: ThongBao) {
  emit("doc-mot", item.id);
  moThongBao.value = false;
  if (item.link) window.location.href = item.link;
}
function ngayGio(value: string | null): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "";
}
function onDocClick(e: MouseEvent) {
  if (moThongBao.value && bellWrap.value && !bellWrap.value.contains(e.target as Node)) {
    moThongBao.value = false;
  }
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") moThongBao.value = false;
}
onMounted(() => {
  document.addEventListener("click", onDocClick);
  document.addEventListener("keydown", onKey);
});
onUnmounted(() => {
  document.removeEventListener("click", onDocClick);
  document.removeEventListener("keydown", onKey);
});
</script>

<template>
  <header class="thanh-tren sticky top-0 z-30 text-chu">
    <div class="mx-auto flex h-[72px] max-w-[1320px] items-center gap-3 px-4 sm:px-6">
      <LogoMark :size="40" ink="currentColor" frame="var(--vien)" />
      <div class="flex min-w-0 flex-col leading-tight">
        <b class="truncate text-[15px] font-semibold">{{ donVi }}</b>
        <span class="truncate text-[12.5px] text-phu">Cấp phép xây dựng nhà ở riêng lẻ</span>
      </div>
      <div class="flex-1"></div>

      <span class="hidden text-[12px] text-phu lg:inline">
        {{ trangThaiKetNoi === "da_ket_noi" ? "Trực tuyến" : trangThaiKetNoi === "mat_ket_noi" ? "Mất kết nối" : "Đang kết nối" }}
      </span>

      <button
        v-if="daDangNhap"
        id="btn-global-search"
        type="button"
        class="nut-tren"
        aria-label="Tìm kiếm toàn cục"
        title="Tìm kiếm toàn cục (Ctrl+K)"
        @click="emit('mo-tim-kiem')"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" />
          <path d="m16 16 4.5 4.5" />
        </svg>
      </button>

      <button
        type="button"
        class="nut-tren nut-giao-dien"
        :aria-label="theme === 'dark' ? 'Nền sáng' : 'Nền tối'"
        :title="theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'"
        @click="toggle"
      >
        <svg v-if="theme === 'dark'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4.2" />
          <path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" />
        </svg>
        <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
          <path d="M20.5 13.2A8.5 8.5 0 1 1 10.8 3.5a6.6 6.6 0 0 0 9.7 9.7z" />
        </svg>
      </button>

      <div ref="bellWrap" class="relative">
        <button
          id="btn-sse-bell"
          type="button"
          class="nut-tren nut-chuong"
          :aria-label="chuaDoc > 0 ? `Thông báo, ${chuaDoc} chưa đọc` : 'Thông báo'"
          :aria-expanded="moThongBao"
          aria-haspopup="true"
          @click="moThongBao = !moThongBao"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true">
            <path d="M6 8.5a6 6 0 1 1 12 0c0 6.5 2.8 7.8 2.8 7.8H3.2S6 15 6 8.5z" />
            <path d="M10 20a2 2 0 0 0 4 0" />
          </svg>
          <span
            v-if="chuaDoc > 0"
            id="badge-unread-count"
            class="absolute -right-1 -top-1 h-[18px] min-w-[18px] rounded-full bg-[rgb(var(--c-cham-nen))] px-1 text-center text-[11px] font-semibold leading-[18px] text-[#060a13]"
          >{{ chuaDoc > 99 ? "99+" : chuaDoc }}</span>
        </button>

        <div
          v-if="moThongBao"
          id="dropdown-notifications"
          class="hop tha-xuong absolute right-0 z-50 mt-3 w-[380px] max-w-[calc(100vw-32px)] !rounded-[24px] text-chu"
          role="dialog"
          aria-label="Thông báo"
        >
          <div class="flex items-center justify-between border-b border-vien-nhat px-5 pb-3 pt-4">
            <span class="font-semibold">Thông báo</span>
            <button type="button" id="btn-mark-all-read" class="btn-lien-ket text-[13px]" @click="emit('da-doc')">
              Đánh dấu đã đọc
            </button>
          </div>
          <div v-if="!danhSach.length" id="empty-notifications" class="px-4 py-8 text-center text-[13px] text-phu">
            Chưa có thông báo nào.
          </div>
          <ul v-else id="list-notifications" class="m-0 max-h-[360px] list-none overflow-y-auto p-0 py-1">
            <li v-for="(n, idx) in danhSach" :key="n.id || idx">
              <button
                type="button"
                class="flex w-full gap-2.5 px-5 py-3 text-left transition-colors duration-500 hover:bg-mat-2"
                @click="chonThongBao(n)"
              >
                <span :class="['mt-1.5 h-2 w-2 flex-shrink-0 rounded-full', n.read_at ? 'bg-transparent' : 'bg-cham']" aria-hidden="true"></span>
                <span class="min-w-0 flex-1">
                  <span class="flex justify-between gap-2">
                    <span :class="['text-[13.5px]', n.read_at ? 'font-normal' : 'font-semibold']">{{ n.title }}</span>
                    <span class="mo whitespace-nowrap">{{ ngayGio(n.created_at) }}</span>
                  </span>
                  <span class="mt-0.5 block text-[13px] text-phu">{{ n.body }}</span>
                  <span v-if="n.link" class="mt-0.5 block text-[12.5px] text-lam">Mở chi tiết</span>
                </span>
              </button>
            </li>
          </ul>
        </div>
      </div>

      <template v-if="daDangNhap">
        <a v-if="xemDieuHanh" href="/dieu-hanh/" class="nut-tren nut-chu hidden md:inline-grid">Bảng điều hành</a>
        <div class="hidden items-center gap-2.5 pl-1.5 sm:flex">
          <div class="grid h-8 w-8 place-items-center rounded-full bg-mat-noi text-[12.5px] font-semibold" aria-hidden="true">{{ initials }}</div>
          <div class="leading-tight">
            <div class="text-[13.5px] font-medium">{{ tenNguoiDung }}</div>
            <div class="text-[12px] text-phu">{{ vai }}</div>
          </div>
        </div>
        <button type="button" class="nut-tren nut-chu" @click="emit('dang-xuat')">Đăng xuất</button>
      </template>
      <template v-else>
        <button type="button" class="btn btn-sm btn-chinh" @click="emit('dang-nhap')">Đăng nhập</button>
      </template>
    </div>

    <nav
      v-if="daDangNhap && tabs.length"
      ref="tabNav"
      class="relative mx-auto flex h-[46px] max-w-[1320px] gap-7 overflow-x-auto px-4 sm:px-6"
      aria-label="Điều hướng"
    >
      <button
        v-for="t in tabs"
        :key="t.ma"
        type="button"
        class="tab-chinh"
        :class="tab === t.ma && 'tab-dang-mo'"
        :aria-current="tab === t.ma ? 'page' : undefined"
        @click="emit('chuyen-tab', t.ma)"
      >
        {{ t.ten }}
      </button>
      <span class="vach-tab" :style="vachKieu" aria-hidden="true"></span>
    </nav>
  </header>
</template>

<style scoped>
.nut-tren {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 16px;
  border: 1px solid var(--vien);
  background: var(--mat);
  color: rgb(var(--c-chu));
  display: inline-grid;
  place-items: center;
  transition: background 500ms var(--em), border-color 500ms var(--em), transform 500ms var(--em);
}
.nut-tren:hover {
  background: var(--mat-noi);
  border-color: var(--vien-noi);
  transform: translateY(-1px);
}
.nut-giao-dien svg { transition: transform 500ms var(--em); }
.nut-giao-dien:hover svg { transform: rotate(30deg); }
.nut-chuong:hover svg {
  transform-origin: 50% 10%;
  animation: chuong-lac 700ms var(--em);
}
@keyframes chuong-lac {
  20% { transform: rotate(14deg); }
  45% { transform: rotate(-10deg); }
  70% { transform: rotate(5deg); }
}
.nut-chu {
  width: auto;
  padding: 0 14px;
  font-size: 13px;
  white-space: nowrap;
}
.tab-chinh {
  position: relative;
  background: none;
  border: 0;
  padding: 0;
  color: rgb(var(--c-phu));
  transition: color 500ms var(--em);
  font-weight: 500;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
}
.tab-chinh:hover,
.tab-dang-mo {
  color: rgb(var(--c-chu));
}
</style>

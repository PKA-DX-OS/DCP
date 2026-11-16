<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <header class="thanh-tren sticky top-0 z-30 text-chu">
    <div class="max-w-[1320px] mx-auto px-4 sm:px-6 h-[72px] flex items-center gap-3">
      <LogoMark ink="currentColor" frame="var(--vien)" />
      <div class="flex flex-col leading-tight min-w-0">
        <b class="font-semibold text-[15px] truncate">{{ donVi }}</b>
        <span class="text-[12.5px] text-phu truncate">Cấp phép xây dựng nhà ở riêng lẻ</span>
      </div>
      <div class="flex-1"></div>

      <button
        type="button"
        class="nut-tren nut-giao-dien"
        :aria-label="theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'"
        :title="theme === 'dark' ? 'Giao diện sáng' : 'Giao diện tối'"
        @click="toggle"
      >
        <svg v-if="theme === 'dark'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2" /><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" /></svg>
        <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M20.5 13.2A8.5 8.5 0 1 1 10.8 3.5a6.6 6.6 0 0 0 9.7 9.7z" /></svg>
      </button>

      <template v-if="user">
        <div class="relative" ref="bellWrap">
          <button
            type="button"
            id="btn-sse-bell"
            class="nut-tren nut-chuong"
            :aria-label="unreadCount > 0 ? `Thông báo, ${unreadCount} chưa đọc` : 'Thông báo'"
            :aria-expanded="showNotifications"
            @click="showNotifications = !showNotifications"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path d="M6 8.5a6 6 0 1 1 12 0c0 6.5 2.8 7.8 2.8 7.8H3.2S6 15 6 8.5z" /><path d="M10 20a2 2 0 0 0 4 0" /></svg>
            <span
              v-if="unreadCount > 0"
              id="badge-unread-count"
              class="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-[rgb(var(--c-cham-nen))] text-[#060a13] text-[11px] font-semibold leading-[18px] text-center"
            >{{ unreadCount }}</span>
          </button>

          <div
            v-if="showNotifications"
            id="dropdown-notifications"
            class="hop tha-xuong !rounded-[24px] absolute right-0 mt-3 w-[380px] max-w-[calc(100vw-32px)] text-chu z-50"
            role="dialog"
            aria-label="Thông báo"
          >
            <div class="flex items-center justify-between px-5 pt-4 pb-3 border-b border-vien-nhat">
              <span class="font-semibold">Thông báo</span>
              <button type="button" id="btn-mark-all-read" class="btn-lien-ket text-[13px]" @click="$emit('clear-unread')">
                Đánh dấu đã đọc
              </button>
            </div>
            <div v-if="notifications.length === 0" id="empty-notifications" class="px-4 py-8 text-center text-phu text-[13px]">
              Chưa có thông báo nào.
            </div>
            <ul v-else id="list-notifications" class="max-h-[360px] overflow-y-auto py-1 m-0 list-none p-0">
              <li v-for="(n, idx) in notifications" :key="n.id || idx">
                <button
                  type="button"
                  class="w-full text-left px-5 py-3 hover:bg-mat-2 flex gap-2.5 transition-colors duration-500"
                  @click="choose(n)"
                >
                  <span :class="['mt-1.5 w-2 h-2 rounded-full flex-shrink-0', n.read_at ? 'bg-transparent' : 'bg-cham']" aria-hidden="true"></span>
                  <span class="min-w-0 flex-1">
                    <span class="flex justify-between gap-2">
                      <span :class="['text-[13.5px]', n.read_at ? 'font-normal' : 'font-semibold']">{{ n.title }}</span>
                      <span class="mo whitespace-nowrap">{{ formatTime(n.created_at || n.time) }}</span>
                    </span>
                    <span class="block text-[13px] text-phu mt-0.5">{{ n.body || n.content }}</span>
                    <span v-if="n.ma_ho_so" class="block text-[12.5px] text-lam mt-0.5">{{ n.ma_ho_so }}</span>
                  </span>
                </button>
              </li>
            </ul>
          </div>
        </div>

        <a v-if="xemDieuHanh" href="/dieu-hanh/" class="nut-tren nut-chu hidden md:inline-grid">Bảng điều hành</a>
        <div class="hidden sm:flex items-center gap-2.5 pl-1.5">
          <div class="w-8 h-8 rounded-full bg-mat-noi grid place-items-center font-semibold text-[12.5px]" aria-hidden="true">{{ initials }}</div>
          <div class="leading-tight">
            <div class="text-[13.5px] font-medium">{{ user.profile.name || user.profile.preferred_username }}</div>
            <div class="text-[12px] text-phu">{{ vai }}</div>
          </div>
        </div>
        <button type="button" class="nut-tren nut-chu" @click="$emit('logout')">Đăng xuất</button>
      </template>
      <template v-else>
        <button type="button" class="btn btn-sm btn-chinh" @click="$emit('login')">Đăng nhập</button>
      </template>
    </div>
    <slot name="tabs" />
  </header>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from "vue";
import LogoMark from "./LogoMark.vue";
import { useTheme } from "../composables/useTheme";
import { tenDonVi, vaiChinh } from "../utils/labels";

const props = defineProps<{
  user: any;
  loading: boolean;
  notifications: any[];
  unreadCount: number;
  tenant?: string;
  roles?: string[];
}>();

const emit = defineEmits<{
  (e: "login"): void;
  (e: "logout"): void;
  (e: "clear-unread"): void;
  (e: "select-notification", notification: any): void;
}>();

const { theme, toggle } = useTheme();
const showNotifications = ref(false);
const bellWrap = ref<HTMLElement | null>(null);

const donVi = computed(() => tenDonVi(props.tenant));
const vai = computed(() => vaiChinh(props.roles));
// Lối sang Bảng điều hành cho những vai được xem bảng đó (cùng danh sách với apps/bang-dieu-hanh)
const VAI_DIEU_HANH = ["app:cap-phep:lanh-dao", "dx:tenant-admin", "dx:platform-admin", "dx:auditor"];
const xemDieuHanh = computed(() => (props.roles || []).some((r) => VAI_DIEU_HANH.includes(r)));
const initials = computed(() => {
  const name = String(props.user?.profile?.name || props.user?.profile?.preferred_username || "");
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
});

function choose(n: any) {
  emit("select-notification", n);
}

function onDocClick(e: MouseEvent) {
  if (showNotifications.value && bellWrap.value && !bellWrap.value.contains(e.target as Node)) {
    showNotifications.value = false;
  }
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") showNotifications.value = false;
}
onMounted(() => {
  document.addEventListener("click", onDocClick);
  document.addEventListener("keydown", onKey);
});
onUnmounted(() => {
  document.removeEventListener("click", onDocClick);
  document.removeEventListener("keydown", onKey);
});

function formatTime(isoOrText: string): string {
  if (!isoOrText) return "";
  if (isoOrText.includes(":") && !isoOrText.includes("T")) return isoOrText;
  const d = new Date(isoOrText);
  if (isNaN(d.getTime())) return isoOrText;
  return d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }) + " " + d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
}
</script>

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
/* Biểu tượng mặt trời / trăng xoay nhẹ, chuông rung một nhịp khi trỏ vào */
.nut-giao-dien svg {
  transition: transform 500ms var(--em);
}
.nut-giao-dien:hover svg {
  transform: rotate(30deg);
}
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
</style>

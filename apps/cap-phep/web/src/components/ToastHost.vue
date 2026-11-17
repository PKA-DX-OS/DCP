<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div class="fixed z-[60] bottom-4 right-4 left-4 sm:left-auto flex flex-col gap-2 items-stretch sm:items-end pointer-events-none" aria-live="polite">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="hop thong-diep pointer-events-auto sm:w-[380px] px-4 py-3 flex items-start gap-3 text-[13.5px]"
      :role="t.kind === 'loi' || t.kind === 'canh_bao' ? 'alert' : 'status'"
    >
      <span :class="['mt-1.5 w-2 h-2 rounded-full flex-shrink-0', mauCham[t.kind]]" aria-hidden="true"></span>
      <span class="flex-1">{{ t.text }}</span>
      <button type="button" class="nut-dong -mr-1 -mt-1" aria-label="Đóng thông báo" @click="dismiss(t.id)">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useToasts } from "../composables/useToast";
import type { ToastKind } from "../composables/useToast";
const { toasts, dismiss } = useToasts();
const mauCham: Record<ToastKind, string> = { ok: "bg-xanh", loi: "bg-son", canh_bao: "bg-vang", tin: "bg-lam" };
</script>

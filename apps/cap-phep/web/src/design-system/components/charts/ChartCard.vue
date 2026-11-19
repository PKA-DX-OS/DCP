<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { ref } from "vue";

/**
 * Khung biểu đồ: tiêu đề, mô tả, nút xem dạng bảng. Bảng dữ liệu luôn có cho trình đọc màn hình;
 * người dùng bấm "Xem bảng số liệu" để thấy bằng mắt.
 */
defineProps<{ title: string; subtitle?: string; empty?: boolean; emptyText?: string }>();
const hienBang = ref(false);
</script>

<template>
  <section class="flex flex-col gap-3 ds-glass p-4">
    <header class="flex items-start justify-between gap-3">
      <div>
        <h3 class="m-0 text-ds-md font-semibold text-ds-text">{{ title }}</h3>
        <p v-if="subtitle" class="m-0 text-ds-sm text-ds-muted">{{ subtitle }}</p>
      </div>
      <button
        v-if="!empty && $slots.table"
        type="button"
        class="ds-focus shrink-0 rounded-ds-sm px-2 py-1 text-ds-xs text-ds-muted hover:bg-ds-surface-2"
        :aria-pressed="hienBang"
        @click="hienBang = !hienBang"
      >
        {{ hienBang ? "Xem biểu đồ" : "Xem bảng số liệu" }}
      </button>
    </header>
    <p v-if="empty" class="m-0 py-8 text-center text-ds-sm text-ds-muted">{{ emptyText || "Chưa có dữ liệu" }}</p>
    <template v-else>
      <div v-show="!hienBang" aria-hidden="true"><slot /></div>
      <div :class="hienBang ? '' : 'sr-only'"><slot name="table" /></div>
      <slot name="legend" />
    </template>
  </section>
</template>

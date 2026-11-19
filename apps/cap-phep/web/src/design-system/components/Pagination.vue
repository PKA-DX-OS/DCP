<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import { pageCount, pageItems } from "../variants";

const props = withDefaults(defineProps<{ total: number; pageSize?: number }>(), { pageSize: 20 });
const page = defineModel<number>({ default: 1 });
const pages = computed(() => pageCount(props.total, props.pageSize));
const items = computed(() => pageItems(props.total, props.pageSize, page.value));
const from = computed(() => (props.total ? (page.value - 1) * props.pageSize + 1 : 0));
const to = computed(() => Math.min(props.total, page.value * props.pageSize));
function go(p: number) {
  page.value = Math.min(Math.max(1, p), pages.value);
}
const btn =
  "ds-focus flex h-9 min-w-9 items-center justify-center rounded-ds-sm px-2 text-ds-sm disabled:cursor-not-allowed disabled:opacity-40";
</script>

<template>
  <nav class="flex flex-wrap items-center justify-between gap-3" aria-label="Phân trang">
    <p class="m-0 text-ds-sm text-ds-muted">{{ from }}–{{ to }} trên {{ total.toLocaleString("vi-VN") }}</p>
    <ul class="m-0 flex list-none items-center gap-1 p-0">
      <li><button type="button" :class="btn" :disabled="page <= 1" aria-label="Trang trước" @click="go(page - 1)">‹</button></li>
      <li v-for="(it, i) in items" :key="i">
        <span v-if="it === '…'" class="px-1 text-ds-muted" aria-hidden="true">…</span>
        <button
          v-else
          type="button"
          :class="[btn, it === page ? 'bg-ds-primary font-semibold text-ds-on-primary' : 'text-ds-text hover:bg-ds-surface-2']"
          :aria-current="it === page ? 'page' : undefined"
          @click="go(it)"
        >
          {{ it }}
        </button>
      </li>
      <li><button type="button" :class="btn" :disabled="page >= pages" aria-label="Trang sau" @click="go(page + 1)">›</button></li>
    </ul>
  </nav>
</template>

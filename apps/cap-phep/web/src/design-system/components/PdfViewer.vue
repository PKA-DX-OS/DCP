<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, ref } from "vue";
import Button from "./Button.vue";

/**
 * Xem PDF bằng trình xem sẵn có của trình duyệt (không đọc CAD). `src` nên là blob URL đã tải
 * qua dịch vụ files kèm token, để không lộ đường dẫn kho lưu trữ.
 */
const props = defineProps<{ src: string; title: string; filename?: string }>();
const MUC = [50, 75, 100, 125, 150, 200];
const zoom = ref(100);
const url = computed(() => `${props.src}#zoom=${zoom.value}&toolbar=0`);
function doi(step: number) {
  const i = MUC.indexOf(zoom.value);
  zoom.value = MUC[Math.min(MUC.length - 1, Math.max(0, i + step))];
}
</script>

<template>
  <div class="flex h-full min-h-[60vh] flex-col gap-2">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-1" role="group" aria-label="Phóng to, thu nhỏ">
        <Button variant="secondary" size="sm" :disabled="zoom <= MUC[0]" aria-label="Thu nhỏ" @click="doi(-1)">−</Button>
        <span class="w-14 text-center text-ds-sm tabular-nums text-ds-text" aria-live="polite">{{ zoom }}%</span>
        <Button variant="secondary" size="sm" :disabled="zoom >= MUC[MUC.length - 1]" aria-label="Phóng to" @click="doi(1)">+</Button>
      </div>
      <a
        :href="src"
        :download="filename || title"
        class="ds-focus inline-flex h-8 items-center rounded-ds-sm border border-ds-border px-3 text-ds-sm font-semibold text-ds-text hover:bg-ds-surface-2"
      >
        Tải về
      </a>
    </div>
    <iframe :key="url" :src="url" :title="title" class="w-full flex-1 rounded-ds-sm border border-ds-border bg-white" />
  </div>
</template>

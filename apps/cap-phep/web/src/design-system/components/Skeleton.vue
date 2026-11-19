<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
withDefaults(defineProps<{ lines?: number; height?: string; rounded?: string }>(), {
  lines: 1,
  height: "1rem",
  rounded: "rounded-ds-sm",
});
</script>

<template>
  <div class="flex flex-col gap-2" role="status" aria-live="polite">
    <span class="sr-only">Đang tải…</span>
    <div
      v-for="i in lines"
      :key="i"
      class="ds-skeleton"
      :class="rounded"
      :style="{ height, width: i === lines && lines > 1 ? '60%' : '100%' }"
      aria-hidden="true"
    />
  </div>
</template>

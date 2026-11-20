<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { chartColor } from "./geometry";

defineProps<{ items: Array<{ label: string; value?: number | string }> }>();
</script>

<template>
  <ul class="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-ds-sm">
    <li v-for="(it, i) in items" :key="it.label" class="flex items-center gap-2 text-ds-text">
      <span class="h-2.5 w-2.5 rounded-full" :style="{ background: chartColor(i) }" aria-hidden="true" />
      {{ it.label }}
      <span v-if="it.value !== undefined" class="tabular-nums text-ds-muted">{{ it.value }}</span>
    </li>
  </ul>
</template>

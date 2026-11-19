<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import { sparkPath } from "./geometry";

const props = withDefaults(defineProps<{ values: number[]; width?: number; height?: number; label?: string }>(), {
  width: 80,
  height: 24,
});
const d = computed(() => sparkPath(props.values, props.width, props.height - 2));
</script>

<template>
  <svg
    v-if="d"
    :width="width"
    :height="height"
    :viewBox="`0 -1 ${width} ${height}`"
    role="img"
    :aria-label="label || 'Xu hướng: ' + values.join(', ')"
  >
    <path :d="d" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
  </svg>
</template>

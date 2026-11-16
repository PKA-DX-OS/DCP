<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <svg :width="size" :height="size" viewBox="0 0 34 34" aria-hidden="true" class="flex-shrink-0">
    <rect x="1" y="1" width="32" height="32" rx="7" fill="none" :stroke="frame" />
    <path d="M8 17 17 9l9 8" fill="none" :stroke="ink" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M11 16v9h12v-9" fill="none" :stroke="ink" stroke-width="2.2" stroke-linejoin="round" />
    <path d="M14.5 20.5l2 2 3.5-3.6" fill="none" stroke="#E0584D" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number; ink?: string; frame?: string }>(), {
  size: 34,
  ink: "#ffffff",
  frame: "rgba(255,255,255,.55)",
});
</script>

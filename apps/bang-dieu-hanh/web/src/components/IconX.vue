<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
defineProps<{
  name: "chart" | "shield" | "bot" | "close";
  size?: number;
}>();
</script>

<template>
  <svg
    :width="size ?? 20"
    :height="size ?? 20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-if="name === 'chart'" d="M3 3v18h18M7 14l3-3 3 2 5-6" />
    <path
      v-else-if="name === 'shield'"
      d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z"
    />
    <g v-else-if="name === 'bot'">
      <rect x="5" y="8" width="14" height="10" rx="2" />
      <path d="M12 4v4M9 13h.01M15 13h.01" />
    </g>
    <path v-else d="M6 6l12 12M18 6L6 18" />
  </svg>
</template>

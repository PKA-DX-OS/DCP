<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
defineProps<{ size?: number }>();
</script>

<template>
  <svg
    :width="size ?? 28"
    :height="size ?? 28"
    viewBox="0 0 32 32"
    aria-label="DX-OS"
    role="img"
  >
    <rect
      x="2"
      y="2"
      width="28"
      height="28"
      rx="8"
      fill="currentColor"
      opacity="0.15"
    />
    <path
      d="M9 22V10h5a6 6 0 0 1 0 12H9zm5-4a2 2 0 0 0 0-4h-1v4h1zm6 4V10h2l4 6 4-6h2v12h-2v-7l-4 6-4-6v7h-2z"
      fill="currentColor"
    />
  </svg>
</template>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
defineProps<{ title: string; description?: string }>();
</script>

<template>
  <div class="flex flex-col items-center gap-3 px-6 py-10 text-center">
    <div class="text-ds-muted" aria-hidden="true">
      <slot name="icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M3 7h6l2 2h10v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" />
          <path d="M3 7V5a1 1 0 0 1 1-1h5l2 2" />
        </svg>
      </slot>
    </div>
    <h4 class="m-0 text-ds-md font-semibold text-ds-text">{{ title }}</h4>
    <p v-if="description" class="m-0 max-w-md text-ds-sm text-ds-muted">{{ description }}</p>
    <div v-if="$slots.default" class="mt-1 flex gap-2"><slot /></div>
  </div>
</template>

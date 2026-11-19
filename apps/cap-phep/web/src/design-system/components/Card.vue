<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
withDefaults(defineProps<{ title?: string; subtitle?: string; padded?: boolean; as?: string }>(), {
  padded: true,
  as: "section",
});
</script>

<template>
  <component :is="as" class="ds-glass">
    <header v-if="title || $slots.actions" class="flex items-start justify-between gap-4 px-5 pt-4">
      <div>
        <h3 v-if="title" class="m-0 text-ds-md font-semibold text-ds-text">{{ title }}</h3>
        <p v-if="subtitle" class="m-0 mt-0.5 text-ds-sm text-ds-muted">{{ subtitle }}</p>
      </div>
      <div class="flex shrink-0 items-center gap-2"><slot name="actions" /></div>
    </header>
    <div :class="padded ? 'p-5' : ''"><slot /></div>
    <footer v-if="$slots.footer" class="border-t border-ds-border px-5 py-3"><slot name="footer" /></footer>
  </component>
</template>

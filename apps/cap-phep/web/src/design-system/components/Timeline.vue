<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import type { Tone } from "../variants";

export interface TimelineItem {
  title: string;
  time?: string;
  description?: string;
  tone?: Tone;
}
defineProps<{ items: TimelineItem[]; label?: string }>();
const dot: Record<Tone, string> = {
  neutral: "bg-ds-muted",
  brand: "bg-ds-brand",
  success: "bg-ds-success",
  warning: "bg-ds-warning",
  danger: "bg-ds-danger",
  info: "bg-ds-info",
  gold: "bg-ds-gold",
};
</script>

<template>
  <ol class="m-0 list-none p-0" :aria-label="label">
    <li v-for="(it, i) in items" :key="i" class="relative flex gap-3 pb-5 last:pb-0">
      <span
        v-if="i < items.length - 1"
        class="absolute left-[7px] top-4 h-full w-px bg-ds-border"
        aria-hidden="true"
      />
      <span class="relative mt-1 h-3.5 w-3.5 shrink-0 rounded-full" :class="dot[it.tone || 'neutral']" aria-hidden="true" />
      <div class="min-w-0">
        <p class="m-0 text-ds-base font-semibold text-ds-text">{{ it.title }}</p>
        <p v-if="it.time" class="m-0 text-ds-xs text-ds-muted">{{ it.time }}</p>
        <p v-if="it.description" class="m-0 mt-1 text-ds-sm text-ds-muted">{{ it.description }}</p>
      </div>
    </li>
  </ol>
</template>

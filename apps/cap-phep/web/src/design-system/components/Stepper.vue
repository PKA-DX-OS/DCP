<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";

export interface StepItem {
  key: string;
  label: string;
  /** Bước không đạt (ví dụ nghiệm thu móng chưa đạt) */
  failed?: boolean;
}
const props = defineProps<{ steps: StepItem[]; current: string; label?: string }>();
const idx = computed(() => props.steps.findIndex((s) => s.key === props.current));
function state(i: number) {
  if (props.steps[i].failed) return "failed";
  if (i < idx.value) return "done";
  if (i === idx.value) return "current";
  return "upcoming";
}
const cls: Record<string, string> = {
  done: "bg-ds-success text-ds-on-brand border-ds-success",
  current: "bg-ds-brand text-ds-on-brand border-ds-brand",
  failed: "bg-ds-danger text-ds-on-brand border-ds-danger",
  upcoming: "bg-transparent text-ds-muted border-ds-border",
};
const sr: Record<string, string> = { done: "đã xong", current: "đang ở bước này", failed: "không đạt", upcoming: "chưa tới" };
</script>

<template>
  <ol class="m-0 flex list-none flex-wrap items-start gap-2 p-0" :aria-label="label || 'Tiến trình'">
    <li
      v-for="(s, i) in steps"
      :key="s.key"
      class="flex min-w-0 flex-1 items-center gap-2"
      :aria-current="state(i) === 'current' ? 'step' : undefined"
    >
      <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-ds-sm font-semibold" :class="cls[state(i)]">
        {{ state(i) === "done" ? "✓" : state(i) === "failed" ? "!" : i + 1 }}
      </span>
      <span class="min-w-0 text-ds-sm" :class="state(i) === 'upcoming' ? 'text-ds-muted' : 'font-semibold text-ds-text'">
        {{ s.label }}<span class="sr-only"> ({{ sr[state(i)] }})</span>
      </span>
      <span v-if="i < steps.length - 1" class="hidden h-px flex-1 bg-ds-border sm:block" aria-hidden="true" />
    </li>
  </ol>
</template>

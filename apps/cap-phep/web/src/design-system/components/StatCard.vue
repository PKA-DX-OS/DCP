<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import { trendPercent, type Tone } from "../variants";

const props = withDefaults(
  defineProps<{
    label: string;
    value: number | string | null;
    unit?: string;
    previous?: number | null;
    /** true khi số tăng là xấu (ví dụ hồ sơ quá hạn) */
    increaseIsBad?: boolean;
    tone?: Tone;
    hint?: string;
    clickable?: boolean;
  }>(),
  { tone: "brand", increaseIsBad: false, clickable: false },
);
defineEmits<{ select: [] }>();

const trend = computed(() =>
  typeof props.value === "number" ? trendPercent(props.value, props.previous ?? null) : null,
);
const trendTone = computed(() => {
  if (trend.value === null || trend.value === 0) return "text-ds-muted";
  const tot = props.increaseIsBad ? trend.value < 0 : trend.value > 0;
  return tot ? "text-ds-success" : "text-ds-danger";
});
const accent: Record<Tone, string> = {
  neutral: "bg-ds-muted",
  brand: "bg-ds-brand",
  success: "bg-ds-success",
  warning: "bg-ds-warning",
  danger: "bg-ds-danger",
  info: "bg-ds-info",
  gold: "bg-ds-gold",
};
const shown = computed(() =>
  props.value === null || props.value === undefined
    ? "—"
    : typeof props.value === "number"
      ? props.value.toLocaleString("vi-VN")
      : props.value,
);
</script>

<template>
  <component
    :is="clickable ? 'button' : 'div'"
    :type="clickable ? 'button' : undefined"
    class="ds-focus relative flex w-full flex-col gap-2 overflow-hidden ds-glass p-4 text-left"
    :class="clickable ? 'cursor-pointer hover:bg-ds-surface-2' : ''"
    @click="clickable && $emit('select')"
  >
    <span class="absolute inset-y-0 left-0 w-1" :class="accent[tone]" aria-hidden="true" />
    <div class="flex items-center justify-between gap-2">
      <span class="text-ds-sm text-ds-muted">{{ label }}</span>
      <slot name="icon" />
    </div>
    <div class="flex items-baseline gap-1">
      <span class="text-ds-xl font-semibold tabular-nums text-ds-text">{{ shown }}</span>
      <span v-if="unit && value !== null" class="text-ds-sm text-ds-muted">{{ unit }}</span>
    </div>
    <div class="flex items-center justify-between gap-2 text-ds-xs">
      <span v-if="trend !== null" :class="trendTone">
        {{ trend > 0 ? "▲" : trend < 0 ? "▼" : "■" }} {{ Math.abs(trend) }}% so với kỳ trước
      </span>
      <span v-else-if="hint" class="text-ds-muted">{{ hint }}</span>
      <slot name="extra" />
    </div>
  </component>
</template>

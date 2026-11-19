<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    label: string;
    value: number | string | null;
    unit?: string;
    icon?: string;
    tone?: "brand" | "success" | "warning" | "danger" | "info" | "gold" | "neutral";
    trend?: number | null;
    series?: number[];
    hint?: string;
  }>(),
  { tone: "brand", icon: "•", series: () => [] },
);
defineEmits<{ select: [] }>();

const tones: Record<string, string> = {
  brand: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
  success: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  warning: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  danger: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200",
  info: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200",
  gold: "bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-200",
  neutral: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
};
const spark = computed(() => {
  const ds = (props.series || []).map(Number).filter((x) => Number.isFinite(x));
  if (ds.length < 2) return "";
  const min = Math.min(...ds);
  const max = Math.max(...ds);
  const span = max - min || 1;
  return ds
    .map((v, i) => `${(i / (ds.length - 1)) * 96 + 2},${28 - ((v - min) / span) * 24}`)
    .join(" ");
});
const trendText = computed(() => {
  if (props.trend === null || props.trend === undefined || !Number.isFinite(props.trend)) return "";
  return `${props.trend > 0 ? "▲" : props.trend < 0 ? "▼" : "■"} ${Math.abs(props.trend).toLocaleString("vi-VN", { maximumFractionDigits: 1 })}%`;
});
const trendClass = computed(() =>
  props.trend === null || props.trend === undefined || props.trend === 0
    ? "chu-phu"
    : props.trend > 0
      ? "text-emerald-700 dark:text-emerald-300"
      : "text-rose-700 dark:text-rose-300",
);
const shown = computed(() =>
  props.value === null || props.value === undefined
    ? "—"
    : typeof props.value === "number"
      ? props.value.toLocaleString("vi-VN", { maximumFractionDigits: 1 })
      : props.value,
);
</script>

<template>
  <button type="button" class="kinh flex w-full flex-col gap-2 p-4 text-left shadow hover:ring-2 hover:ring-slate-300" :title="hint" @click="$emit('select')">
    <div class="flex items-center justify-between gap-2">
      <span class="text-sm chu-phu">{{ label }}</span>
      <span class="flex h-8 w-8 items-center justify-center rounded-full text-base" :class="tones[tone]" aria-hidden="true">{{ icon }}</span>
    </div>
    <div class="flex items-baseline gap-1">
      <span class="text-2xl font-semibold">{{ shown }}</span>
      <span v-if="unit && value !== null" class="text-sm chu-phu">{{ unit }}</span>
    </div>
    <div class="flex items-end justify-between gap-2">
      <span class="text-xs" :class="trendClass">{{ trendText || "—" }}</span>
      <svg v-if="spark" viewBox="0 0 100 30" class="h-7 w-24" role="img" aria-label="Xu hướng gần đây">
        <polyline :points="spark" fill="none" stroke="currentColor" stroke-width="2" class="text-sky-600 dark:text-sky-300" />
      </svg>
    </div>
  </button>
</template>

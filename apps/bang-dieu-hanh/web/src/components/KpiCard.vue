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
  { tone: "brand", icon: "", series: () => [] },
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
  <button type="button" class="chi-so" :title="hint" @click="$emit('select')">
    <span class="nhan-nho block min-h-[34px]">{{ label }}</span>
    <span :class="['so mt-3 block text-[40px] font-semibold leading-[1.05] tracking-[-0.02em]', tone === 'gold' ? 'text-cham' : 'text-chu']">
      {{ shown }}
    </span>
    <span v-if="unit && value !== null" class="mt-2 block text-[13px] text-phu">{{ unit }}</span>
    <span v-if="trendText" class="mt-1 block text-[12px]" :class="trendClass">{{ trendText }} so với kỳ trước</span>
  </button>
</template>


<style scoped>
.chi-so {
  text-align: left;
  padding: 24px;
  transition: background 500ms var(--em), box-shadow 500ms var(--em);
  border: 0;
  border-right: 1px solid var(--vien-nhat);
  border-bottom: 1px solid var(--vien-nhat);
  background: transparent;
  color: inherit;
}
.chi-so:hover {
  background: radial-gradient(240px circle at var(--mx, 50%) var(--my, 50%), var(--sang-mat), transparent 70%), var(--mat-2);
}
.chi-so .so { transition: transform 500ms var(--em); }
.chi-so:hover .so { transform: translateY(-3px); }
</style>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{ labels: string[]; series: { label: string; values: number[]; color?: string }[]; title?: string }>(),
  { title: "" },
);
const COLORS = ["#2563eb", "#059669", "#d97706"];
const W = 600;
const H = 220;
const PAD = { left: 36, right: 12, top: 12, bottom: 28 };
const max = computed(() => Math.max(1, ...props.series.flatMap((s) => s.values.map(Number).filter(Number.isFinite))));
const points = computed(() =>
  props.series.map((s, si) => {
    const ds = s.values.map((v) => Math.max(0, Number(v) || 0));
    const step = ds.length > 1 ? (W - PAD.left - PAD.right) / (ds.length - 1) : 0;
    return {
      ...s,
      color: s.color || COLORS[si % COLORS.length],
      path: ds
        .map((v, i) => `${PAD.left + i * step},${H - PAD.bottom - (v / max.value) * (H - PAD.top - PAD.bottom)}`)
        .join(" "),
    };
  }),
);
const nhanX = computed(() => {
  const step = props.labels.length > 1 ? (W - PAD.left - PAD.right) / (props.labels.length - 1) : 0;
  return props.labels.map((label, i) => ({ label, x: PAD.left + i * step })).filter((_, i) => i % Math.max(1, Math.ceil(props.labels.length / 6)) === 0 || i === props.labels.length - 1);
});
</script>

<template>
  <div class="kinh p-4 shadow">
    <h2 class="mb-2 text-sm font-semibold chu-phu">{{ title || "Xu hướng" }}</h2>
    <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" role="img" :aria-label="title || 'Biểu đồ đường'">
      <line :x1="PAD.left" :x2="W - PAD.right" :y1="H - PAD.bottom" :y2="H - PAD.bottom" stroke="currentColor" class="text-slate-300 dark:text-slate-700" />
      <line v-for="i in 4" :key="i" :x1="PAD.left" :x2="W - PAD.right" :y1="H - PAD.bottom - (i / 4) * (H - PAD.top - PAD.bottom)" :y2="H - PAD.bottom - (i / 4) * (H - PAD.top - PAD.bottom)" stroke="currentColor" class="text-slate-200 dark:text-slate-800" />
      <polyline v-for="s in points" :key="s.label" :points="s.path" fill="none" :stroke="s.color" stroke-width="2.5" />
      <text v-for="n in nhanX" :key="n.label" :x="n.x" :y="H - 8" text-anchor="middle" font-size="10" class="fill-slate-500">{{ n.label }}</text>
    </svg>
    <div class="mt-2 flex flex-wrap gap-3 text-xs">
      <span v-for="s in points" :key="s.label" class="flex items-center gap-1"><span class="inline-block h-2 w-2 rounded-full" :style="{ background: s.color }" />{{ s.label }}</span>
    </div>
  </div>
</template>

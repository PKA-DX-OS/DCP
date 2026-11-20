<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(defineProps<{ items: { label: string; value: number; color?: string }[]; title?: string }>(), {
  title: "",
});
const COLORS = ["#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#65a30d", "#64748b"];
const tong = computed(() => props.items.reduce((s, x) => s + Math.max(0, Number(x.value) || 0), 0));
const cung = computed(() => {
  const r = 42;
  const chuVi = 2 * Math.PI * r;
  let offset = 0;
  return props.items
    .filter((x) => Number(x.value) > 0)
    .map((x, i) => {
      const phan = Number(x.value) / (tong.value || 1);
      const doan = { ...x, color: x.color || COLORS[i % COLORS.length], dash: `${phan * chuVi} ${chuVi}`, offset: -offset };
      offset += phan * chuVi;
      return doan;
    });
});
</script>

<template>
  <div class="kinh p-4 shadow">
    <h2 class="mb-2 text-sm font-semibold chu-phu">{{ title || "Phân bố" }}</h2>
    <div class="flex flex-wrap items-center gap-4">
      <svg viewBox="0 0 100 100" class="h-36 w-36 shrink-0" role="img" :aria-label="title || 'Biểu đồ tròn'">
        <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" stroke-width="16" class="text-slate-200 dark:text-slate-700" />
        <circle
          v-for="c in cung"
          :key="c.label"
          cx="50"
          cy="50"
          r="42"
          fill="none"
          :stroke="c.color"
          stroke-width="16"
          :stroke-dasharray="c.dash"
          :stroke-dashoffset="c.offset"
          transform="rotate(-90 50 50)"
        >
          <title>{{ c.label }}: {{ c.value }}</title>
        </circle>
        <text x="50" y="47" text-anchor="middle" font-size="12" class="fill-slate-900 dark:fill-slate-100">{{ tong }}</text>
        <text x="50" y="60" text-anchor="middle" font-size="6" class="fill-slate-500">tổng</text>
      </svg>
      <ul class="min-w-[180px] flex-1 list-none space-y-1 p-0 text-sm">
        <li v-for="(c, i) in cung" :key="c.label" class="flex items-center justify-between gap-2">
          <span class="flex items-center gap-2"><span class="inline-block h-2.5 w-2.5 rounded-full" :style="{ background: c.color || COLORS[i % COLORS.length] }" />{{ c.label }}</span>
          <b>{{ c.value }}</b>
        </li>
      </ul>
    </div>
  </div>
</template>

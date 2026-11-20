<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(defineProps<{ items: { label: string; value: number }[]; title?: string }>(), { title: "" });
const W = 600;
const H = 240;
const PAD = { left: 36, right: 12, top: 12, bottom: 54 };
const max = computed(() => Math.max(1, ...props.items.map((x) => Number(x.value) || 0)));
const bars = computed(() => {
  const n = Math.max(1, props.items.length);
  const slot = (W - PAD.left - PAD.right) / n;
  return props.items.map((x, i) => {
    const h = ((Number(x.value) || 0) / max.value) * (H - PAD.top - PAD.bottom);
    return { ...x, x: PAD.left + i * slot + slot * 0.15, y: H - PAD.bottom - h, w: slot * 0.7, h };
  });
});
</script>

<template>
  <div class="kinh p-4 shadow">
    <h2 class="mb-2 text-sm font-semibold chu-phu">{{ title || "Tải việc" }}</h2>
    <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" role="img" :aria-label="title || 'Biểu đồ cột'">
      <line :x1="PAD.left" :x2="W - PAD.right" :y1="H - PAD.bottom" :y2="H - PAD.bottom" stroke="currentColor" class="text-slate-300 dark:text-slate-700" />
      <g v-for="b in bars" :key="b.label">
        <rect :x="b.x" :y="b.y" :width="b.w" :height="b.h" rx="4" class="fill-sky-600 dark:fill-sky-400">
          <title>{{ b.label }}: {{ b.value }}</title>
        </rect>
        <text :x="b.x + b.w / 2" :y="b.y - 4" text-anchor="middle" font-size="10" class="fill-slate-700 dark:fill-slate-200">{{ b.value }}</text>
        <text :x="b.x + b.w / 2" :y="H - 32" text-anchor="middle" font-size="10" class="fill-slate-500" :transform="`rotate(-30 ${b.x + b.w / 2} ${H - 32})`">{{ b.label.slice(0, 18) }}</text>
      </g>
    </svg>
  </div>
</template>

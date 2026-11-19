<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import ChartCard from "./ChartCard.vue";
import DataTable from "./DataTable.vue";
import { DEFAULT_BOX, barRects, chartColor, ticks } from "./geometry";

const props = defineProps<{
  title: string;
  subtitle?: string;
  items: Array<{ label: string; value: number }>;
  unit?: string;
}>();
const box = DEFAULT_BOX;
const max = computed(() => Math.max(0, ...props.items.map((i) => i.value)));
const yTicks = computed(() => ticks(max.value));
const top = computed(() => yTicks.value[yTicks.value.length - 1]);
const y = (v: number) => box.padTop + (box.height - box.padTop - box.padBottom) * (1 - v / top.value);
const rects = computed(() => barRects(props.items.map((i) => i.value), max.value, box));
const empty = computed(() => !props.items.length);
</script>

<template>
  <ChartCard :title="title" :subtitle="subtitle" :empty="empty">
    <svg :viewBox="`0 0 ${box.width} ${box.height}`" class="h-auto w-full">
      <g v-for="t in yTicks" :key="t">
        <line :x1="box.padLeft" :x2="box.width - box.padRight" :y1="y(t)" :y2="y(t)" stroke="var(--vien)" />
        <text :x="box.padLeft - 6" :y="y(t) + 4" text-anchor="end" class="fill-ds-muted" style="font-size: 11px">
          {{ t.toLocaleString("vi-VN") }}
        </text>
      </g>
      <g v-for="(r, i) in rects" :key="items[i].label">
        <rect :x="r.x" :y="r.y" :width="r.width" :height="r.height" rx="3" :fill="chartColor(0)">
          <title>{{ items[i].label }}: {{ items[i].value.toLocaleString("vi-VN") }} {{ unit || "" }}</title>
        </rect>
        <text :x="r.x + r.width / 2" :y="box.height - 8" text-anchor="middle" class="fill-ds-muted" style="font-size: 11px">
          {{ items[i].label.length > 12 ? items[i].label.slice(0, 11) + "…" : items[i].label }}
        </text>
      </g>
    </svg>
    <template #table>
      <DataTable :caption="title" :headers="['Mục', unit ? `Giá trị (${unit})` : 'Giá trị']" :rows="items.map((i) => [i.label, i.value])" />
    </template>
  </ChartCard>
</template>

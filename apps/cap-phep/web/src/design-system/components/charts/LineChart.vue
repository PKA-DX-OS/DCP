<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import ChartCard from "./ChartCard.vue";
import DataTable from "./DataTable.vue";
import Legend from "./Legend.vue";
import { DEFAULT_BOX, chartColor, linePath, linePoints, ticks } from "./geometry";

const props = defineProps<{
  title: string;
  subtitle?: string;
  labels: string[];
  series: Array<{ name: string; values: Array<number | null> }>;
}>();
const box = DEFAULT_BOX;
const max = computed(() => Math.max(0, ...props.series.flatMap((s) => s.values.filter((v): v is number => v !== null))));
const yTicks = computed(() => ticks(max.value));
const top = computed(() => yTicks.value[yTicks.value.length - 1]);
const y = (v: number) => box.padTop + (box.height - box.padTop - box.padBottom) * (1 - v / top.value);
const lines = computed(() => props.series.map((s) => linePoints(s.values, max.value, box)));
const empty = computed(() => !props.series.some((s) => s.values.some((v) => v !== null)));
/* Nhãn trục X thưa bớt khi nhiều điểm */
const every = computed(() => Math.max(1, Math.ceil(props.labels.length / 8)));
</script>

<template>
  <ChartCard :title="title" :subtitle="subtitle" :empty="empty">
    <svg :viewBox="`0 0 ${box.width} ${box.height}`" class="h-auto w-full">
      <g class="text-ds-muted">
        <g v-for="t in yTicks" :key="t">
          <line :x1="box.padLeft" :x2="box.width - box.padRight" :y1="y(t)" :y2="y(t)" stroke="var(--vien)" />
          <text :x="box.padLeft - 6" :y="y(t) + 4" text-anchor="end" class="fill-ds-muted" style="font-size: 11px">
            {{ t.toLocaleString("vi-VN") }}
          </text>
        </g>
        <template v-for="(l, i) in labels" :key="l + i">
          <text
            v-if="i % every === 0"
            :x="lines[0]?.[i]?.x ?? 0"
            :y="box.height - 8"
            text-anchor="middle"
            class="fill-ds-muted"
            style="font-size: 11px"
          >
            {{ l }}
          </text>
        </template>
      </g>
      <g v-for="(pts, si) in lines" :key="series[si].name">
        <path :d="linePath(pts)" fill="none" :stroke="chartColor(si)" stroke-width="2.5" stroke-linejoin="round" />
        <template v-for="(p, pi) in pts" :key="pi">
          <circle v-if="p.y !== null" :cx="p.x" :cy="p.y" r="3.5" :fill="chartColor(si)">
            <title>{{ series[si].name }} · {{ labels[pi] }}: {{ (p.value as number).toLocaleString("vi-VN") }}</title>
          </circle>
        </template>
      </g>
    </svg>
    <template v-if="series.length > 1" #legend><Legend :items="series.map((s) => ({ label: s.name }))" /></template>
    <template #table>
      <DataTable
        :caption="title"
        :headers="['Kỳ', ...series.map((s) => s.name)]"
        :rows="labels.map((l, i) => [l, ...series.map((s) => s.values[i] ?? null)])"
      />
    </template>
  </ChartCard>
</template>

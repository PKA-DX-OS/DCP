<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import ChartCard from "./ChartCard.vue";
import DataTable from "./DataTable.vue";
import Legend from "./Legend.vue";
import { chartColor, donutArcs } from "./geometry";

const props = defineProps<{
  title: string;
  subtitle?: string;
  items: Array<{ label: string; value: number }>;
  centerLabel?: string;
}>();
const arcs = computed(() => donutArcs(props.items.map((i) => i.value)));
const total = computed(() => props.items.reduce((a, b) => a + (Number.isFinite(b.value) && b.value > 0 ? b.value : 0), 0));
const pct = (f: number) => `${Math.round(f * 1000) / 10}%`;
</script>

<template>
  <ChartCard :title="title" :subtitle="subtitle" :empty="!arcs.length">
    <div class="flex justify-center">
      <svg viewBox="0 0 100 100" class="h-48 w-48">
        <path v-for="a in arcs" :key="a.index" :d="a.path" :fill="chartColor(a.index)">
          <title>{{ items[a.index].label }}: {{ a.value.toLocaleString("vi-VN") }} ({{ pct(a.fraction) }})</title>
        </path>
        <text x="50" y="49" text-anchor="middle" class="fill-ds-text" style="font-size: 12px; font-weight: 600">
          {{ total.toLocaleString("vi-VN") }}
        </text>
        <text x="50" y="61" text-anchor="middle" class="fill-ds-muted" style="font-size: 6px">{{ centerLabel || "tổng" }}</text>
      </svg>
    </div>
    <template #legend>
      <Legend :items="items.map((i) => ({ label: i.label, value: i.value.toLocaleString('vi-VN') }))" />
    </template>
    <template #table>
      <DataTable
        :caption="title"
        :headers="['Nhóm', 'Số lượng', 'Tỷ lệ']"
        :rows="items.map((i) => [i.label, i.value, total ? pct(i.value / total) : '—'])"
      />
    </template>
  </ChartCard>
</template>

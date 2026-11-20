<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts" generic="T extends Record<string, any>">
import Skeleton from "./Skeleton.vue";
import EmptyState from "./EmptyState.vue";

export interface TableColumn {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  width?: string;
}

const props = withDefaults(
  defineProps<{
    columns: TableColumn[];
    rows: T[];
    rowKey?: string;
    loading?: boolean;
    emptyTitle?: string;
    emptyDescription?: string;
    caption?: string;
  }>(),
  { rowKey: "id", loading: false, emptyTitle: "Chưa có dữ liệu" },
);
defineEmits<{ rowClick: [row: T] }>();
const align = (a?: string) => (a === "right" ? "text-right" : a === "center" ? "text-center" : "text-left");
const keyOf = (row: T, i: number) => (row[props.rowKey] ?? i) as string | number;
</script>

<template>
  <div class="ds-glass overflow-x-auto" tabindex="0" role="region" :aria-label="caption || 'Bảng dữ liệu'">
    <table class="w-full border-collapse text-ds-base">
      <caption v-if="caption" class="sr-only">{{ caption }}</caption>
      <thead>
        <tr>
          <th
            v-for="c in columns"
            :key="c.key"
            scope="col"
            class="whitespace-nowrap border-b border-ds-border px-4 py-2 text-ds-xs font-semibold text-ds-muted"
            :class="align(c.align)"
            :style="c.width ? { width: c.width } : undefined"
          >
            {{ c.label }}
          </th>
        </tr>
      </thead>
      <tbody v-if="loading">
        <tr v-for="i in 3" :key="i">
          <td v-for="c in columns" :key="c.key" class="border-b border-ds-border px-4 py-3"><Skeleton /></td>
        </tr>
      </tbody>
      <tbody v-else-if="rows.length">
        <tr
          v-for="(row, i) in rows"
          :key="keyOf(row, i)"
          class="hover:bg-ds-surface-2"
          @click="$emit('rowClick', row)"
        >
          <td
            v-for="c in columns"
            :key="c.key"
            class="border-b border-ds-border px-4 py-3 align-top text-ds-text"
            :class="align(c.align)"
          >
            <slot :name="'cell-' + c.key" :row="row" :value="row[c.key]">{{ row[c.key] ?? "—" }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
    <EmptyState v-if="!loading && !rows.length" :title="emptyTitle" :description="emptyDescription">
      <slot name="empty-action" />
    </EmptyState>
  </div>
</template>

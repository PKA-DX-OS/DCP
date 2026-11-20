<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
/** Bảng số liệu đi kèm biểu đồ (thay thế cho trình đọc màn hình và người cần số chính xác). */
defineProps<{ caption: string; headers: string[]; rows: Array<Array<string | number | null>> }>();
const fmt = (v: string | number | null) => (v === null ? "—" : typeof v === "number" ? v.toLocaleString("vi-VN") : v);
</script>

<template>
  <table class="w-full border-collapse text-ds-sm">
    <caption class="sr-only">{{ caption }}</caption>
    <thead>
      <tr>
        <th v-for="h in headers" :key="h" scope="col" class="border-b border-ds-border px-2 py-1 text-left text-ds-muted">{{ h }}</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(r, i) in rows" :key="i">
        <td v-for="(c, j) in r" :key="j" class="border-b border-ds-border px-2 py-1 tabular-nums text-ds-text">{{ fmt(c) }}</td>
      </tr>
    </tbody>
  </table>
</template>

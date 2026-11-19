<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { apiGet } from "../api";

interface AuditItem {
  id: number | string;
  at: string;
  actor_sub: string;
  actor_type: string;
  action: string;
  object_type: string;
  object_id: string;
  detail: unknown;
  prev_hash: string | null;
  hash: string | null;
}
interface AuditResponse {
  tenant: string;
  chain_valid: boolean;
  head_hash: string | null;
  count: number;
  items: AuditItem[];
}
interface VerifyResponse {
  valid: boolean;
  head_hash: string | null;
  count: number;
  last_id?: number;
}

const duLieu = ref<AuditResponse | null>(null);
const xacMinh = ref<VerifyResponse | null>(null);
const loading = ref(false);
const error = ref("");
const locEntity = ref("");
const locActor = ref("");
const locAction = ref("");
const tuKhoa = ref("");

const entities = computed(() => Array.from(new Set((duLieu.value?.items ?? []).map((x) => x.object_type).filter(Boolean))).sort());
const daLoc = computed(() => {
  const q = tuKhoa.value.trim().toLowerCase();
  return (duLieu.value?.items ?? []).filter(
    (x) =>
      (!locEntity.value || x.object_type === locEntity.value) &&
      (!locActor.value || x.actor_sub.toLowerCase().includes(locActor.value.toLowerCase())) &&
      (!locAction.value || x.action.toLowerCase().includes(locAction.value.toLowerCase())) &&
      (!q || `${x.action} ${x.actor_sub} ${x.object_type} ${x.object_id}`.toLowerCase().includes(q)),
  );
});

function ngayGio(value: string): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "—";
}
function nganHash(value: string | null): string {
  return value ? `${value.slice(0, 12)}…` : "—";
}
async function tai(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [chain, verify] = await Promise.all([
      apiGet<AuditResponse>("/audit/chain?limit=200"),
      apiGet<VerifyResponse>("/audit/verify"),
    ]);
    duLieu.value = chain;
    xacMinh.value = verify;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được nhật ký kiểm toán";
  } finally {
    loading.value = false;
  }
}
async function xacMinhLai(): Promise<void> {
  try {
    xacMinh.value = await apiGet<VerifyResponse>("/audit/verify");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không xác minh được chuỗi";
  }
}
function xuatCsv(): void {
  const header = ["Thời gian", "Người thực hiện", "Hành động", "Đối tượng", "ID đối tượng", "Hash", "Prev hash"];
  const rows = daLoc.value.map((x) => [
    ngayGio(x.at),
    x.actor_sub,
    x.action,
    x.object_type,
    x.object_id,
    x.hash || "",
    x.prev_hash || "",
  ]);
  const csv = [header, ...rows]
    .map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","))
    .join("\r\n");
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `audit-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
onMounted(tai);
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3 rounded-lg kinh p-4 shadow">
      <div>
        <h1 class="text-lg font-semibold">Nhật ký kiểm toán</h1>
        <p class="text-sm chu-phu">Chuỗi băm bất biến; kiểm toán viên chỉ đọc, không sửa dữ liệu.</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span
          class="rounded-full px-3 py-1 text-xs font-medium"
          :class="xacMinh?.valid ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200' : 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200'"
        >
          {{ xacMinh ? (xacMinh.valid ? "Chuỗi hợp lệ" : "Chuỗi không hợp lệ") : "Chưa xác minh" }}
        </span>
        <button class="rounded border px-3 py-1 text-sm" :disabled="loading" @click="tai">Tải lại</button>
        <button class="rounded border px-3 py-1 text-sm" @click="xacMinhLai">Xác minh</button>
        <button class="rounded bg-slate-800 px-3 py-1 text-sm text-white" @click="xuatCsv">Xuất CSV</button>
      </div>
    </div>

    <div class="rounded-lg kinh p-4 shadow">
      <div class="grid gap-3 sm:grid-cols-4">
        <label class="text-sm">Đối tượng
          <select v-model="locEntity" class="mt-1 w-full rounded border px-2 py-1">
            <option value="">Tất cả</option>
            <option v-for="e in entities" :key="e" :value="e">{{ e }}</option>
          </select>
        </label>
        <label class="text-sm">Người thực hiện
          <input v-model="locActor" class="mt-1 w-full rounded border px-2 py-1" placeholder="sub hoặc username" />
        </label>
        <label class="text-sm">Hành động
          <input v-model="locAction" class="mt-1 w-full rounded border px-2 py-1" placeholder="vd: ho_so" />
        </label>
        <label class="text-sm">Tìm kiếm
          <input v-model="tuKhoa" class="mt-1 w-full rounded border px-2 py-1" placeholder="action, id, đối tượng" />
        </label>
      </div>
      <p class="mt-2 text-xs chu-phu">
        Head hash: <code>{{ xacMinh?.head_hash || "—" }}</code> · {{ duLieu?.count ?? 0 }} bản ghi gần nhất
      </p>
    </div>

    <p v-if="loading" class="chu-phu">Đang tải nhật ký…</p>
    <p v-else-if="error" class="text-red-700">{{ error }}</p>
    <div v-else class="overflow-x-auto rounded-lg kinh shadow">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr class="border-b text-left text-xs chu-phu">
            <th class="px-3 py-2">Thời gian</th>
            <th class="px-3 py-2">Người thực hiện</th>
            <th class="px-3 py-2">Hành động</th>
            <th class="px-3 py-2">Đối tượng</th>
            <th class="px-3 py-2">Hash</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="x in daLoc" :key="x.id" class="border-b last:border-0" :title="JSON.stringify(x.detail)">
            <td class="whitespace-nowrap px-3 py-2">{{ ngayGio(x.at) }}</td>
            <td class="px-3 py-2">{{ x.actor_sub }}<span class="block text-xs chu-phu">{{ x.actor_type }}</span></td>
            <td class="px-3 py-2">{{ x.action }}</td>
            <td class="px-3 py-2">{{ x.object_type }}<span class="block text-xs chu-phu">{{ x.object_id }}</span></td>
            <td class="px-3 py-2 font-mono text-xs" :title="x.hash || ''">{{ nganHash(x.hash) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!daLoc.length" class="p-4 text-sm chu-phu">Không có bản ghi phù hợp bộ lọc.</p>
    </div>
  </section>
</template>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { apiGet, apiPost } from "../api";

interface DsarRequest {
  id: string;
  tenant: string;
  subject_sub: string;
  type: string;
  status: string;
  received_at: string;
  ack_due_at: string;
  due_at: string;
  closed_at: string | null;
  result: unknown;
  legal_basis_note: string | null;
}

const ds = ref<DsarRequest[]>([]);
const loading = ref(false);
const error = ref("");
const thongBao = ref("");
const locTrangThai = ref("");
const dangXuLy = ref("");

const LOAI: Record<string, string> = {
  access: "Truy cập, xem dữ liệu",
  rectify: "Chỉnh sửa dữ liệu",
  erase: "Xóa dữ liệu",
  restrict: "Hạn chế xử lý",
  withdraw: "Rút đồng ý",
};
const TRANG_THAI: Record<string, string> = {
  received: "Đã tiếp nhận",
  in_progress: "Đang xử lý",
  completed: "Hoàn tất",
  rejected: "Từ chối",
  closed: "Đã đóng",
};

const dsLoc = computed(() => ds.value.filter((x) => !locTrangThai.value || x.status === locTrangThai.value));
const soQuaHan = computed(() =>
  ds.value.filter((x) => !x.closed_at && new Date(x.due_at).getTime() < Date.now()).length,
);

function nhanLoai(value: string): string {
  return LOAI[value] || value;
}
function nhanTrangThai(value: string): string {
  return TRANG_THAI[value] || value;
}
function ngay(value: string | null): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "—";
}
function quaHan(x: DsarRequest): boolean {
  return !x.closed_at && new Date(x.due_at).getTime() < Date.now();
}
function lopTrangThai(value: string): string {
  if (value === "completed") return "tt-xanh";
  if (value === "rejected") return "tt-do";
  if (value === "in_progress") return "tt-lam";
  return "tt-vang";
}

async function tai(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    ds.value = await apiGet<DsarRequest[]>("/rest/dsar_requests?order=received_at.desc");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được yêu cầu dữ liệu cá nhân";
  } finally {
    loading.value = false;
  }
}

async function capNhat(x: DsarRequest, status: "in_progress" | "completed" | "rejected"): Promise<void> {
  let result = "";
  if (status === "completed" || status === "rejected") {
    const label = status === "completed" ? "Kết quả xử lý" : "Lý do từ chối";
    const value = window.prompt(label, "");
    if (value === null) return;
    result = value.trim();
    if (!result) {
      error.value = `Cần nhập ${label.toLowerCase()}`;
      return;
    }
  }
  dangXuLy.value = x.id;
  error.value = "";
  thongBao.value = "";
  try {
    await apiPost("/rest/rpc/xu_ly_dsar", {
      p_request_id: x.id,
      p_status: status,
      p_result: result || null,
      p_due_at: null,
    });
    thongBao.value = `Đã cập nhật yêu cầu ${x.id.slice(0, 8)}… sang ${nhanTrangThai(status)}`;
    await tai();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không cập nhật được yêu cầu";
  } finally {
    dangXuLy.value = "";
  }
}

onMounted(tai);
</script>

<template>
  <section id="dsar-panel" class="space-y-4">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="tieu-de-trang">Yêu cầu dữ liệu cá nhân</h1>
        <p class="mt-1 text-sm chu-phu">
          Tiếp nhận, xử lý và đóng yêu cầu DSAR theo thời hạn phản hồi.
        </p>
      </div>
      <div class="flex flex-wrap items-end gap-2">
        <label class="text-sm">
          Trạng thái
          <select v-model="locTrangThai" class="mt-1 rounded border px-2 py-1">
            <option value="">Tất cả</option>
            <option v-for="(ten, ma) in TRANG_THAI" :key="ma" :value="ma">{{ ten }}</option>
          </select>
        </label>
        <button class="rounded border px-3 py-1 text-sm" :disabled="loading" @click="tai">Làm mới</button>
      </div>
    </div>

    <div class="grid gap-3 sm:grid-cols-3">
      <div class="rounded-lg kinh p-4 shadow">
        <p class="text-xs chu-phu">Tổng yêu cầu</p>
        <p class="mt-1 text-2xl font-semibold">{{ ds.length }}</p>
      </div>
      <div class="rounded-lg kinh p-4 shadow">
        <p class="text-xs chu-phu">Đang mở</p>
        <p class="mt-1 text-2xl font-semibold">{{ ds.filter((x) => !x.closed_at).length }}</p>
      </div>
      <div class="rounded-lg kinh p-4 shadow">
        <p class="text-xs chu-phu">Quá hạn</p>
        <p class="mt-1 text-2xl font-semibold" :class="soQuaHan ? 'text-red-700' : ''">{{ soQuaHan }}</p>
      </div>
    </div>

    <p v-if="thongBao" class="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100">
      {{ thongBao }}
    </p>
    <p v-if="error" class="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-100">{{ error }}</p>

    <div v-if="loading" class="kinh animate-pulse space-y-3 p-4 shadow" role="status" aria-busy="true">
      <span class="sr-only">Đang tải yêu cầu dữ liệu cá nhân</span>
      <div v-for="i in 5" :key="i" class="h-3 w-full rounded bg-slate-200 dark:bg-slate-700" aria-hidden="true"></div>
    </div>

    <div v-else class="overflow-x-auto rounded-lg kinh shadow">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr class="border-b text-left text-xs chu-phu">
            <th class="px-3 py-2">Người yêu cầu</th>
            <th class="px-3 py-2">Loại</th>
            <th class="px-3 py-2">Trạng thái</th>
            <th class="px-3 py-2">Tiếp nhận</th>
            <th class="px-3 py-2">Hạn xử lý</th>
            <th class="px-3 py-2">Căn cứ / ghi chú</th>
            <th class="px-3 py-2">Thao tác</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="x in dsLoc" :key="x.id" class="border-b align-top">
            <td class="px-3 py-2">
              <span class="block font-medium">{{ x.subject_sub }}</span>
              <span class="block text-xs chu-phu">{{ x.tenant }} · {{ x.id.slice(0, 8) }}…</span>
            </td>
            <td class="px-3 py-2 whitespace-nowrap">{{ nhanLoai(x.type) }}</td>
            <td class="px-3 py-2 whitespace-nowrap">
              <span class="rounded-full px-2 py-0.5 text-xs" :class="lopTrangThai(x.status)">{{ nhanTrangThai(x.status) }}</span>
              <span v-if="quaHan(x)" class="mt-1 block text-xs text-red-700">Quá hạn</span>
            </td>
            <td class="px-3 py-2 whitespace-nowrap">{{ ngay(x.received_at) }}</td>
            <td class="px-3 py-2 whitespace-nowrap">{{ ngay(x.due_at) }}</td>
            <td class="px-3 py-2 max-w-[280px] text-xs chu-phu">{{ x.legal_basis_note || "—" }}</td>
            <td class="px-3 py-2">
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-if="x.status === 'received'"
                  class="rounded border px-2 py-1 text-xs"
                  :disabled="dangXuLy === x.id"
                  @click="capNhat(x, 'in_progress')"
                >Nhận xử lý</button>
                <button
                  v-if="x.status !== 'completed' && x.status !== 'rejected' && x.status !== 'closed'"
                  class="rounded bg-emerald-700 px-2 py-1 text-xs text-white"
                  :disabled="dangXuLy === x.id"
                  @click="capNhat(x, 'completed')"
                >Hoàn tất</button>
                <button
                  v-if="x.status !== 'completed' && x.status !== 'rejected' && x.status !== 'closed'"
                  class="rounded border border-red-300 px-2 py-1 text-xs text-red-700"
                  :disabled="dangXuLy === x.id"
                  @click="capNhat(x, 'rejected')"
                >Từ chối</button>
                <span v-if="x.status === 'completed' || x.status === 'rejected' || x.status === 'closed'" class="text-xs chu-phu">
                  {{ x.closed_at ? ngay(x.closed_at) : "Đã đóng" }}
                </span>
              </div>
            </td>
          </tr>
          <tr v-if="!dsLoc.length">
            <td colspan="7" class="px-3 py-8 text-center chu-phu">Chưa có yêu cầu dữ liệu cá nhân.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

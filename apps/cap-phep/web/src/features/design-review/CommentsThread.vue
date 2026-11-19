<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Badge, Button, EmptyState, Select, Textarea } from "../../design-system";
import type { BanVe, MucDo, NhanXet } from "./types";

const props = defineProps<{
  comments: NhanXet[];
  drawings: BanVe[];
  canComment: boolean;
  canResolve: boolean;
  loading: boolean;
  saving?: boolean;
  selectedDrawingId?: string | null;
}>();
const emit = defineEmits<{
  add: [payload: { ban_ve_id: string; noi_dung: string; muc_do: MucDo }];
  resolve: [payload: { id: string; ghi_chu: string }];
}>();

const locMucDo = ref("");
const locTrangThai = ref("");
const banVeId = ref("");
const noiDung = ref("");
const mucDo = ref<MucDo>("gop_y");
const ghiChu = ref<Record<string, string>>({});

watch(
  () => props.selectedDrawingId,
  (id) => {
    if (id) banVeId.value = id;
  },
  { immediate: true },
);
watch(
  () => props.drawings,
  (ds) => {
    if (!banVeId.value && ds.length) banVeId.value = ds[0].id;
  },
  { immediate: true },
);

const dsBanVe = computed(() =>
  props.drawings.map((bv) => ({ value: bv.id, label: `${bv.ten} (${bv.bo_mon})` })),
);
const mucDoOptions = [
  { value: "", label: "Tất cả mức độ" },
  { value: "loi", label: "Lỗi" },
  { value: "canh_bao", label: "Cảnh báo" },
  { value: "gop_y", label: "Góp ý" },
];
const trangThaiOptions = [
  { value: "", label: "Tất cả trạng thái" },
  { value: "mo", label: "Đang mở" },
  { value: "da_xu_ly", label: "Đã xử lý" },
];
const mucDoNhap = [
  { value: "loi", label: "Lỗi" },
  { value: "canh_bao", label: "Cảnh báo" },
  { value: "gop_y", label: "Góp ý" },
];
const daLoc = computed(() =>
  props.comments.filter(
    (x) => (!locMucDo.value || x.muc_do === locMucDo.value) && (!locTrangThai.value || x.trang_thai === locTrangThai.value),
  ),
);
const theoBoMon = computed(() => {
  const map = new Map<string, NhanXet[]>();
  for (const x of daLoc.value) map.set(x.bo_mon, [...(map.get(x.bo_mon) || []), x]);
  return Array.from(map.entries());
});

function nhanMucDo(m: string): string {
  return m === "loi" ? "Lỗi" : m === "canh_bao" ? "Cảnh báo" : "Góp ý";
}
function toneMucDo(m: string): "danger" | "warning" | "info" {
  return m === "loi" ? "danger" : m === "canh_bao" ? "warning" : "info";
}
function ngay(value?: string | null): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "—";
}
function gui() {
  const nd = noiDung.value.trim();
  if (!banVeId.value || !nd) return;
  emit("add", { ban_ve_id: banVeId.value, noi_dung: nd, muc_do: mucDo.value });
  noiDung.value = "";
}
</script>

<template>
  <div id="design-review-comments" class="flex flex-col gap-4">
    <div class="grid gap-2 sm:grid-cols-2">
      <Select v-model="locMucDo" label="Lọc mức độ" :options="mucDoOptions" />
      <Select v-model="locTrangThai" label="Lọc trạng thái" :options="trangThaiOptions" />
    </div>

    <form v-if="canComment" class="rounded-ds-sm border border-ds-border bg-ds-surface-2/50 p-3" @submit.prevent="gui">
      <h5 class="m-0 mb-2 text-ds-sm font-semibold text-ds-text">Thêm nhận xét</h5>
      <div class="grid gap-2 sm:grid-cols-2">
        <Select v-model="banVeId" label="Bản vẽ" :options="dsBanVe" placeholder="Chọn bản vẽ" required />
        <Select v-model="mucDo" label="Mức độ" :options="mucDoNhap" required />
      </div>
      <Textarea v-model="noiDung" class="mt-2" label="Nội dung" :rows="3" :maxlength="4000" required placeholder="Mô tả điểm cần sửa, kèm vị trí nếu có" />
      <Button class="mt-2" type="submit" size="sm" :disabled="saving || !noiDung.trim() || !banVeId">
        {{ saving ? "Đang gửi…" : "Gửi nhận xét" }}
      </Button>
    </form>

    <p v-if="loading" class="m-0 text-ds-sm text-ds-muted">Đang tải nhận xét…</p>
    <EmptyState v-else-if="!daLoc.length" title="Chưa có nhận xét" description="Nhận xét của thẩm định viên sẽ hiện ở đây." />
    <template v-else>
      <section v-for="[boMon, ds] in theoBoMon" :key="boMon" class="flex flex-col gap-2">
        <h5 class="m-0 text-ds-sm font-semibold text-ds-text">{{ boMon }}</h5>
        <article v-for="nx in ds" :key="nx.id" class="rounded-ds-sm border border-ds-border p-3">
          <div class="flex flex-wrap items-center gap-2">
            <Badge :tone="toneMucDo(nx.muc_do)" size="sm">{{ nhanMucDo(nx.muc_do) }}</Badge>
            <Badge :tone="nx.trang_thai === 'mo' ? 'warning' : 'success'" size="sm">
              {{ nx.trang_thai === "mo" ? "Đang mở" : "Đã xử lý" }}
            </Badge>
            <span class="text-ds-xs text-ds-muted">{{ nx.nguoi }} · {{ ngay(nx.created_at) }}</span>
          </div>
          <p class="mt-2 mb-0 whitespace-pre-wrap text-ds-sm text-ds-text">{{ nx.noi_dung }}</p>
          <p v-if="nx.trang_thai === 'da_xu_ly'" class="mt-1 mb-0 text-ds-xs text-ds-success">
            Đã xử lý {{ ngay(nx.xu_ly_luc) }}<template v-if="nx.ghi_chu_xu_ly"> — {{ nx.ghi_chu_xu_ly }}</template>
          </p>
          <div v-else-if="canResolve" class="mt-2 flex flex-wrap items-end gap-2">
            <label class="min-w-[220px] flex-1">
              <span class="mb-1 block text-ds-xs text-ds-muted">Ghi chú xử lý (không bắt buộc)</span>
              <input v-model="ghiChu[nx.id]" class="ds-focus h-9 w-full rounded-ds-sm border border-ds-border bg-ds-surface px-2 text-ds-sm text-ds-text" maxlength="2000" />
            </label>
            <Button size="sm" variant="secondary" :disabled="saving" @click="emit('resolve', { id: nx.id, ghi_chu: ghiChu[nx.id] || '' })">
              Đánh dấu đã xử lý
            </Button>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import { Badge, Button, EmptyState } from "../../design-system";
import { moTaSoSanh, soSanhPhienBan } from "./compare";
import type { MaBoMon, PhienBanDayDu } from "./types";

const props = defineProps<{
  versions: PhienBanDayDu[];
  currentId: string | null;
  boMonBatBuoc: readonly MaBoMon[];
}>();
const emit = defineEmits<{ select: [id: string] }>();

const chiSo = computed(() => props.versions.findIndex((v) => v.id === props.currentId));
const hienTai = computed(() => (chiSo.value >= 0 ? props.versions[chiSo.value] : null));
const truoc = computed(() => (chiSo.value >= 0 ? props.versions[chiSo.value + 1] || null : null));
const soSanh = computed(() =>
  hienTai.value && truoc.value ? soSanhPhienBan(truoc.value, hienTai.value, props.boMonBatBuoc) : null,
);
const nhanTrangThai: Record<string, string> = {
  dang_soan: "Đang soạn",
  dang_tham_dinh: "Đang thẩm định",
  dat: "Đạt",
  khong_dat: "Không đạt",
};
function tone(tt: string): "neutral" | "warning" | "success" | "danger" {
  return tt === "dat" ? "success" : tt === "khong_dat" ? "danger" : tt === "dang_tham_dinh" ? "warning" : "neutral";
}
function ngay(value?: string | null): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "—";
}
</script>

<template>
  <div id="design-review-versions" class="flex flex-col gap-4">
    <EmptyState v-if="!versions.length" title="Chưa có phiên bản thiết kế" description="Chủ đầu tư tạo phiên bản đầu tiên để bắt đầu thẩm định." />
    <template v-else>
      <div class="grid gap-2">
        <button
          v-for="v in versions"
          :id="'design-review-version-' + v.so_phien_ban"
          :key="v.id"
          type="button"
          class="ds-focus flex w-full flex-wrap items-center justify-between gap-2 rounded-ds-sm border px-3 py-2 text-left"
          :class="v.id === currentId ? 'border-ds-brand bg-ds-brand/5' : 'border-ds-border hover:bg-ds-surface-2'"
          @click="emit('select', v.id)"
        >
          <span class="flex flex-wrap items-center gap-2">
            <b class="text-ds-text">v{{ v.so_phien_ban }}</b>
            <Badge :tone="tone(v.trang_thai)" size="sm">{{ nhanTrangThai[v.trang_thai] || v.trang_thai }}</Badge>
            <span class="text-ds-sm text-ds-text">{{ v.mo_ta_thay_doi }}</span>
          </span>
          <span class="text-ds-xs text-ds-muted">{{ v.ban_ve.length }} bản vẽ · {{ ngay(v.created_at) }}</span>
        </button>
      </div>

      <div v-if="soSanh && hienTai && truoc" class="rounded-ds-sm border border-ds-border bg-ds-surface-2/60 p-3">
        <h5 class="m-0 text-ds-sm font-semibold text-ds-text">v{{ truoc.so_phien_ban }} → v{{ hienTai.so_phien_ban }}: {{ moTaSoSanh(soSanh) }}</h5>
        <ul class="mt-2 list-disc pl-5 text-ds-sm text-ds-text">
          <li v-for="bv in soSanh.them" :key="'them-' + bv.id">Thêm: {{ bv.ten }} ({{ bv.bo_mon }})</li>
          <li v-for="bv in soSanh.bo" :key="'bo-' + bv.id">Bỏ: {{ bv.ten }} ({{ bv.bo_mon }})</li>
          <li v-for="d in soSanh.doi" :key="'doi-' + d.moi.id">
            Đổi: {{ d.moi.ten }} ({{ d.moi.bo_mon }}), hash {{ d.cu.sha256.slice(0, 8) }}… → {{ d.moi.sha256.slice(0, 8) }}…
          </li>
        </ul>
        <p v-if="soSanh.thieuBoMon.length" class="mt-2 mb-0 text-ds-sm text-ds-danger">
          Thiếu bộ môn bắt buộc: {{ soSanh.thieuBoMon.join(", ") }}
        </p>
        <p v-else class="mt-2 mb-0 text-ds-sm text-ds-success">Đủ bộ môn bắt buộc.</p>
      </div>
      <p v-else-if="hienTai" class="m-0 text-ds-sm text-ds-muted">
        {{ hienTai.mo_ta_thay_doi }} — phiên bản đầu tiên, chưa có bản trước để so sánh.
      </p>
      <Button v-if="truoc" size="sm" variant="secondary" @click="emit('select', truoc.id)">Xem phiên bản trước v{{ truoc.so_phien_ban }}</Button>
    </template>
  </div>
</template>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import { Badge, Button, EmptyState, Skeleton } from "../../design-system";
import type { BanVe, NhomBoMon, PhienBan } from "./types";

const props = defineProps<{
  nhom: NhomBoMon[];
  version: PhienBan | null;
  laChuHoSo: boolean;
  laThamDinh: boolean;
  loading: boolean;
}>();
const emit = defineEmits<{
  preview: [bv: BanVe];
  download: [bv: BanVe];
  comment: [bv: BanVe];
  evaluate: [bv: BanVe, ketQua: "dat" | "khong_dat"];
}>();

const coTheSua = computed(() => props.laChuHoSo && props.version?.trang_thai === "dang_soan");

function ketQuaBoMon(n: NhomBoMon): string {
  if (!n.ban_ve.length) return "chua_co";
  if (n.ban_ve.some((bv) => bv.trang_thai === "khong_dat")) return "khong_dat";
  if (n.ban_ve.every((bv) => bv.trang_thai === "dat")) return "dat";
  return "cho_tham_dinh";
}
function nhanKetQua(kq: string): string {
  return kq === "dat" ? "Đạt" : kq === "khong_dat" ? "Không đạt" : kq === "cho_tham_dinh" ? "Chờ thẩm định" : "Chưa có bản vẽ";
}
function toneKetQua(kq: string): "success" | "danger" | "warning" | "neutral" {
  return kq === "dat" ? "success" : kq === "khong_dat" ? "danger" : kq === "cho_tham_dinh" ? "warning" : "neutral";
}
function nhanBanVe(tt: string): string {
  return tt === "dat" ? "Đạt" : tt === "khong_dat" ? "Không đạt" : "Chờ thẩm định";
}
function toneBanVe(tt: string): "success" | "danger" | "warning" {
  return tt === "dat" ? "success" : tt === "khong_dat" ? "danger" : "warning";
}
function ngay(value?: string | null): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "—";
}
function kichThuoc(value?: number | null): string {
  if (!value) return "—";
  return value >= 1024 * 1024 ? `${(value / 1024 / 1024).toFixed(1)} MB` : `${Math.round(value / 1024)} KB`;
}
</script>

<template>
  <div id="design-review-drawings" class="flex flex-col gap-4">
    <p v-if="loading" class="m-0"><Skeleton :lines="4" /></p>
    <template v-else>
      <section v-for="n in nhom" :key="n.bo_mon" class="ds-glass p-4" :aria-labelledby="`bo-mon-${n.bo_mon}`">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex flex-wrap items-center gap-2">
            <h5 :id="`bo-mon-${n.bo_mon}`" class="m-0 text-ds-md font-semibold text-ds-text">{{ n.ten }}</h5>
            <Badge :tone="n.bat_buoc ? 'danger' : 'neutral'" size="sm">{{ n.bat_buoc ? "Bắt buộc" : "Tùy chọn" }}</Badge>
            <Badge :tone="toneKetQua(ketQuaBoMon(n))" size="sm">{{ nhanKetQua(ketQuaBoMon(n)) }}</Badge>
          </div>
          <span class="text-ds-xs text-ds-muted">{{ n.ban_ve.length }} bản vẽ</span>
        </div>

        <div v-if="n.ban_ve.length" class="mt-3 overflow-x-auto" tabindex="0" role="region" :aria-labelledby="`bo-mon-${n.bo_mon}`">
          <table class="w-full min-w-[540px] border-collapse text-ds-sm">
            <thead>
              <tr class="border-b border-ds-border text-left text-ds-xs text-ds-muted">
                <th class="py-2 pr-3 font-semibold">Tên</th>
                <th class="py-2 pr-3 font-semibold">Trạng thái</th>
                <th class="py-2 pr-3 font-semibold">Người thẩm định</th>
                <th class="py-2 pr-3 font-semibold">Ngày</th>
                <th class="py-2 text-right font-semibold">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="bv in n.ban_ve" :key="bv.id" class="border-b border-ds-border align-top">
                <td class="py-2.5 pr-3">
                  <span class="font-medium text-ds-text">{{ bv.ten }}</span>
                  <span class="block text-ds-xs text-ds-muted">SHA-256: {{ bv.sha256.slice(0, 12) }}… · {{ kichThuoc(bv.kich_thuoc) }}</span>
                  <span v-if="bv.so_nhan_xet_mo" class="block text-ds-xs text-ds-warning">{{ bv.so_nhan_xet_mo }} nhận xét mở</span>
                </td>
                <td class="py-2.5 pr-3"><Badge :tone="toneBanVe(bv.trang_thai)" size="sm">{{ nhanBanVe(bv.trang_thai) }}</Badge></td>
                <td class="py-2.5 pr-3 text-ds-text">{{ bv.nguoi_tham_dinh || "—" }}</td>
                <td class="py-2.5 pr-3 text-ds-text">{{ ngay(bv.ngay_tham_dinh) }}</td>
                <td class="py-2.5">
                  <div class="flex flex-wrap justify-end gap-1.5">
                    <Button size="sm" variant="secondary" @click="emit('preview', bv)">Xem</Button>
                    <Button size="sm" variant="secondary" @click="emit('download', bv)">Tải</Button>
                    <Button size="sm" variant="ghost" @click="emit('comment', bv)">Nhận xét</Button>
                    <Button v-if="laThamDinh" size="sm" variant="secondary" @click="emit('evaluate', bv, 'dat')">Đạt</Button>
                    <Button v-if="laThamDinh" size="sm" variant="danger" @click="emit('evaluate', bv, 'khong_dat')">Không đạt</Button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState
          v-else
          class="py-6"
          :title="n.bat_buoc ? 'Chưa có bản vẽ bắt buộc' : 'Chưa có bản vẽ'"
          :description="coTheSua ? 'Thêm bản vẽ ở nút phía trên.' : 'Chủ đầu tư chưa nộp bản vẽ cho bộ môn này.'"
        />
      </section>
      <EmptyState v-if="!nhom.length" title="Chưa có bộ môn" description="Danh mục bộ môn chưa được nạp." />
    </template>
  </div>
</template>

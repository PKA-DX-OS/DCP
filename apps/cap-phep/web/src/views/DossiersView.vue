<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <section>
    <div class="flex flex-wrap items-end gap-4 mb-6">
      <div class="min-w-0">
        <h1 class="tieu-de-trang">Hồ sơ cấp phép</h1>
        <p class="text-phu text-[16px] mt-2 mb-0">{{ summary }}</p>
      </div>
      <div class="flex-1"></div>

      <div v-if="isStaff" class="w-full sm:w-auto">
        <label for="txt-open-dossier-code" class="nhan">Tra cứu hồ sơ theo mã (cán bộ)</label>
        <div class="flex gap-2">
          <input
            v-model="searchCode"
            id="txt-open-dossier-code"
            type="text"
            placeholder="CP-2026-xxxxxx"
            class="o sm:w-56"
            aria-describedby="goi-y-tra-cuu"
            @keydown.enter="handleOpenByCode"
          />
          <button type="button" id="btn-open-by-code" class="btn" :disabled="!searchCode.trim()" @click="handleOpenByCode">Mở hồ sơ</button>
        </div>
      </div>

      <div class="flex gap-2">
        <button type="button" class="btn" @click="$emit('refresh')">Làm mới</button>
        <button
          v-if="isApplicant || !isStaff"
          type="button"
          id="btn-nop-ho-so-modal"
          class="btn btn-chinh"
          @click="$emit('create-dossier')"
        >Nộp hồ sơ mới</button>
      </div>
    </div>
    <p v-if="isStaff" id="goi-y-tra-cuu" class="goi-y -mt-2 mb-4 sm:text-right">
      Hồ sơ chưa được phân công sẽ cần yêu cầu truy cập khẩn có lý do, được lãnh đạo duyệt và ghi nhật ký.
    </p>

    <div v-if="errorMsg" class="thong-bao-loi mb-4" role="alert">{{ errorMsg }}</div>

    <div class="the overflow-hidden">
      <div class="flex gap-2 px-4 py-3.5 border-b border-vien-nhat overflow-x-auto" role="group" aria-label="Lọc theo trạng thái">
        <button
          v-for="f in filters"
          :key="f.key"
          type="button"
          :aria-pressed="filter === f.key"
          :class="['chip', filter === f.key && 'chip-chon']"
          @click="filter = f.key"
        >{{ f.label }}<span v-if="f.count" class="ml-1 opacity-70">{{ f.count }}</span></button>
      </div>

      <div v-if="dossiers.length === 0" id="empty-dossiers-state" class="px-6 py-12 text-center">
        <p class="font-medium m-0">Chưa có hồ sơ nào.</p>
        <p v-if="isStaff" class="text-phu mt-1.5 mb-0 max-w-[460px] mx-auto">
          Danh sách chỉ hiện hồ sơ được giao cho bạn. Để mở hồ sơ khác, nhập mã hồ sơ vào ô tra cứu ở trên.
        </p>
        <p v-else class="text-phu mt-1.5 mb-0">Bấm "Nộp hồ sơ mới" để bắt đầu.</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="bang" id="table-ho-so">
          <thead>
            <tr>
              <th>Mã hồ sơ</th>
              <th>Chủ đầu tư</th>
              <th>Công trình</th>
              <th>Trạng thái</th>
              <th>Hạn giải quyết</th>
              <th><span class="sr-only">Thao tác</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in shown" :key="d.id">
              <td class="ma whitespace-nowrap">{{ d.ma_ho_so }}</td>
              <td>
                {{ d.ho_ten }}
                <div class="mo">CCCD {{ cheCccd(d.cccd) }}</div>
              </td>
              <td class="max-w-[280px]">
                {{ d.dia_chi_cong_trinh }}
                <div class="mo">{{ d.so_tang }} tầng, {{ formatNumberVi(d.dien_tich_san_m2) }} m²</div>
              </td>
              <td class="whitespace-nowrap">
                <span :class="getStatusBadgeClass(d.trang_thai)">{{ formatStatus(d.trang_thai) }}</span>
                <span v-if="d.qua_han" class="tt tt-do ml-1">Quá hạn</span>
              </td>
              <td :class="['whitespace-nowrap', hanGap(d) && 'text-son font-semibold']">{{ hanText(d) }}</td>
              <td class="text-right whitespace-nowrap">
                <button
                  v-if="d.trang_thai === 'CAN_BO_SUNG'"
                  type="button"
                  :id="'btn-supplement-' + d.ma_ho_so"
                  class="btn btn-sm mr-1.5 text-vang"
                  @click="$emit('supplement', d)"
                >Bổ sung</button>
                <button type="button" :id="'btn-detail-' + d.ma_ho_so" class="btn btn-sm" @click="$emit('view-detail', d)">Xem</button>
              </td>
            </tr>
            <tr v-if="shown.length === 0">
              <td colspan="6" class="text-center text-phu py-8">Không có hồ sơ nào ở trạng thái này.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import type { HoSo } from "../types";
import { formatStatus, getStatusBadgeClass, formatNumberVi } from "../utils/formatters";
import { cheCccd, ngayNgan } from "../utils/labels";

const props = defineProps<{
  dossiers: HoSo[];
  errorMsg: string;
  isStaff?: boolean;
  isApplicant?: boolean;
}>();

const emit = defineEmits<{
  (e: "create-dossier"): void;
  (e: "refresh"): void;
  (e: "view-detail", dossier: HoSo): void;
  (e: "supplement", dossier: HoSo): void;
  (e: "open-by-code", code: string): void;
}>();

const searchCode = ref("");
type FilterKey = "all" | "dang" | "bo-sung" | "cap" | "qua-han";
const filter = ref<FilterKey>("all");

const DANG = ["DA_NOP", "CHO_TIEP_NHAN", "TIEP_NHAN", "DUOC_PHAN_CONG", "DANG_THAM_DINH", "CHO_DUYET", "CHO_KY"];
const match: Record<FilterKey, (d: HoSo) => boolean> = {
  all: () => true,
  dang: (d) => DANG.includes(String(d.trang_thai)),
  "bo-sung": (d) => d.trang_thai === "CAN_BO_SUNG",
  cap: (d) => d.trang_thai === "DA_CAP",
  "qua-han": (d) => Boolean((d as any).qua_han),
};

const filters = computed(() => [
  { key: "all" as FilterKey, label: "Tất cả", count: 0 },
  { key: "dang" as FilterKey, label: "Đang xử lý", count: props.dossiers.filter(match.dang).length },
  { key: "bo-sung" as FilterKey, label: "Cần bổ sung", count: props.dossiers.filter(match["bo-sung"]).length },
  { key: "cap" as FilterKey, label: "Đã cấp phép", count: props.dossiers.filter(match.cap).length },
  { key: "qua-han" as FilterKey, label: "Quá hạn", count: props.dossiers.filter(match["qua-han"]).length },
]);

const shown = computed(() => props.dossiers.filter(match[filter.value]));

function daysLeft(d: HoSo): number | null {
  const v = (d as any).han_tong_at;
  if (!v) return null;
  const t = new Date(v).getTime();
  if (isNaN(t)) return null;
  return Math.ceil((t - Date.now()) / 86400000);
}

function hanGap(d: HoSo): boolean {
  if (d.trang_thai === "DA_CAP" || d.trang_thai === "TU_CHOI") return false;
  const n = daysLeft(d);
  return n !== null && n <= 2;
}

function hanText(d: HoSo): string {
  const n = daysLeft(d);
  if (n === null) return "";
  if (d.trang_thai !== "DA_CAP" && d.trang_thai !== "TU_CHOI") {
    if (n < 0) return `Quá ${-n} ngày`;
    if (n === 0) return "Hết hạn hôm nay";
    if (n <= 2) return `Còn ${n} ngày`;
  }
  return ngayNgan((d as any).han_tong_at);
}

const summary = computed(() => {
  const total = props.dossiers.length;
  if (total === 0) return "Chưa có hồ sơ";
  const sap = props.dossiers.filter(hanGap).length;
  return sap > 0 ? `${total} hồ sơ, ${sap} hồ sơ sắp đến hạn` : `${total} hồ sơ`;
});

function handleOpenByCode() {
  if (!searchCode.value.trim()) return;
  emit("open-by-code", searchCode.value.trim());
}
</script>

<style scoped>
.chip {
  height: 32px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid var(--vien-nhat);
  background: transparent;
  color: rgb(var(--c-phu));
  font-size: 13px;
  white-space: nowrap;
  transition: background 500ms var(--em), color 500ms var(--em), border-color 500ms var(--em), transform 500ms var(--em);
}
.chip:hover {
  color: rgb(var(--c-chu));
  background: var(--mat-2);
  border-color: var(--vien);
  transform: translateY(-1px);
}
.chip-chon,
.chip-chon:hover {
  background: var(--mat-noi);
  border-color: var(--vien-noi);
  color: rgb(var(--c-chu));
}
</style>

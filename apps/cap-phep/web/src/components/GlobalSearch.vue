<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { timKiemToanCuc, type KetQuaTimKiem, type MucTimKiem, type NguonDuLieu } from "../api/dh";
import { useModal } from "../composables/useModal";

const props = defineProps<{ token: string }>();
const emit = defineEmits<{
  (e: "close"): void;
  (e: "mo-ho-so", id: string): void;
}>();

const hop = ref<HTMLElement | null>(null);
const oNhap = ref<HTMLInputElement | null>(null);
const tuKhoa = ref("");
const ketQua = ref<KetQuaTimKiem | null>(null);
const nguon = ref<NguonDuLieu | null>(null);
const dangTim = ref(false);
const loi = ref("");
const chon = ref(0);
let hen: ReturnType<typeof setTimeout> | null = null;
let lan = 0;

useModal(hop, () => emit("close"));

const phang = computed(() =>
  (ketQua.value?.groups || []).flatMap((nhom) => nhom.items.map((muc) => ({ ...muc, nhom: nhom.type }))),
);

const NHAN_LOAI: Record<string, string> = {
  ho_so: "Hồ sơ",
  chu_dau_tu: "Chủ đầu tư",
  thua_dat: "Thửa đất",
  cong_trinh: "Công trình",
  giay_phep: "Giấy phép",
};

const NHAN_KHOP: Record<string, string> = {
  exact: "Khớp chính xác",
  prefix: "Khớp đầu chuỗi",
  fuzzy: "Gần đúng",
};

function tenLoai(type: string): string {
  return NHAN_LOAI[type] || type;
}

function tenKhop(khop: string): string {
  return NHAN_KHOP[khop] || khop;
}

function tongNhom(type: string): number {
  return ketQua.value?.groups.find((g) => g.type === type)?.total ?? 0;
}

function moDuoc(m: MucTimKiem): boolean {
  return Boolean(m.dossier_id || (m.type === "ho_so" && m.id));
}

function idDeMo(m: MucTimKiem): string {
  return m.dossier_id || (m.type === "ho_so" ? m.id : "");
}

function mo(m: MucTimKiem): void {
  const id = idDeMo(m);
  if (id) emit("mo-ho-so", id);
}

function chonMuc(i: number, m: MucTimKiem): void {
  if (moDuoc(m)) chon.value = i;
}

function moMucDangChon(e?: KeyboardEvent): void {
  if (e?.isComposing || dangTim.value) return;
  const muc = phang.value[chon.value];
  if (muc && moDuoc(muc)) mo(muc);
}

function diChuyen(buoc: number, e?: KeyboardEvent): void {
  if (e?.isComposing || dangTim.value) return;
  const ds = phang.value;
  if (!ds.length) return;
  let i = chon.value;
  for (let k = 0; k < ds.length; k++) {
    i = (i + buoc + ds.length) % ds.length;
    if (moDuoc(ds[i])) {
      chon.value = i;
      void nextTick(() => document.getElementById(`ket-qua-tim-${i}`)?.scrollIntoView({ block: "nearest" }));
      return;
    }
  }
}

function chonDauTienMoDuoc(): void {
  const i = phang.value.findIndex(moDuoc);
  chon.value = i < 0 ? 0 : i;
}

async function tim(q: string): Promise<void> {
  const lanNay = ++lan;
  dangTim.value = true;
  loi.value = "";
  try {
    const kq = await timKiemToanCuc(props.token, q);
    if (lanNay !== lan) return;
    ketQua.value = kq.data;
    nguon.value = kq.source;
    chonDauTienMoDuoc();
  } catch (e) {
    if (lanNay !== lan) return;
    ketQua.value = null;
    nguon.value = null;
    loi.value = e instanceof Error ? e.message : "Không tìm kiếm được";
  } finally {
    if (lanNay === lan) dangTim.value = false;
  }
}

watch(tuKhoa, (value) => {
  if (hen) clearTimeout(hen);
  const q = value.trim();
  if (q.length < 2) {
    lan += 1;
    ketQua.value = null;
    nguon.value = null;
    dangTim.value = false;
    loi.value = "";
    return;
  }
  hen = setTimeout(() => void tim(q), 300);
});

onBeforeUnmount(() => {
  if (hen) clearTimeout(hen);
  lan += 1;
});
</script>

<template>
  <div class="nen-hop nen-tim" @click.self="emit('close')">
    <div
      ref="hop"
      class="hop w-full max-w-[720px] overflow-hidden !rounded-[24px]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tieu-de-tim-kiem"
    >
      <h2 id="tieu-de-tim-kiem" class="sr-only">Tìm kiếm toàn cục</h2>

      <div class="flex items-center gap-3 border-b border-vien-nhat px-4 py-3">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" />
          <path d="m16 16 4.5 4.5" />
        </svg>
        <input
          ref="oNhap"
          v-model="tuKhoa"
          type="search"
          class="min-w-0 flex-1 border-0 bg-transparent p-0 text-[15px] text-chu outline-none placeholder:text-phu/80"
          placeholder="Tìm mã hồ sơ, CCCD, họ tên, điện thoại, địa chỉ, số giấy phép…"
          aria-label="Từ khóa tìm kiếm toàn cục"
          autocomplete="off"
          spellcheck="false"
          @keydown.down.prevent="diChuyen(1, $event)"
          @keydown.up.prevent="diChuyen(-1, $event)"
          @keydown.enter.prevent="moMucDangChon($event)"
        />
        <kbd class="rounded-[8px] border border-vien-nhat px-2 py-0.5 text-[11px] text-phu">Esc</kbd>
      </div>

      <div class="max-h-[58vh] overflow-y-auto p-2">
        <p v-if="dangTim" class="m-0 px-3 py-6 text-center text-[13px] text-phu" role="status">Đang tìm…</p>
        <p v-else-if="loi" class="m-0 px-3 py-6 text-center text-[13px] text-son" role="alert">{{ loi }}</p>
        <p v-else-if="tuKhoa.trim().length < 2" class="m-0 px-3 py-6 text-center text-[13px] text-phu">
          Nhập ít nhất 2 ký tự để tìm trong hồ sơ, công dân, thửa đất, công trình và giấy phép.
        </p>
        <p v-else-if="!phang.length" class="m-0 px-3 py-6 text-center text-[13px] text-phu">
          Không tìm thấy kết quả phù hợp với “{{ tuKhoa.trim() }}”.
        </p>

        <template v-else>
          <p class="sr-only" role="status" aria-live="polite">{{ phang.length }} kết quả</p>
          <template v-for="(m, i) in phang" :key="`${m.nhom}-${m.id}-${i}`">
            <p
              v-if="i === 0 || phang[i - 1].nhom !== m.nhom"
              class="m-0 px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wide text-phu"
            >
              {{ tenLoai(m.nhom) }}
              <span class="font-normal normal-case">· {{ tongNhom(m.nhom) }}</span>
            </p>
            <button
              :id="`ket-qua-tim-${i}`"
              type="button"
              class="flex w-full items-start gap-3 rounded-[14px] px-3 py-2.5 text-left transition-colors"
              :class="[chon === i ? 'bg-mat-2' : 'hover:bg-mat-2', moDuoc(m) ? '' : 'cursor-default opacity-70']"
              :disabled="!moDuoc(m)"
              :title="moDuoc(m) ? 'Mở hồ sơ liên quan' : 'Kết quả này chưa gắn hồ sơ để mở'"
              @mouseenter="chonMuc(i, m)"
              @click="mo(m)"
            >
              <span class="mt-0.5 grid h-7 w-7 flex-none place-items-center rounded-full bg-mat text-[11px] font-semibold text-phu" aria-hidden="true">
                {{ tenLoai(m.nhom).slice(0, 1) }}
              </span>
              <span class="min-w-0 flex-1">
                <span class="flex flex-wrap items-baseline justify-between gap-2">
                  <b class="min-w-0 break-words text-[13.5px] font-medium">{{ m.nhan }}</b>
                  <span class="whitespace-nowrap rounded-full bg-mat px-2 py-0.5 text-[11px] text-phu">{{ tenKhop(m.khop) }}</span>
                </span>
                <span v-if="m.phu" class="mt-0.5 block break-words text-[12.5px] text-phu">{{ m.phu }}</span>
                <span v-if="!moDuoc(m)" class="mt-0.5 block text-[11.5px] text-vang">Chưa gắn hồ sơ để mở</span>
              </span>
            </button>
          </template>
        </template>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-2 border-t border-vien-nhat px-4 py-2.5 text-[11.5px] text-phu">
        <span v-if="nguon === 'api'">Dữ liệu tìm kiếm toàn cục</span>
        <span v-else-if="nguon === 'cuc-bo'">Tìm trong danh sách hồ sơ hiện có — API tìm kiếm chưa sẵn sàng</span>
        <span v-else> Tìm theo mã hồ sơ, CCCD, họ tên, điện thoại, địa chỉ, số giấy phép </span>
        <span class="flex items-center gap-2">
          <span>↑↓ chọn</span>
          <span>Enter mở</span>
          <span>Esc đóng</span>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.nen-tim {
  z-index: 80;
  align-items: flex-start;
  padding-top: 10vh;
}
</style>

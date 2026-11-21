<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { taiHieuQua, type ChiSoHieuQua } from "../../api/automation";

const props = defineProps<{ thang?: string }>();

const duLieu = ref<ChiSoHieuQua | null>(null);
const nguon = ref<"api" | "mock" | null>(null);
const loading = ref(false);
const loi = ref("");
let lan = 0;

const kyMoc = computed(() => duLieu.value?.baseline_label || "v1.1");

function cuoiThang(thang: string): string | undefined {
  const [nam, thangSo] = thang.split("-").map(Number);
  if (!nam || !thangSo) return undefined;
  return new Date(Date.UTC(nam, thangSo, 0)).toISOString().slice(0, 10);
}

function dinhDang(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const so = Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 2 });
  if (unit === "%") return `${so}%`;
  return unit ? `${so} ${unit}` : so;
}

function nhanDelta(m: ChiSoHieuQua["metrics"][number]): string {
  if (m.current === null || m.current === undefined) return "Chưa có số hiện tại";
  if (m.delta_pct === null || m.delta_pct === undefined) return "Chưa có mốc so sánh";
  if (m.delta_pct === 0) return "Không đổi so với mốc";
  const dau = m.delta_pct > 0 ? "+" : "";
  const so = Number(m.delta_pct).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
  return `${dau}${so}% so với mốc`;
}

function lopDelta(m: ChiSoHieuQua["metrics"][number]): string {
  if (m.current === null || m.delta_pct === null || m.delta_pct === undefined || m.delta_pct === 0) {
    return "text-phu";
  }
  const tot = m.better === "lower" ? m.delta_pct < 0 : m.delta_pct > 0;
  return tot ? "text-xanh" : "text-son";
}

function ngayGio(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("vi-VN");
}

async function tai(): Promise<void> {
  const lanNay = ++lan;
  loading.value = true;
  loi.value = "";
  const from = props.thang ? `${props.thang}-01` : undefined;
  const to = props.thang ? cuoiThang(props.thang) : undefined;
  try {
    const kq = await taiHieuQua(from, to);
    if (lanNay !== lan) return;
    duLieu.value = kq.data;
    nguon.value = kq.source;
  } catch (e) {
    if (lanNay !== lan) return;
    duLieu.value = null;
    nguon.value = null;
    loi.value = e instanceof Error ? e.message : "Không tải được chỉ số hiệu quả";
  } finally {
    if (lanNay === lan) loading.value = false;
  }
}

watch(() => props.thang, () => void tai());
onMounted(tai);
</script>

<template>
  <section class="space-y-4" aria-labelledby="tieu-de-hieu-qua">
    <div class="mb-2 flex flex-wrap items-end gap-3">
      <div>
        <h1 id="tieu-de-hieu-qua" class="tieu-de-trang">Hiệu quả vận hành</h1>
        <p class="mt-2 max-w-2xl text-[15px] text-phu">
          Thao tác thủ công, chuyển tay, hồ sơ phải bổ sung, thời gian xử lý và tự phục vụ — tính từ nhật ký và hồ sơ.
        </p>
      </div>
      <div class="flex-1"></div>
      <span v-if="nguon" class="tt" :class="nguon === 'api' ? 'tt-xanh' : 'tt-vang'">
        {{ nguon === "api" ? "Số đo thật" : "Mốc v1.1, chưa có số hiện tại" }}
      </span>
      <button type="button" class="btn" :disabled="loading" @click="tai()">
        {{ loading ? "Đang tải…" : "Làm mới" }}
      </button>
    </div>

    <div v-if="loading" class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4" role="status" aria-busy="true">
      <span class="sr-only">Đang tải chỉ số hiệu quả vận hành</span>
      <div v-for="i in 7" :key="i" class="kinh animate-pulse space-y-3 p-4 shadow" aria-hidden="true">
        <div class="h-3 w-2/3 rounded bg-slate-200 dark:bg-slate-700"></div>
        <div class="h-8 w-1/3 rounded bg-slate-200 dark:bg-slate-700"></div>
        <div class="h-3 w-1/2 rounded bg-slate-200 dark:bg-slate-700"></div>
      </div>
    </div>

    <div v-else-if="loi" class="the p-4" role="alert">
      <p class="m-0 text-son">Không tải được chỉ số hiệu quả: {{ loi }}</p>
      <button type="button" class="btn btn-sm mt-3" @click="tai()">Thử lại</button>
    </div>

    <template v-else-if="duLieu">
      <div
        v-if="nguon === 'mock'"
        class="rounded-lg border border-amber-300 bg-amber-50 p-4 text-[13.5px] text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100"
        role="note"
      >
        <p class="m-0 font-semibold">Chưa có API chỉ số hiệu quả</p>
        <p class="m-0 mt-1">
          API <code>/api/v1/automation/metrics</code> chưa triển khai. Màn hình chỉ hiển thị mốc đo v1.1 để đối chiếu;
          không hiển thị số hiện tại và không dùng để công bố tiết kiệm.
        </p>
      </div>

      <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[13px] text-phu">
        <span v-if="duLieu.period.from || duLieu.period.to">
          Kỳ {{ duLieu.period.from || "—" }} → {{ duLieu.period.to || "—" }}
        </span>
        <span v-else>Mốc so sánh: {{ kyMoc }}</span>
        <span>· {{ duLieu.so_ho_so }} hồ sơ</span>
        <span v-if="nguon === 'api'">· tính lúc {{ ngayGio(duLieu.computed_at) }}</span>
      </div>

      <div v-if="duLieu.metrics.length" class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
        <article v-for="m in duLieu.metrics" :key="m.key" class="the p-4">
          <p class="m-0 min-h-[34px] text-[12.5px] font-medium text-phu">{{ m.label }}</p>
          <p class="mt-2 break-words text-[30px] font-semibold leading-none tracking-[-0.02em]">
            {{ dinhDang(m.current, m.unit) }}
          </p>
          <p class="m-0 mt-2 text-[12.5px] text-phu">
            Mốc {{ kyMoc }}: <b class="font-medium text-chu">{{ dinhDang(m.baseline, m.unit) }}</b>
          </p>
          <p class="m-0 mt-1 text-[12px]" :class="lopDelta(m)">{{ nhanDelta(m) }}</p>
          <p class="m-0 mt-3 break-all text-[11px] text-phu">Nguồn: {{ m.source }}</p>
        </article>
      </div>

      <p v-else class="rounded-lg kinh p-4 text-sm text-phu">API chưa trả chỉ số nào cho kỳ này.</p>

      <div class="the p-4">
        <h2 class="m-0 text-sm font-semibold">Cách đọc</h2>
        <p class="m-0 mt-1 text-[13px] text-phu">
          “Thấp hơn tốt” nghĩa là giảm so với mốc là cải thiện; “cao hơn tốt” thì ngược lại. Chỉ số chỉ được coi là số thật
          khi API trả về; mốc v1.1 lấy từ <code>docs/data/baseline-v1.1.md</code>.
        </p>
        <ul v-if="duLieu.ghi_chu?.length" class="m-0 mt-2 list-none space-y-1 p-0 text-[13px] text-phu">
          <li v-for="(g, i) in duLieu.ghi_chu" :key="i">· {{ g }}</li>
        </ul>
      </div>
    </template>
  </section>
</template>

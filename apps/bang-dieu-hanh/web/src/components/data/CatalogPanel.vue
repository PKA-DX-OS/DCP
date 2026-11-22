<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import {
  fetchCatalogAsset,
  fetchCatalogAssets,
  fetchCatalogContracts,
  type HopDongDuLieu,
  type PhanLoaiDuLieu,
  type TaiSanChiTiet,
  type TaiSanDuLieu,
} from "../../api/catalog";
import { formatThoiDiem } from "../../utils/metrics";

const TEN_MIEN: Record<string, string> = {
  cong_dan: "Công dân",
  thua_dat: "Thửa đất",
  ho_so: "Hồ sơ",
  giay_phep: "Giấy phép",
  cong_trinh: "Công trình",
  giay_to: "Giấy tờ",
  kiem_tra: "Kiểm tra",
  tai_chinh: "Tài chính",
  audit: "Nhật ký",
  he_thong: "Hệ thống",
};

const NHAN_PHAN_LOAI: Record<PhanLoaiDuLieu, string> = {
  public: "Công khai",
  internal: "Nội bộ",
  pii: "Dữ liệu cá nhân",
  sensitive: "Nhạy cảm",
};

const assets = ref<TaiSanDuLieu[]>([]);
const chiTiet = ref<TaiSanChiTiet | null>(null);
const hopDong = ref<HopDongDuLieu[]>([]);
const loading = ref(false);
const loadingChiTiet = ref(false);
const error = ref("");
const errorChiTiet = ref("");
const locMien = ref("");
const locPhanLoai = ref<PhanLoaiDuLieu | "">("");
const dsMien = ref<string[]>([]);

function tenMien(v: string): string {
  return TEN_MIEN[v] || v;
}

function nhanPhanLoai(v: string): string {
  return NHAN_PHAN_LOAI[v as PhanLoaiDuLieu] || v;
}

function lopPhanLoai(v: string): string {
  if (v === "sensitive") return "tt tt-do";
  if (v === "pii") return "tt tt-vang";
  if (v === "public") return "tt tt-xanh";
  return "tt tt-xam";
}

function ngay(iso: string | null): string {
  return iso ? formatThoiDiem(iso) : "—";
}

function diem(v: number | null): string {
  return v === null || v === undefined ? "—" : Number(v).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
}

function lopDiem(v: number | null): string {
  if (v === null || v === undefined) return "text-phu";
  return v >= 80 ? "text-xanh" : v >= 50 ? "text-vang" : "text-son";
}

async function tai(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    assets.value = await fetchCatalogAssets({
      domain: locMien.value || undefined,
      classification: locPhanLoai.value || undefined,
    });
    if (!locMien.value && !locPhanLoai.value) {
      dsMien.value = Array.from(new Set(assets.value.map((a) => a.domain))).sort();
    }
    if (chiTiet.value && !assets.value.some((a) => a.asset === chiTiet.value?.asset)) {
      chiTiet.value = null;
      hopDong.value = [];
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được danh mục dữ liệu";
  } finally {
    loading.value = false;
  }
}

async function chon(a: TaiSanDuLieu): Promise<void> {
  loadingChiTiet.value = true;
  errorChiTiet.value = "";
  try {
    const [ct, hd] = await Promise.all([fetchCatalogAsset(a.asset), fetchCatalogContracts(a.asset)]);
    chiTiet.value = ct;
    hopDong.value = hd;
  } catch (e) {
    chiTiet.value = null;
    hopDong.value = [];
    errorChiTiet.value = e instanceof Error ? e.message : "Không tải được chi tiết tài sản";
  } finally {
    loadingChiTiet.value = false;
  }
}

watch([locMien, locPhanLoai], () => void tai());
onMounted(tai);
</script>

<template>
  <section class="space-y-4" aria-labelledby="tieu-de-catalog">
    <div class="mb-2 flex flex-wrap items-end gap-3">
      <div>
        <h1 id="tieu-de-catalog" class="tieu-de-trang">Danh mục dữ liệu</h1>
        <p class="mt-2 max-w-3xl text-[15px] text-phu">
          Tài sản dữ liệu, chủ quản, phân loại, thời hạn lưu trữ, độ tươi và hợp đồng dữ liệu.
        </p>
      </div>
      <div class="flex-1"></div>
      <label class="flex items-center gap-2 text-[12.5px] text-phu">
        Miền
        <select v-model="locMien" class="o w-auto">
          <option value="">Tất cả</option>
          <option v-for="m in dsMien" :key="m" :value="m">{{ tenMien(m) }}</option>
        </select>
      </label>
      <label class="flex items-center gap-2 text-[12.5px] text-phu">
        Phân loại
        <select v-model="locPhanLoai" class="o w-auto">
          <option value="">Tất cả</option>
          <option value="public">Công khai</option>
          <option value="internal">Nội bộ</option>
          <option value="pii">Dữ liệu cá nhân</option>
          <option value="sensitive">Nhạy cảm</option>
        </select>
      </label>
      <button type="button" class="btn" :disabled="loading" @click="tai">
        {{ loading ? "Đang tải…" : "Làm mới" }}
      </button>
    </div>

    <div v-if="loading" class="the p-4" role="status" aria-busy="true">
      <span class="sr-only">Đang tải danh mục dữ liệu</span>
      <div class="animate-pulse space-y-3" aria-hidden="true">
        <div v-for="i in 6" :key="i" class="h-10 rounded bg-slate-200 dark:bg-slate-700"></div>
      </div>
    </div>

    <div v-else-if="error" class="the p-4" role="alert">
      <p class="m-0 text-son">Không tải được danh mục: {{ error }}</p>
      <button class="btn btn-sm mt-3" @click="tai">Thử lại</button>
    </div>

    <template v-else>
      <div class="the overflow-hidden">
        <table class="bang w-full text-[12.5px]">
          <thead>
            <tr>
              <th>Tài sản</th>
              <th>Miền</th>
              <th>Chủ quản</th>
              <th>Phân loại</th>
              <th>Lưu trữ</th>
              <th>Độ tươi</th>
              <th>Điểm DQ</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="a in assets"
              :key="a.asset"
              class="cursor-pointer transition-colors hover:bg-mat-2"
              :class="chiTiet?.asset === a.asset && 'bg-mat-2'"
              @click="chon(a)"
            >
              <td>
                <button
                  type="button"
                  class="text-left font-medium underline-offset-2 hover:underline"
                  :aria-pressed="chiTiet?.asset === a.asset"
                  @click.stop="chon(a)"
                >
                  {{ a.asset }}
                </button>
                <span class="block text-[11.5px] text-phu">{{ a.description }}</span>
              </td>
              <td class="whitespace-nowrap">{{ tenMien(a.domain) }}</td>
              <td class="whitespace-nowrap">{{ a.owner }}</td>
              <td class="whitespace-nowrap"><span :class="lopPhanLoai(a.classification)">{{ nhanPhanLoai(a.classification) }}</span></td>
              <td class="whitespace-nowrap">{{ a.retention || "—" }}</td>
              <td class="whitespace-nowrap">{{ a.freshness_sla || "—" }}</td>
              <td class="whitespace-nowrap">
                <b :class="lopDiem(a.dq_score)">{{ diem(a.dq_score) }}</b>
              </td>
            </tr>
            <tr v-if="!assets.length">
              <td colspan="7" class="py-6 text-center text-phu">Không có tài sản khớp bộ lọc.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="sr-only" role="status">{{ chiTiet ? `Đã tải chi tiết ${chiTiet.asset}` : "" }}</p>
      <div v-if="loadingChiTiet" class="the p-4" role="status">Đang tải chi tiết tài sản…</div>
      <div v-else-if="errorChiTiet" class="the p-4" role="alert">
        <p class="m-0 text-son">{{ errorChiTiet }}</p>
      </div>
      <div v-else-if="chiTiet" class="grid gap-4 lg:grid-cols-2">
        <div class="the p-4">
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 class="m-0 text-[15px] font-semibold">{{ chiTiet.asset }}</h2>
              <p class="m-0 mt-1 text-[12.5px] text-phu">{{ chiTiet.description }}</p>
            </div>
            <span :class="lopPhanLoai(chiTiet.classification)">{{ nhanPhanLoai(chiTiet.classification) }}</span>
          </div>
          <dl class="ds-thong-tin mt-3">
            <dt>Chủ quản</dt><dd>{{ chiTiet.owner }}</dd>
            <dt>Quản lý chất lượng</dt><dd>{{ chiTiet.steward || "—" }}</dd>
            <dt>Lưu trữ</dt><dd>{{ chiTiet.retention || "—" }}</dd>
            <dt>Độ tươi</dt><dd>{{ chiTiet.freshness_sla || "—" }}</dd>
            <dt>Cập nhật</dt><dd>{{ ngay(chiTiet.last_updated) }}</dd>
            <dt>Phiên bản</dt><dd>{{ chiTiet.version }}</dd>
            <dt>Điểm DQ</dt><dd>{{ diem(chiTiet.dq_score) }}</dd>
          </dl>
          <h3 class="mt-4 mb-1 text-[13px] font-semibold">Cột dữ liệu</h3>
          <div class="max-h-[320px] overflow-y-auto" tabindex="0" role="region" aria-label="Cột dữ liệu của tài sản">
            <table class="bang w-full text-[12px]">
              <thead><tr><th>Cột</th><th>Kiểu</th><th>Phân loại</th><th>Che API</th></tr></thead>
              <tbody>
                <tr v-for="c in chiTiet.columns" :key="c.name">
                  <td class="font-medium">{{ c.name }}</td>
                  <td>{{ c.type }}</td>
                  <td><span :class="lopPhanLoai(c.classification)">{{ nhanPhanLoai(c.classification) }}</span></td>
                  <td>{{ c.masked_in_api ? "Có" : "—" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="the p-4">
          <h2 class="m-0 text-[15px] font-semibold">Hợp đồng dữ liệu</h2>
          <p v-if="!hopDong.length" class="mt-2 mb-0 text-[13px] text-phu">Chưa có hợp đồng cho tài sản này.</p>
          <div v-for="h in hopDong" :key="`${h.asset}-${h.version}`" class="mt-3 rounded-[14px] border border-vien-nhat p-3 text-[12.5px]">
            <p class="m-0 font-semibold">Phiên bản {{ h.version }}</p>
            <p class="m-0 mt-1 text-phu">Độ tươi: {{ h.sla.freshness || "—" }} · sẵn sàng: {{ h.sla.availability_pct ?? "—" }}%</p>
            <p class="m-0 mt-1 text-phu">Bên dùng: {{ h.consumers.join(", ") || "—" }}</p>
            <p class="m-0 mt-1 text-phu">Hiệu lực: {{ ngay(h.effective_from) }}</p>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

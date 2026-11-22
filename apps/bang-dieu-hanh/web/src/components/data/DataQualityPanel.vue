<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import {
  fetchDqIssues,
  fetchDqRules,
  fetchDqSummary,
  resolveDqIssue,
  type MienDuLieu,
  type MucDoDq,
  type RuleDq,
  type TongQuanDq,
  type TrangThaiDq,
  type VanDeDq,
} from "../../api/data-quality";
import { formatThoiDiem } from "../../utils/metrics";

const props = defineProps<{ vaiTro: string[] }>();

const VAI_DONG = ["dx:tenant-admin", "dx:data-steward", "dx:platform-admin"];
const coTheDong = computed(() => props.vaiTro.some((r) => VAI_DONG.includes(r)));

const TEN_MIEN: Record<MienDuLieu, string> = {
  cong_dan: "Công dân",
  thua_dat: "Thửa đất",
  ho_so: "Hồ sơ",
  giay_phep: "Giấy phép",
  cong_trinh: "Công trình",
  giay_to: "Giấy tờ",
  kiem_tra: "Kiểm tra",
  tai_chinh: "Tài chính",
  audit: "Nhật ký",
};

const summary = ref<TongQuanDq | null>(null);
const rules = ref<RuleDq[]>([]);
const issues = ref<{ items: VanDeDq[]; page: number; page_size: number; total: number } | null>(null);
const loading = ref(false);
const error = ref("");
const dangDong = ref<string | null>(null);
const moGhiChu = ref<string | null>(null);
const ghiChu = reactive<Record<string, string>>({});
const thongBao = ref("");

const boLoc = reactive<{ domain: MienDuLieu | ""; severity: MucDoDq | ""; status: TrangThaiDq | "" }>({
  domain: "",
  severity: "",
  status: "open",
});

const soTrang = computed(() => {
  const i = issues.value;
  if (!i) return 1;
  return Math.max(1, Math.ceil(i.total / Math.max(1, i.page_size)));
});

function tenMien(v: string): string {
  return TEN_MIEN[v as MienDuLieu] || v;
}

function nhanMucDo(v: string): string {
  return v === "critical" ? "Nghiêm trọng" : v === "warn" ? "Cảnh báo" : "Thông tin";
}

function lopMucDo(v: string): string {
  return v === "critical" ? "tt tt-do" : v === "warn" ? "tt tt-vang" : "tt tt-xam";
}

function nhanTrangThai(v: string): string {
  return v === "open" ? "Mở" : v === "in_progress" ? "Đang xử lý" : v === "resolved" ? "Đã đóng" : "Bỏ qua";
}

function diem(v: number | null): string {
  return v === null || v === undefined ? "—" : Number(v).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
}

function ngay(iso: string | null): string {
  return iso ? formatThoiDiem(iso) : "—";
}

async function taiDanhSach(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [s, r, i] = await Promise.all([
      fetchDqSummary(),
      fetchDqRules(boLoc.domain || undefined, "critical"),
      fetchDqIssues({
        domain: boLoc.domain || undefined,
        severity: boLoc.severity || undefined,
        status: boLoc.status || undefined,
        page: 1,
        page_size: 20,
      }),
    ]);
    summary.value = s;
    rules.value = r;
    issues.value = i;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được chất lượng dữ liệu";
  } finally {
    loading.value = false;
  }
}

async function doiTrang(buoc: number): Promise<void> {
  if (!issues.value) return;
  const trang = Math.min(soTrang.value, Math.max(1, issues.value.page + buoc));
  if (trang === issues.value.page) return;
  loading.value = true;
  try {
    issues.value = await fetchDqIssues({
      domain: boLoc.domain || undefined,
      severity: boLoc.severity || undefined,
      status: boLoc.status || undefined,
      page: trang,
      page_size: issues.value.page_size,
    });
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được trang vấn đề";
  } finally {
    loading.value = false;
  }
}

async function dong(v: VanDeDq, status: "resolved" | "ignored"): Promise<void> {
  const note = (ghiChu[v.id] || "").trim();
  if (note.length < 3) {
    thongBao.value = "Nhập ghi chú ít nhất 3 ký tự trước khi đóng hoặc bỏ qua.";
    return;
  }
  dangDong.value = v.id;
  thongBao.value = "";
  try {
    await resolveDqIssue(v.id, status, note);
    thongBao.value = status === "resolved" ? "Đã đóng vấn đề và ghi audit." : "Đã bỏ qua vấn đề và ghi audit.";
    moGhiChu.value = null;
    delete ghiChu[v.id];
    await taiDanhSach();
  } catch (e) {
    thongBao.value = e instanceof Error ? e.message : "Không cập nhật được vấn đề";
  } finally {
    dangDong.value = null;
  }
}

watch(
  () => [boLoc.domain, boLoc.severity, boLoc.status],
  () => void taiDanhSach(),
);

onMounted(taiDanhSach);
</script>

<template>
  <section class="space-y-4" aria-labelledby="tieu-de-dq">
    <div class="mb-2 flex flex-wrap items-end gap-3">
      <div>
        <h1 id="tieu-de-dq" class="tieu-de-trang">Chất lượng dữ liệu</h1>
        <p class="mt-2 max-w-3xl text-[15px] text-phu">
          Điểm theo miền, rule nghiêm trọng đang lỗi và vấn đề cần xử lý — tính từ lần chạy DQ gần nhất.
        </p>
      </div>
      <div class="flex-1"></div>
      <button type="button" class="btn" :disabled="loading" @click="taiDanhSach">
        {{ loading ? "Đang tải…" : "Làm mới" }}
      </button>
    </div>

    <div v-if="loading && !summary" class="grid gap-4 md:grid-cols-4" role="status" aria-busy="true">
      <span class="sr-only">Đang tải chất lượng dữ liệu</span>
      <div v-for="i in 4" :key="i" class="kinh animate-pulse space-y-3 p-4 shadow" aria-hidden="true">
        <div class="h-3 w-2/3 rounded bg-slate-200 dark:bg-slate-700"></div>
        <div class="h-8 w-1/3 rounded bg-slate-200 dark:bg-slate-700"></div>
      </div>
    </div>

    <div v-else-if="error" class="the p-4" role="alert">
      <p class="m-0 text-son">Không tải được chất lượng dữ liệu: {{ error }}</p>
      <button class="btn btn-sm mt-3" @click="taiDanhSach">Thử lại</button>
    </div>

    <template v-else-if="summary">
      <div class="grid gap-4 lg:grid-cols-[320px_1fr]">
        <div class="the p-5">
          <p class="nhan-nho m-0">Điểm tổng</p>
          <p class="mt-2 text-[54px] font-semibold leading-none tracking-[-0.03em]" :class="(summary.overall_score ?? 0) >= 80 ? 'text-xanh' : (summary.overall_score ?? 0) >= 50 ? 'text-vang' : 'text-son'">
            {{ diem(summary.overall_score) }}
          </p>
          <p class="mt-2 mb-0 text-[12.5px] text-phu">
            {{ summary.domains.length }} miền · tính lúc {{ ngay(summary.computed_at) }}
          </p>
          <p class="m-0 mt-1 break-all text-[11px] text-phu">Lần chạy: {{ summary.run_id || "chưa có" }}</p>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <article v-for="d in summary.domains" :key="d.domain" class="the p-4">
            <div class="flex items-baseline justify-between gap-2">
              <b class="text-[13.5px]">{{ tenMien(d.domain) }}</b>
              <span class="text-[20px] font-semibold" :class="(d.score ?? 0) >= 80 ? 'text-xanh' : (d.score ?? 0) >= 50 ? 'text-vang' : 'text-son'">{{ diem(d.score) }}</span>
            </div>
            <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-mat-noi" role="progressbar" :aria-label="`Điểm ${tenMien(d.domain)}`" :aria-valuenow="d.score ?? 0" aria-valuemin="0" aria-valuemax="100">
              <div class="h-full rounded-full" :class="(d.score ?? 0) >= 80 ? 'bg-xanh' : (d.score ?? 0) >= 50 ? 'bg-vang' : 'bg-son'" :style="{ width: `${d.score ?? 0}%` }"></div>
            </div>
            <p class="m-0 mt-2 text-[12px] text-phu">
              {{ d.rules }} rule · {{ d.failed_rules }} lỗi · {{ d.open_issues }} vấn đề mở
            </p>
          </article>
        </div>
      </div>

      <div class="the p-4">
        <div class="flex flex-wrap items-end gap-3">
          <h2 class="m-0 text-[15px] font-semibold">Vấn đề dữ liệu</h2>
          <span class="mo">{{ issues?.total ?? 0 }} vấn đề</span>
          <div class="flex-1"></div>
          <label class="flex items-center gap-2 text-[12.5px] text-phu">
            Miền
            <select v-model="boLoc.domain" class="o w-auto">
              <option value="">Tất cả</option>
              <option v-for="(ten, ma) in TEN_MIEN" :key="ma" :value="ma">{{ ten }}</option>
            </select>
          </label>
          <label class="flex items-center gap-2 text-[12.5px] text-phu">
            Mức độ
            <select v-model="boLoc.severity" class="o w-auto">
              <option value="">Tất cả</option>
              <option value="critical">Nghiêm trọng</option>
              <option value="warn">Cảnh báo</option>
              <option value="info">Thông tin</option>
            </select>
          </label>
          <label class="flex items-center gap-2 text-[12.5px] text-phu">
            Trạng thái
            <select v-model="boLoc.status" class="o w-auto">
              <option value="">Tất cả</option>
              <option value="open">Mở</option>
              <option value="in_progress">Đang xử lý</option>
              <option value="resolved">Đã đóng</option>
              <option value="ignored">Bỏ qua</option>
            </select>
          </label>
        </div>

        <p v-if="thongBao" class="mt-2 mb-0 text-[12.5px]" :class="thongBao.startsWith('Đã') ? 'text-xanh' : 'text-son'" role="status">{{ thongBao }}</p>

        <div class="mt-3 overflow-x-auto">
          <table class="bang w-full text-[12.5px]">
            <thead>
              <tr>
                <th>Mức độ</th>
                <th>Rule</th>
                <th>Miền</th>
                <th>Trường</th>
                <th>Trạng thái</th>
                <th>Thời điểm</th>
                <th v-if="coTheDong" class="text-right">Xử lý</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="v in issues?.items || []" :key="v.id">
                <td><span :class="lopMucDo(v.severity)">{{ nhanMucDo(v.severity) }}</span></td>
                <td class="whitespace-nowrap font-medium">{{ v.rule_code }}</td>
                <td class="whitespace-nowrap">{{ tenMien(v.domain) }}</td>
                <td class="whitespace-nowrap">{{ v.field || "—" }}</td>
                <td class="whitespace-nowrap">{{ nhanTrangThai(v.status) }}</td>
                <td class="whitespace-nowrap text-phu">{{ ngay(v.created_at) }}</td>
                <td v-if="coTheDong" class="text-right">
                  <template v-if="v.status === 'open' || v.status === 'in_progress'">
                    <button type="button" class="btn btn-sm" :disabled="dangDong === v.id" @click="moGhiChu = moGhiChu === v.id ? null : v.id">
                      {{ moGhiChu === v.id ? "Hủy" : "Xử lý" }}
                    </button>
                  </template>
                  <span v-else class="text-phu">—</span>
                </td>
              </tr>
              <tr v-if="!(issues?.items || []).length">
                <td :colspan="coTheDong ? 7 : 6" class="py-6 text-center text-phu">Không có vấn đề khớp bộ lọc.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="issues && moGhiChu" class="mt-3 rounded-[14px] border border-vien-nhat bg-mat-2 p-3" role="region" aria-label="Đóng vấn đề dữ liệu">
          <label class="block">
            <span class="nhan">Ghi chú xử lý (bắt buộc)</span>
            <input v-model="ghiChu[moGhiChu]" class="o w-full" maxlength="1000" placeholder="Ví dụ: đã bổ sung mã định danh địa điểm" />
          </label>
          <div class="mt-2 flex flex-wrap gap-2">
            <button type="button" class="btn btn-sm btn-chinh" :disabled="dangDong === moGhiChu" @click="dong(issues.items.find((x) => x.id === moGhiChu)!, 'resolved')">
              Đóng vấn đề
            </button>
            <button type="button" class="btn btn-sm" :disabled="dangDong === moGhiChu" @click="dong(issues.items.find((x) => x.id === moGhiChu)!, 'ignored')">
              Bỏ qua
            </button>
          </div>
        </div>

        <div v-if="issues && soTrang > 1" class="mt-3 flex items-center justify-between border-t border-vien-nhat pt-3">
          <button type="button" class="btn btn-sm" :disabled="issues.page <= 1 || loading" @click="doiTrang(-1)">Trước</button>
          <span class="mo">Trang {{ issues.page }}/{{ soTrang }}</span>
          <button type="button" class="btn btn-sm" :disabled="issues.page >= soTrang || loading" @click="doiTrang(1)">Sau</button>
        </div>
      </div>

      <div class="the p-4">
        <div class="flex items-center justify-between gap-2">
          <h2 class="m-0 text-[15px] font-semibold">Rule nghiêm trọng đang lỗi</h2>
          <span class="tt tt-do">{{ rules.filter((r) => (r.last_result?.failed || 0) > 0).length }}</span>
        </div>
        <p v-if="!rules.length" class="mt-2 mb-0 text-[13px] text-phu">Chưa có rule nghiêm trọng.</p>
        <table v-else class="bang mt-2 w-full text-[12.5px]">
          <thead><tr><th>Rule</th><th>Miền</th><th>Mô tả</th><th>Lỗi / tổng</th><th>Điểm</th></tr></thead>
          <tbody>
            <tr v-for="r in rules" :key="r.code">
              <td class="whitespace-nowrap font-medium">{{ r.code }}</td>
              <td class="whitespace-nowrap">{{ tenMien(r.domain) }}</td>
              <td class="max-w-[360px]">{{ r.description }}</td>
              <td class="whitespace-nowrap">{{ r.last_result?.failed ?? 0 }} / {{ r.last_result?.total ?? 0 }}</td>
              <td class="whitespace-nowrap"><b :class="(r.last_result?.score ?? 0) >= 80 ? 'text-xanh' : 'text-son'">{{ diem(r.last_result?.score ?? null) }}</b></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

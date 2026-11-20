<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { canViewDashboard, getUser, handleCallbackIfNeeded, login, logout, readRoles } from "./auth";
import { ApiError, apiDownload, apiGet, apiPost, luuBlob } from "./api";
import { formatThoiDiem, nhanChiSo } from "./utils/metrics";
import { renderMarkdown, tenNguon } from "./utils/markdown";
import { useTheme } from "./composables/useTheme";
import KpiCard from "./components/KpiCard.vue";
import DonutChart from "./components/DonutChart.vue";
import LineChart from "./components/LineChart.vue";
import BarChart from "./components/BarChart.vue";
import AuditorPanel from "./components/AuditorPanel.vue";
import TenantAdminPanel from "./components/TenantAdminPanel.vue";
import LogoMark from "./components/LogoMark.vue";

const { cheDo } = useTheme();

function doiGiaoDien() {
  cheDo.value = cheDo.value === "toi" ? "sang" : "toi";
}

interface MetricItem {
  code: string;
  name?: string;
  unit?: string;
  value: number | null;
  error?: string;
}
interface MetricsResponse {
  tenant: string;
  computed_at: string;
  metrics: MetricItem[];
}
interface Lineage {
  metric_code: string;
  bang_nguon: string[];
  dieu_kien_loc: string;
  job: string;
  lineage_events: unknown[];
}
interface Citation {
  so: number;
  nguon: string;
  chunk_id: string;
  trich: string;
}
interface AskResponse {
  answer: string;
  citations: Citation[];
  mode: string;
}
interface BreakdownResponse {
  items: { trang_thai: string; so_luong: number }[];
}
interface TrendResponse {
  items: { thang: string; so_ho_so: number; da_cap: number; qua_han: number }[];
}
interface WorkloadResponse {
  items: { ho_ten: string; so_ho_so_duoc_giao: number; dang_xu_ly: number }[];
}
interface HoSoTomTat {
  id: string;
  ma_ho_so: string;
  ho_ten: string;
  dia_chi_cong_trinh: string;
  trang_thai: string;
  buoc: string;
  han_tong_at?: string;
  han_buoc_at?: string;
}
interface DanhSachHoSo {
  items: HoSoTomTat[];
}

const KEY_FILTER = "dxos-bdh-filter";
const APP_CODE = "cap-phep";
type Tab = "chi-so" | "tro-ly" | "kiem-toan" | "quan-tri";

type AuthState = "dang_kiem_tra" | "chua_dang_nhap" | "khong_quyen" | "ok";
const auth = ref<AuthState>("dang_kiem_tra");
const tab = ref<Tab>("chi-so");
const vaiTro = ref<string[]>([]);
const laKiemToan = computed(() =>
  vaiTro.value.some((r) => ["dx:auditor", "dx:tenant-admin", "dx:platform-admin"].includes(r)),
);
const laQuanTri = computed(() =>
  vaiTro.value.some((r) => ["dx:tenant-admin", "dx:platform-admin"].includes(r)),
);

// Bộ lọc giữ nguyên khi chuyển tab và khi tải lại trang (sessionStorage)
const filter = reactive(loadFilter());
function loadFilter(): { thang: string; diaBan: string } {
  const macDinh = new Date().toISOString().slice(0, 7);
  try {
    const raw = sessionStorage.getItem(KEY_FILTER);
    if (raw) {
      const da = JSON.parse(raw);
      return { thang: da.thang || macDinh, diaBan: da.diaBan || "" };
    }
  } catch {
    /* bỏ qua: dùng giá trị mặc định */
  }
  return { thang: macDinh, diaBan: "" };
}
watch(filter, (v) => sessionStorage.setItem(KEY_FILTER, JSON.stringify(v)), {
  deep: true,
});

// Chỉ số
const loading = ref(false);
const loadError = ref("");
const data = ref<MetricsResponse | null>(null);

async function loadMetrics(): Promise<void> {
  loading.value = true;
  loadError.value = "";
  const q = new URLSearchParams();
  if (filter.thang) q.set("thang", filter.thang);
  if (filter.diaBan) q.set("dia_ban", filter.diaBan);
  try {
    data.value = await apiGet<MetricsResponse>(
      `/metrics${q.toString() ? `?${q}` : ""}`,
    );
  } catch (e) {
    data.value = null;
    loadError.value = e instanceof Error ? e.message : "Lỗi không xác định";
  } finally {
    loading.value = false;
  }
}

const hasAnyValue = computed(() =>
  (data.value?.metrics ?? []).some((m) => m.value !== null),
);

// Dashboard 8 KPI + 3 biểu đồ + 2 danh sách (B-UX-01)
const breakdown = ref<BreakdownResponse | null>(null);
const trendData = ref<TrendResponse | null>(null);
const workload = ref<WorkloadResponse | null>(null);
const overdue = ref<DanhSachHoSo | null>(null);
const todayTasks = ref<DanhSachHoSo | null>(null);
const dashboardLoading = ref(false);
const dashboardError = ref("");

const KPI_ICON: Record<string, string> = {
  ho_so_moi: "📄",
  ho_so_dang_xu_ly: "⏳",
  ho_so_qua_han: "⚠️",
  thoi_gian_xu_ly_tb: "⏱️",
  truy_cap_tu_choi: "🚫",
  phieu_kiem_tra: "🔎",
  canh_bao_cong_truong: "🔔",
  vi_pham: "⚖️",
};
const KPI_TONE: Record<string, "brand" | "success" | "warning" | "danger" | "info" | "gold" | "neutral"> = {
  ho_so_moi: "brand",
  ho_so_dang_xu_ly: "info",
  ho_so_qua_han: "danger",
  thoi_gian_xu_ly_tb: "gold",
  truy_cap_tu_choi: "warning",
  phieu_kiem_tra: "success",
  canh_bao_cong_truong: "warning",
  vi_pham: "danger",
};
const TRANG_THAI: Record<string, string> = {
  MOI_TAO: "Mới tạo",
  DA_NOP: "Đã nộp",
  TIEP_NHAN: "Tiếp nhận",
  CAN_BO_SUNG: "Cần bổ sung",
  DUOC_PHAN_CONG: "Được phân công",
  DANG_THAM_DINH: "Đang thẩm định",
  YEU_CAU_BO_SUNG: "Yêu cầu bổ sung",
  CHO_DUYET: "Chờ duyệt",
  CHO_PHE_DUYET: "Chờ phê duyệt",
  CHO_KY: "Chờ ký",
  DA_CAP: "Đã cấp",
  DA_CAP_PHEP: "Đã cấp phép",
  TU_CHOI: "Từ chối",
};
function nhanTrangThai(v: string): string {
  return TRANG_THAI[v] || v;
}
const trendSeries = computed(() => {
  const items = trendData.value?.items ?? [];
  return {
    so_ho_so: items.map((x) => Number(x.so_ho_so) || 0),
    da_cap: items.map((x) => Number(x.da_cap) || 0),
    qua_han: items.map((x) => Number(x.qua_han) || 0),
  };
});
function seriesCho(code: string): number[] {
  const t = trendSeries.value;
  if (code === "ho_so_qua_han") return t.qua_han;
  if (code === "ho_so_dang_xu_ly") return t.so_ho_so.map((v, i) => Math.max(0, v - (t.da_cap[i] || 0)));
  return t.so_ho_so;
}
function xuHuong(series: number[]): number | null {
  if (series.length < 2) return null;
  const truoc = series[series.length - 2];
  const nay = series[series.length - 1];
  if (!truoc) return null;
  return ((nay - truoc) / truoc) * 100;
}
const kpiCards = computed(() =>
  (data.value?.metrics ?? []).slice(0, 8).map((m) => {
    const series = seriesCho(m.code);
    return {
      ...m,
      label: nhanChiSo(m.code),
      icon: KPI_ICON[m.code] || "•",
      tone: KPI_TONE[m.code] || "brand",
      series,
      trend: xuHuong(series),
    };
  }),
);
const statusItems = computed(() =>
  (breakdown.value?.items ?? []).map((x, i) => ({
    label: nhanTrangThai(x.trang_thai),
    value: Number(x.so_luong) || 0,
    color: ["#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2"][i % 6],
  })),
);
const trendLabels = computed(() => (trendData.value?.items ?? []).map((x) => x.thang.slice(2)));
const trendLines = computed(() => [
  { label: "Hồ sơ mới", values: trendSeries.value.so_ho_so, color: "#2563eb" },
  { label: "Đã cấp", values: trendSeries.value.da_cap, color: "#059669" },
  { label: "Quá hạn", values: trendSeries.value.qua_han, color: "#dc2626" },
]);
const workloadItems = computed(() =>
  (workload.value?.items ?? []).slice(0, 8).map((x) => ({ label: x.ho_ten, value: Number(x.so_ho_so_duoc_giao) || 0 })),
);

async function loadDashboard(): Promise<void> {
  dashboardLoading.value = true;
  dashboardError.value = "";
  const thang = filter.thang || "";
  try {
    const [b, t, w, o, h] = await Promise.all([
      apiGet<BreakdownResponse>(`/metrics/status-breakdown${thang ? `?month=${encodeURIComponent(thang)}` : ""}`),
      apiGet<TrendResponse>("/metrics/trend?months=6"),
      apiGet<WorkloadResponse>("/metrics/workload"),
      apiGet<DanhSachHoSo>("/metrics/overdue"),
      apiGet<DanhSachHoSo>("/metrics/today-tasks"),
    ]);
    breakdown.value = b;
    trendData.value = t;
    workload.value = w;
    overdue.value = o;
    todayTasks.value = h;
  } catch (e) {
    dashboardError.value = e instanceof Error ? e.message : "Lỗi không xác định";
  } finally {
    dashboardLoading.value = false;
  }
}

async function taiTatCa(): Promise<void> {
  await Promise.all([loadMetrics(), loadDashboard()]);
}

const dangXuatTep = ref(false);
async function xuatPdf(): Promise<void> {
  dangXuatTep.value = true;
  try {
    luuBlob(await apiDownload("/export/metrics.pdf"), "bao-cao-tong-hop.pdf");
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : "Không xuất được PDF";
  } finally {
    dangXuatTep.value = false;
  }
}
async function xuatExcel(): Promise<void> {
  dangXuatTep.value = true;
  try {
    luuBlob(await apiDownload("/export/dossiers.xlsx"), `ho-so-${new Date().toISOString().slice(0, 10)}.xlsx`);
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : "Không xuất được Excel";
  } finally {
    dangXuatTep.value = false;
  }
}

// Phả hệ
const selected = ref<string | null>(null);
const lineage = ref<Lineage | null>(null);
const lineageLoading = ref(false);
const lineageError = ref("");

async function openLineage(code: string): Promise<void> {
  selected.value = code;
  lineage.value = null;
  lineageError.value = "";
  lineageLoading.value = true;
  try {
    lineage.value = await apiGet<Lineage>(
      `/metrics/${encodeURIComponent(code)}/lineage`,
    );
  } catch (e) {
    lineageError.value = e instanceof Error ? e.message : "Lỗi không xác định";
  } finally {
    lineageLoading.value = false;
  }
}

// Trợ lý hỏi đáp
const question = ref("");
const asking = ref(false);
const askError = ref("");
const answer = ref<AskResponse | null>(null);

async function ask(): Promise<void> {
  const q = question.value.trim();
  if (q.length < 3) {
    askError.value = "Nhập câu hỏi ít nhất 3 ký tự";
    return;
  }
  asking.value = true;
  askError.value = "";
  answer.value = null;
  try {
    const res = await apiPost<AskResponse>("/assistant/ask", {
      question: q,
      app: APP_CODE,
    });
    res.citations = (res.citations || []).map((c: any, i: number) =>
      typeof c === "string"
        ? { so: i + 1, nguon: c, chunk_id: `src-${i}`, trich: "" }
        : c,
    );
    answer.value = res;
  } catch (e) {
    askError.value = e instanceof Error ? e.message : "Lỗi không xác định";
  } finally {
    asking.value = false;
  }
}

// Chỉ hiển thị câu trả lời khi có trích dẫn nguồn
const answerText = computed(() => {
  const a = answer.value;
  if (!a) return "";
  if (!a.citations || a.citations.length === 0)
    return "Không tìm thấy căn cứ trong tri thức của địa bàn bạn.";
  return a.answer;
});
const answerHtml = computed(() => renderMarkdown(answerText.value));
const daChep = ref(false);
const SUGGESTED = [
  "Hồ sơ nhà ở riêng lẻ cần giấy tờ gì?",
  "Thời hạn giải quyết cấp phép là bao lâu?",
  "Khi nào phải xin điều chỉnh giấy phép?",
];
async function copyAnswer(): Promise<void> {
  if (!answerText.value) return;
  try {
    await navigator.clipboard.writeText(answerText.value);
    daChep.value = true;
    setTimeout(() => (daChep.value = false), 2000);
  } catch {
    askError.value = "Trình duyệt không cho chép tự động.";
  }
}
function hoiNhanh(q: string): void {
  question.value = q;
  void ask();
}

onMounted(async () => {
  await handleCallbackIfNeeded();
  const user = await getUser();
  if (!user || user.expired) {
    auth.value = "chua_dang_nhap";
    return;
  }
  vaiTro.value = readRoles(user.access_token);
  if (!canViewDashboard(vaiTro.value)) {
    auth.value = "khong_quyen";
    return;
  }
  auth.value = "ok";
  await taiTatCa();
});

// Đổi bộ lọc thì tải lại số liệu, không tải lại trang
watch(
  () => [filter.thang, filter.diaBan],
  () => {
    if (auth.value === "ok") void taiTatCa();
  },
);

function fmtDate(iso?: string): string {
  return iso ? formatThoiDiem(iso) : "—";
}
</script>

<template>
  <a href="#bdh-main" class="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded focus:bg-white focus:px-4 focus:py-2 focus:text-slate-900">Bỏ qua điều hướng</a>
  <div v-if="auth === 'dang_kiem_tra'" class="chu-phu">
    Đang kiểm tra đăng nhập...
  </div>

  <div v-else-if="auth === 'chua_dang_nhap'" class="login-shell">
    <button class="absolute right-4 top-4 rounded border border-slate-300 px-3 py-2 text-sm" :aria-label="cheDo === 'toi' ? 'Chuyển nền sáng' : 'Chuyển nền tối'" @click="doiGiaoDien()">
      {{ cheDo === "toi" ? "Nền sáng" : "Nền tối" }}
    </button>
    <main class="brand-hero kinh" aria-labelledby="bdh-title">
      <div class="flex items-center gap-3">
        <LogoMark :size="48" />
        <div>
          <p class="m-0 text-xs chu-phu">DX-OS Open-Core</p>
          <h1 id="bdh-title" class="m-0 text-2xl font-semibold">Bảng điều hành lãnh đạo</h1>
        </div>
      </div>
      <p class="mt-3 max-w-xl text-sm chu-phu">
        Theo dõi hồ sơ, tải việc, cảnh báo quá hạn và kiểm toán chuỗi dữ liệu của địa bàn.
      </p>
      <div class="mt-5 flex flex-wrap gap-2">
        <button class="min-h-[44px] rounded bg-slate-800 px-4 py-2 text-white" @click="login()">Đăng nhập</button>
        <a class="inline-flex min-h-[44px] items-center rounded border border-slate-300 px-4 py-2 text-sm" href="/">Về trang cấp phép</a>
        <a class="inline-flex min-h-[44px] items-center rounded border border-slate-300 px-4 py-2 text-sm" href="/kiem-tra/" target="_blank" rel="noopener">Tra cứu công khai</a>
      </div>
      <p class="mt-6 mb-0 text-xs chu-phu">DX-OS Open-Core v1.0.0 · Mã nguồn mở AGPL-3.0</p>
    </main>
  </div>

  <div
    v-else-if="auth === 'khong_quyen'"
    class="rounded-lg kinh p-6 shadow"
  >
    <h1 class="text-xl font-semibold">Không có quyền</h1>
    <p class="mt-2 chu-phu">
      Tài khoản không có vai trò lãnh đạo. Bảng điều hành chỉ đọc chỉ số.
    </p>
    <button
      class="mt-4 rounded bg-slate-800 px-4 py-2 text-white"
      @click="logout()"
    >
      Đăng xuất
    </button>
  </div>

  <main v-else id="bdh-main" class="space-y-4">
    <header class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-xl font-semibold">Bảng điều hành lãnh đạo</h1>
      <div class="flex flex-wrap items-center gap-2">
        <button class="min-h-[44px] rounded border px-3 py-1 text-sm" :disabled="dangXuatTep" @click="xuatExcel">Xuất Excel</button>
        <button class="min-h-[44px] rounded border px-3 py-1 text-sm" :disabled="dangXuatTep" @click="xuatPdf">Xuất PDF</button>
        <button class="min-h-[44px] text-sm chu-phu underline" @click="doiGiaoDien()">
          {{ cheDo === "toi" ? "Giao diện sáng" : "Giao diện tối" }}
        </button>
        <button class="min-h-[44px] text-sm chu-phu underline" @click="logout()">Đăng xuất</button>
      </div>
    </header>

    <nav class="flex gap-2 border-b">
      <button
        class="px-3 py-2 text-sm"
        :class="
          tab === 'chi-so'
            ? 'border-b-2 border-slate-800 font-semibold'
            : 'chu-phu'
        "
        @click="tab = 'chi-so'"
      >
        Chỉ số
      </button>
      <button
        class="px-3 py-2 text-sm"
        :class="
          tab === 'tro-ly'
            ? 'border-b-2 border-slate-800 font-semibold'
            : 'chu-phu'
        "
        @click="tab = 'tro-ly'"
      >
        Trợ lý
      </button>
      <button
        v-if="laKiemToan"
        class="px-3 py-2 text-sm"
        :class="
          tab === 'kiem-toan'
            ? 'border-b-2 border-slate-800 font-semibold'
            : 'chu-phu'
        "
        @click="tab = 'kiem-toan'"
      >
        Kiểm toán
      </button>
      <button
        v-if="laQuanTri"
        class="px-3 py-2 text-sm"
        :class="
          tab === 'quan-tri'
            ? 'border-b-2 border-slate-800 font-semibold'
            : 'chu-phu'
        "
        @click="tab = 'quan-tri'"
      >
        Quản trị
      </button>
    </nav>

    <!-- Tab Chỉ số: dùng v-show để giữ trạng thái khi chuyển tab -->
    <section v-show="tab === 'chi-so'" class="space-y-4">
      <div
        class="flex flex-wrap items-end gap-4 rounded-lg kinh p-4 shadow"
      >
        <label class="text-sm">
          Tháng
          <input
            v-model="filter.thang"
            type="month"
            class="ml-2 rounded border px-2 py-1"
          />
        </label>
      </div>

      <p v-if="loading" class="chu-phu">Đang tải chỉ số...</p>

      <div v-else-if="loadError" class="rounded-lg kinh p-4 shadow">
        <p class="text-red-700">Không tải được số liệu: {{ loadError }}</p>
        <button
          class="mt-2 rounded bg-slate-800 px-3 py-1 text-white"
          @click="loadMetrics()"
        >
          Thử lại
        </button>
      </div>

      <p
        v-else-if="!data || !data.metrics.length || !hasAnyValue"
        class="rounded-lg kinh p-4 chu-phu shadow"
      >
        Chưa có số liệu cho bộ lọc này.
      </p>

      <template v-else>
        <p class="text-sm chu-phu">
          Thời điểm tính: {{ fmtDate(data.computed_at) }}
        </p>

        <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
          <KpiCard
            v-for="m in kpiCards"
            :key="m.code"
            :label="m.label"
            :value="m.value"
            :unit="m.unit"
            :icon="m.icon"
            :tone="m.tone"
            :trend="m.trend"
            :series="m.series"
            :hint="m.error ? 'Không có số liệu cho kỳ này' : 'Bấm để xem phả hệ chỉ số'"
            @select="openLineage(m.code)"
          />
        </div>

        <div class="grid gap-4 lg:grid-cols-2">
          <DonutChart title="Hồ sơ theo trạng thái" :items="statusItems" />
          <LineChart title="Hồ sơ theo tháng (6 tháng)" :labels="trendLabels" :series="trendLines" />
        </div>
        <BarChart title="Tải việc theo cán bộ" :items="workloadItems" />

        <p v-if="dashboardLoading" class="chu-phu">Đang tải biểu đồ và danh sách…</p>
        <p v-else-if="dashboardError" class="text-amber-700">Không tải được dữ liệu biểu đồ: {{ dashboardError }}</p>

        <div class="grid gap-4 lg:grid-cols-2">
          <div class="rounded-lg kinh p-4 shadow">
            <div class="flex items-center justify-between gap-2">
              <h2 class="text-sm font-semibold chu-phu">Hồ sơ quá hạn</h2>
              <span class="rounded-full bg-rose-100 px-2 text-xs text-rose-800 dark:bg-rose-950 dark:text-rose-200">{{ overdue?.items?.length || 0 }}</span>
            </div>
            <p v-if="!overdue?.items?.length" class="mt-2 text-sm chu-phu">Không có hồ sơ quá hạn.</p>
            <ul v-else class="mt-2 list-none space-y-2 p-0 text-sm">
              <li v-for="h in overdue.items.slice(0, 5)" :key="h.id" class="border-b border-slate-200 pb-2 last:border-0 dark:border-slate-700">
                <a :href="'/?tab=ho-so'" target="_blank" rel="noopener" class="font-medium underline">{{ h.ma_ho_so }}</a>
                <span class="block chu-phu">{{ h.ho_ten }} · {{ h.dia_chi_cong_trinh }}</span>
                <span class="block text-xs text-rose-700 dark:text-rose-300">Hạn: {{ fmtDate(h.han_tong_at) }} · {{ nhanTrangThai(h.trang_thai) }}</span>
              </li>
            </ul>
          </div>

          <div class="rounded-lg kinh p-4 shadow">
            <div class="flex items-center justify-between gap-2">
              <h2 class="text-sm font-semibold chu-phu">Việc cần xử lý hôm nay</h2>
              <span class="rounded-full bg-amber-100 px-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200">{{ todayTasks?.items?.length || 0 }}</span>
            </div>
            <p v-if="!todayTasks?.items?.length" class="mt-2 text-sm chu-phu">Không có việc đến hạn hôm nay.</p>
            <ul v-else class="mt-2 list-none space-y-2 p-0 text-sm">
              <li v-for="h in todayTasks.items.slice(0, 5)" :key="h.id" class="border-b border-slate-200 pb-2 last:border-0 dark:border-slate-700">
                <a :href="'/?tab=ban-lam-viec'" target="_blank" rel="noopener" class="font-medium underline">{{ h.ma_ho_so }}</a>
                <span class="block chu-phu">{{ h.ho_ten }} · {{ h.buoc || "Đang xử lý" }}</span>
                <span class="block text-xs text-amber-700 dark:text-amber-300">Hạn bước: {{ fmtDate(h.han_buoc_at || h.han_tong_at) }}</span>
              </li>
            </ul>
          </div>
        </div>

        <div v-if="selected" class="rounded-lg kinh p-4 shadow">
          <div class="flex items-center justify-between">
            <h2 class="font-semibold">Phả hệ: {{ nhanChiSo(selected) }}</h2>
            <button
              class="text-sm chu-phu underline"
              @click="selected = null"
            >
              Đóng
            </button>
          </div>
          <p v-if="lineageLoading" class="mt-2 chu-phu">
            Đang tải phả hệ...
          </p>
          <p v-else-if="lineageError" class="mt-2 text-red-700">
            {{ lineageError }}
          </p>
          <div v-else-if="lineage" class="mt-2 space-y-1 text-sm">
            <p>
              <span class="chu-phu">Bảng nguồn:</span>
              {{ lineage.bang_nguon.join(", ") || "—" }}
            </p>
            <p>
              <span class="chu-phu">Điều kiện lọc:</span>
              {{ lineage.dieu_kien_loc || "—" }}
            </p>
            <p>
              <span class="chu-phu">Luồng dữ liệu:</span>
              {{ lineage.job }}
            </p>
            <p>
              <span class="chu-phu">Thời điểm tính:</span>
              {{ fmtDate(data.computed_at) }}
            </p>
            <p class="chu-phu">
              Sự kiện lineage: {{ lineage.lineage_events.length }}
            </p>
          </div>
        </div>
      </template>
    </section>

    <!-- Tab Trợ lý -->
    <section v-show="tab === 'tro-ly'" class="space-y-4">
      <div class="rounded-lg kinh p-4 shadow">
        <h2 class="text-sm font-semibold">Trợ lý pháp lý</h2>
        <p class="mt-1 text-sm chu-phu">Hỏi về quy định cấp phép xây dựng. Câu trả lời chỉ dùng khi có trích dẫn nguồn.</p>
        <div class="mt-2 flex flex-wrap gap-2">
          <button
            v-for="q in SUGGESTED"
            :key="q"
            type="button"
            class="rounded-full border border-slate-300 px-3 py-1 text-xs hover:bg-slate-100 dark:border-slate-600 dark:hover:bg-slate-800"
            @click="hoiNhanh(q)"
          >
            {{ q }}
          </button>
        </div>
      </div>

      <form class="flex gap-2" @submit.prevent="ask()">
        <input
          v-model="question"
          type="text"
          maxlength="500"
          placeholder="Nhập câu hỏi về quy định cấp phép"
          class="flex-1 rounded border px-3 py-2"
        />
        <button
          type="submit"
          :disabled="asking"
          class="rounded bg-slate-800 px-4 py-2 text-white disabled:opacity-50"
        >
          {{ asking ? "Đang hỏi..." : "Hỏi" }}
        </button>
      </form>
      <p v-if="askError" class="text-red-700">{{ askError }}</p>

      <div v-if="asking" class="rounded-lg kinh p-4 shadow" aria-live="polite">
        <p class="text-sm chu-phu">Đang tra cứu tri thức…</p>
        <div class="mt-3 animate-pulse space-y-2">
          <div class="h-3 w-3/4 rounded bg-slate-200 dark:bg-slate-700"></div>
          <div class="h-3 w-full rounded bg-slate-200 dark:bg-slate-700"></div>
          <div class="h-3 w-2/3 rounded bg-slate-200 dark:bg-slate-700"></div>
        </div>
      </div>

      <div v-else-if="answer" class="rounded-lg kinh p-4 shadow" aria-live="polite">
        <div class="flex items-center justify-between gap-2">
          <h2 class="text-sm font-semibold">Câu trả lời</h2>
          <button type="button" class="text-xs underline chu-phu" @click="copyAnswer()">
            {{ daChep ? "Đã chép" : "Chép câu trả lời" }}
          </button>
        </div>
        <div class="markdown mt-2" v-html="answerHtml"></div>
        <div v-if="answer.citations.length" class="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span class="chu-phu">Căn cứ:</span>
          <span
            v-for="c in answer.citations"
            :key="c.chunk_id"
            class="rounded-full border border-sky-300 bg-sky-50 px-2 py-1 text-sky-900 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-100"
            :title="c.trich"
          >
            [{{ c.so }}] {{ tenNguon(c.nguon) }}
          </span>
        </div>
      </div>

      <div v-else class="rounded-lg kinh p-4 text-sm chu-phu shadow">
        Chào bạn. Hãy chọn một câu hỏi gợi ý hoặc nhập câu hỏi về cấp phép xây dựng.
      </div>
    </section>

    <!-- Tab Kiểm toán (chỉ dx:auditor / quản trị) -->
    <section v-if="laKiemToan" v-show="tab === 'kiem-toan'">
      <AuditorPanel />
    </section>

    <!-- Tab Quản trị địa bàn (dx:platform-admin / dx:tenant-admin) -->
    <section v-if="laQuanTri" v-show="tab === 'quan-tri'">
      <TenantAdminPanel :vai-tro="vaiTro" />
    </section>
  </main>
</template>

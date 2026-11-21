<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { canViewDashboard, getUser, handleCallbackIfNeeded, login, logout, readRoles, readTenant } from "./auth";
import { ApiError, apiDownload, apiGet, apiPost, luuBlob } from "./api";
import { donViHienThi, formatThoiDiem, nhanChiSo, sapXepChiSo } from "./utils/metrics";
import { renderMarkdown, tenNguon } from "./utils/markdown";
import { useTheme } from "./composables/useTheme";
import KpiCard from "./components/KpiCard.vue";
import DonutChart from "./components/DonutChart.vue";
import LineChart from "./components/LineChart.vue";
import BarChart from "./components/BarChart.vue";
import AuditorPanel from "./components/AuditorPanel.vue";
import TenantAdminPanel from "./components/TenantAdminPanel.vue";
import DsarPanel from "./components/DsarPanel.vue";
import AutomationMetricsPanel from "./components/automation/AutomationMetricsPanel.vue";
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
  lineage_events: any[];
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
interface PlanningFailResponse {
  items: { ma_zone: string; ten: string; so_lan_fail: number }[];
}
interface AcceptanceProgressResponse {
  items: { loai_moc: string; ket_qua: string; so_luong: number }[];
}
interface OnTimeResponse {
  items: { thang: string; da_cap: number; dung_han: number; ty_le: number | null }[];
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
type Tab = "chi-so" | "hieu-qua" | "tro-ly" | "du-lieu-ca-nhan" | "kiem-toan" | "quan-tri";

type AuthState = "dang_kiem_tra" | "chua_dang_nhap" | "khong_quyen" | "ok";
const auth = ref<AuthState>("dang_kiem_tra");
const tab = ref<Tab>("chi-so");
const vaiTro = ref<string[]>([]);
const tenNguoiDung = ref("");
const tenant = ref("");
const laQuanTriNenTang = computed(() => vaiTro.value.includes("dx:platform-admin"));
const danhSachDiaBan = ref<{ tenant: string; ten: string }[]>([]);
/** Phường đang xem: quản trị nền tảng (tenant global) chọn phường, vai khác xem phường của mình. */
const diaBanXem = computed(() => (laQuanTriNenTang.value && filter.diaBan ? filter.diaBan : tenant.value));
const donVi = computed(() => {
  const t = diaBanXem.value;
  const daBiet = danhSachDiaBan.value.find((x) => x.tenant === t);
  if (daBiet?.ten) return daBiet.ten;
  const m = /^(phuong|xa)-(.+)$/.exec(t || "");
  if (m) return `UBND ${m[1] === "phuong" ? "Phường" : "Xã"} ${m[2].toUpperCase()}`;
  if (t === "global") return "toàn hệ thống (chưa chọn phường)";
  return t || "Hệ thống cấp phép";
});
/** Thêm `tenant=` vào đường dẫn khi quản trị nền tảng xem một phường. */
function theoDiaBan(duongDan: string): string {
  if (!laQuanTriNenTang.value || !filter.diaBan) return duongDan;
  return `${duongDan}${duongDan.includes("?") ? "&" : "?"}tenant=${encodeURIComponent(filter.diaBan)}`;
}
async function taiDiaBan(): Promise<void> {
  if (!laQuanTriNenTang.value) return;
  try {
    const res = await apiGet<{ items: { tenant: string; ten: string; active: boolean }[] }>("/admin/tenants");
    danhSachDiaBan.value = res.items.filter((x) => x.tenant !== "global" && x.active !== false);
    if (!filter.diaBan || !danhSachDiaBan.value.some((x) => x.tenant === filter.diaBan)) {
      filter.diaBan = danhSachDiaBan.value[0]?.tenant || "";
    }
  } catch {
    danhSachDiaBan.value = [];
  }
}
const vai = computed(() => {
  if (vaiTro.value.includes("app:cap-phep:lanh-dao")) return "Lãnh đạo phường";
  if (vaiTro.value.includes("dx:auditor")) return "Kiểm toán viên";
  if (vaiTro.value.includes("dx:platform-admin")) return "Quản trị nền tảng";
  if (vaiTro.value.includes("dx:tenant-admin")) return "Quản trị địa bàn";
  return "Tài khoản đã xác thực";
});
const laKiemToan = computed(() =>
  vaiTro.value.some((r) => ["dx:auditor", "dx:tenant-admin", "dx:platform-admin"].includes(r)),
);
const laQuanTri = computed(() =>
  vaiTro.value.some((r) => ["dx:tenant-admin", "dx:platform-admin"].includes(r)),
);
const laDsar = computed(() =>
  vaiTro.value.some((r) =>
    ["dx:dpo", "dx:tenant-admin", "dx:platform-admin", "app:cap-phep:lanh-dao"].includes(r),
  ),
);
const laHieuQua = computed(() =>
  vaiTro.value.some((r) =>
    ["app:cap-phep:lanh-dao", "dx:auditor", "dx:tenant-admin", "dx:platform-admin"].includes(r),
  ),
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
  try {
    data.value = await apiGet<MetricsResponse>(theoDiaBan("/metrics"));
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
const planningFail = ref<PlanningFailResponse | null>(null);
const acceptanceProgress = ref<AcceptanceProgressResponse | null>(null);
const onTime = ref<OnTimeResponse | null>(null);
const dashboardLoading = ref(false);
const dashboardError = ref("");

const KPI_TONE: Record<string, "brand" | "success" | "warning" | "danger" | "info" | "gold" | "neutral"> = {
  ho_so_moi: "brand",
  ho_so_dang_xu_ly: "info",
  ho_so_qua_han: "danger",
  thoi_gian_xu_ly_tb: "gold",
  truy_cap_tu_choi: "warning",
  phieu_kiem_tra: "success",
  canh_bao_cong_truong: "warning",
  vi_pham: "danger",
  ho_so_fail_quy_hoach: "danger",
  ho_so_dang_nghiem_thu: "info",
  ty_le_dung_han: "success",
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
const BUOC: Record<string, string> = {
  tiep_nhan: "Tiếp nhận",
  phan_cong: "Phân công",
  tham_dinh: "Thẩm định",
  phe_duyet: "Phê duyệt",
  hoan_thanh: "Hoàn thành",
};
function nhanBuoc(v?: string | null): string {
  return (v && BUOC[v]) || v || "Đang xử lý";
}
/** Hồ sơ quá hạn vì hạn tổng hay vì hạn của bước hiện tại: in đúng mốc đã bị lỡ. */
function hanBiLo(h: { han_tong_at?: string | null; han_buoc_at?: string | null }): string {
  const now = Date.now();
  if (h.han_tong_at && new Date(h.han_tong_at).getTime() < now) return `Quá hạn giải quyết: ${fmtDate(h.han_tong_at)}`;
  if (h.han_buoc_at) return `Quá hạn bước: ${fmtDate(h.han_buoc_at)}`;
  return `Hạn giải quyết: ${fmtDate(h.han_tong_at || undefined)}`;
}
function daQua(iso?: string | null): boolean {
  return !!iso && new Date(iso).getTime() < Date.now();
}
const trendSeries = computed(() => {
  const items = trendData.value?.items ?? [];
  return {
    so_ho_so: items.map((x) => Number(x.so_ho_so) || 0),
    da_cap: items.map((x) => Number(x.da_cap) || 0),
    qua_han: items.map((x) => Number(x.qua_han) || 0),
  };
});
function seriesCho(code: string): number[] | null {
  const t = trendSeries.value;
  if (code === "ho_so_moi") return t.so_ho_so;
  if (code === "ho_so_qua_han") return t.qua_han;
  if (code === "ho_so_dang_xu_ly") return t.so_ho_so.map((v, i) => Math.max(0, v - (t.da_cap[i] || 0)));
  // Các chỉ số không suy ra từ chuỗi tháng thì không hiển thị xu hướng giả.
  return null;
}
function xuHuong(series: number[]): number | null {
  if (series.length < 2) return null;
  const truoc = series[series.length - 2];
  const nay = series[series.length - 1];
  // Tránh % nhảy vọt vô nghĩa khi tháng trước chỉ có 1-2 hồ sơ
  // hoặc khi mức thay đổi quá lớn (dữ liệu demo không đủ ổn định).
  if (!truoc || truoc < 5) return null;
  const pct = ((nay - truoc) / truoc) * 100;
  return Math.abs(pct) > 500 ? null : pct;
}
const kpiCards = computed(() =>
  sapXepChiSo(data.value?.metrics ?? []).map((m: any) => {
    const series = seriesCho(m.code);
    return {
      ...m,
      label: nhanChiSo(m.code, m.name),
      unit: donViHienThi(m.unit),
      icon: m.code,
      tone: KPI_TONE[m.code] || "brand",
      series: series || [],
      trend: series ? xuHuong(series) : null,
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
const trendLabels = computed(() => (trendData.value?.items ?? []).map((x) => `${x.thang.slice(5, 7)}/${x.thang.slice(0, 4)}`));
const trendLines = computed(() => [
  { label: "Hồ sơ mới", values: trendSeries.value.so_ho_so, color: "#2563eb" },
  { label: "Đã cấp", values: trendSeries.value.da_cap, color: "#059669" },
  { label: "Quá hạn", values: trendSeries.value.qua_han, color: "#dc2626" },
]);
const workloadItems = computed(() =>
  (workload.value?.items ?? []).slice(0, 8).map((x) => ({ label: x.ho_ten, value: Number(x.so_ho_so_duoc_giao) || 0 })),
);

const acceptanceRows = computed(() => {
  const map = new Map<string, { dat: number; khong_dat: number; khac: number }>();
  for (const row of acceptanceProgress.value?.items ?? []) {
    const item = map.get(row.loai_moc) || { dat: 0, khong_dat: 0, khac: 0 };
    if (row.ket_qua === "dat") item.dat += Number(row.so_luong) || 0;
    else if (row.ket_qua === "khong_dat") item.khong_dat += Number(row.so_luong) || 0;
    else item.khac += Number(row.so_luong) || 0;
    map.set(row.loai_moc, item);
  }
  return Array.from(map.entries()).map(([loai, value]) => ({ loai, ...value }));
});
const onTimeRecent = computed(() => (onTime.value?.items ?? []).slice(-6).reverse());
function tenMoc(value: string): string {
  return {
    mong: "Móng",
    ket_cau: "Kết cấu",
    hoan_thien: "Hoàn thiện",
    hoan_cong: "Hoàn công",
  }[value] || value;
}
function tomTatNguon(value: any): string {
  if (!value) return "—";
  if (Array.isArray(value)) {
    return value
      .map((x) => (typeof x === "string" ? x : x?.name || x?.namespace || JSON.stringify(x)))
      .join(", ");
  }
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

async function loadDashboard(): Promise<void> {
  dashboardLoading.value = true;
  dashboardError.value = "";
  const thang = filter.thang || "";
  try {
    const [b, t, w, o, h, pf, ap, ot] = await Promise.all([
      apiGet<BreakdownResponse>(theoDiaBan(`/metrics/status-breakdown${thang ? `?month=${encodeURIComponent(thang)}` : ""}`)),
      apiGet<TrendResponse>(theoDiaBan("/metrics/trend?months=6")),
      apiGet<WorkloadResponse>(theoDiaBan("/metrics/workload")),
      apiGet<DanhSachHoSo>(theoDiaBan("/metrics/overdue")),
      apiGet<DanhSachHoSo>(theoDiaBan("/metrics/today-tasks")),
      apiGet<PlanningFailResponse>(theoDiaBan(`/metrics/planning-fail${thang ? `?month=${encodeURIComponent(thang)}` : ""}`)),
      apiGet<AcceptanceProgressResponse>(theoDiaBan(`/metrics/acceptance-progress${thang ? `?month=${encodeURIComponent(thang)}` : ""}`)),
      apiGet<OnTimeResponse>(theoDiaBan("/metrics/on-time?months=12")),
    ]);
    breakdown.value = b;
    trendData.value = t;
    workload.value = w;
    overdue.value = o;
    todayTasks.value = h;
    planningFail.value = pf;
    acceptanceProgress.value = ap;
    onTime.value = ot;
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
  tenNguoiDung.value = (user.profile?.name as string) || (user.profile?.preferred_username as string) || "";
  tenant.value = readTenant(user.access_token);
  if (!canViewDashboard(vaiTro.value)) {
    auth.value = "khong_quyen";
    return;
  }
  auth.value = "ok";
  await taiDiaBan();
  await taiTatCa();
});

// Đổi bộ lọc thì tải lại số liệu, không tải lại trang
watch(
  () => [filter.thang, filter.diaBan],
  () => {
    if (auth.value === "ok") void taiTatCa();
  },
);

function fmtDate(iso?: string | null): string {
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
        <button class="min-h-[44px] rounded bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700" @click="login()">Đăng nhập</button>
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
      class="mt-4 rounded bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700"
      @click="logout()"
    >
      Đăng xuất
    </button>
  </div>

  <div v-else class="flex min-h-screen max-w-full flex-col overflow-x-hidden">
    <header class="thanh-tren sticky top-0 z-30 text-chu">
      <div class="mx-auto flex h-[72px] max-w-[1320px] items-center gap-3 px-4 sm:px-6">
        <LogoMark ink="currentColor" frame="var(--vien)" />
        <div class="flex min-w-0 flex-col leading-tight">
          <b class="truncate text-[15px] font-semibold">{{ donVi }}</b>
          <span class="truncate text-[12.5px] text-phu">Bảng điều hành</span>
        </div>
        <div class="flex-1"></div>
        <button
          type="button"
          class="nut-tren nut-giao-dien"
          :aria-label="cheDo === 'toi' ? 'Nền sáng' : 'Nền tối'"
          :title="cheDo === 'toi' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'"
          @click="doiGiaoDien()"
        >
          <svg v-if="cheDo === 'toi'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
            <circle cx="12" cy="12" r="4.2" />
            <path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" />
          </svg>
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path d="M20.5 13.2A8.5 8.5 0 1 1 10.8 3.5a6.6 6.6 0 0 0 9.7 9.7z" />
          </svg>
        </button>
        <a href="/" class="nut-tren nut-chu hidden sm:inline-grid">Trang cấp phép</a>
        <template v-if="auth === 'ok'">
          <div class="hidden pl-1.5 leading-tight md:block">
            <div class="text-[13.5px] font-medium">{{ tenNguoiDung }}</div>
            <div class="text-[12px] text-phu">{{ vai }}</div>
          </div>
          <button type="button" class="nut-tren nut-chu" @click="logout()">Đăng xuất</button>
        </template>
        <button v-else type="button" class="btn btn-sm btn-chinh" @click="login()">Đăng nhập</button>
      </div>
      <nav v-if="auth === 'ok'" class="relative mx-auto flex h-[46px] max-w-[1320px] gap-7 overflow-x-auto px-4 sm:px-6" aria-label="Điều hướng bảng điều hành">
        <button type="button" class="tab-chinh" :class="tab === 'chi-so' && 'tab-dang-mo'" :aria-current="tab === 'chi-so' ? 'page' : undefined" @click="tab = 'chi-so'">Chỉ số điều hành</button>
        <button v-if="laHieuQua" type="button" class="tab-chinh" :class="tab === 'hieu-qua' && 'tab-dang-mo'" :aria-current="tab === 'hieu-qua' ? 'page' : undefined" @click="tab = 'hieu-qua'">Hiệu quả vận hành</button>
        <button type="button" class="tab-chinh" :class="tab === 'tro-ly' && 'tab-dang-mo'" :aria-current="tab === 'tro-ly' ? 'page' : undefined" @click="tab = 'tro-ly'">Hỏi đáp quy định</button>
        <button v-if="laDsar" type="button" class="tab-chinh" :class="tab === 'du-lieu-ca-nhan' && 'tab-dang-mo'" :aria-current="tab === 'du-lieu-ca-nhan' ? 'page' : undefined" @click="tab = 'du-lieu-ca-nhan'">Dữ liệu cá nhân</button>
        <button v-if="laKiemToan" type="button" class="tab-chinh" :class="tab === 'kiem-toan' && 'tab-dang-mo'" :aria-current="tab === 'kiem-toan' ? 'page' : undefined" @click="tab = 'kiem-toan'">Kiểm toán</button>
        <button v-if="laQuanTri" type="button" class="tab-chinh" :class="tab === 'quan-tri' && 'tab-dang-mo'" :aria-current="tab === 'quan-tri' ? 'page' : undefined" @click="tab = 'quan-tri'">Quản trị</button>
      </nav>
    </header>
    <main id="bdh-main" class="mx-auto w-full max-w-[1320px] flex-1 px-4 py-6 sm:px-6">

    <!-- Tab Chỉ số: dùng v-show để giữ trạng thái khi chuyển tab -->
    <section v-show="tab === 'chi-so'" class="space-y-4">
      <div class="mb-2 flex flex-wrap items-end gap-4">
        <div>
          <h1 class="tieu-de-trang">Chỉ số điều hành</h1>
          <p class="mt-2 text-[16px] text-phu">
            Tính trực tiếp từ dữ liệu của {{ donVi }}<template v-if="data">, cập nhật lúc {{ fmtDate(data.computed_at) }}</template>.
          </p>
        </div>
        <div class="flex-1"></div>
        <label v-if="laQuanTriNenTang && danhSachDiaBan.length" class="flex items-center gap-2 text-sm chu-phu">
          Phường
          <select v-model="filter.diaBan" class="o w-auto">
            <option v-for="d in danhSachDiaBan" :key="d.tenant" :value="d.tenant">{{ d.ten || d.tenant }}</option>
          </select>
        </label>
        <label class="flex items-center gap-2 text-sm chu-phu">
          Tháng
          <input v-model="filter.thang" type="month" class="o w-auto" />
        </label>
        <button class="btn" :disabled="dangXuatTep" @click="xuatExcel">Xuất Excel</button>
        <button class="btn" :disabled="dangXuatTep" @click="xuatPdf">Xuất PDF</button>
        <button class="btn" :disabled="loading" @click="loadMetrics()">Làm mới</button>
      </div>

      <div v-if="loading" class="grid grid-cols-2 gap-4 md:grid-cols-4" role="status" aria-busy="true">
        <span class="sr-only">Đang tải chỉ số</span>
        <div v-for="i in 8" :key="i" class="kinh flex animate-pulse flex-col gap-3 p-4 shadow" aria-hidden="true">
          <div class="flex items-center justify-between gap-2">
            <div class="h-3 w-2/3 rounded bg-slate-200 dark:bg-slate-700"></div>
            <div class="h-8 w-8 rounded-full bg-slate-200 dark:bg-slate-700"></div>
          </div>
          <div class="h-7 w-1/3 rounded bg-slate-200 dark:bg-slate-700"></div>
          <div class="h-3 w-1/2 rounded bg-slate-200 dark:bg-slate-700"></div>
        </div>
      </div>

      <div v-else-if="loadError" class="the p-4" role="alert">
        <p class="m-0 text-son">Không tải được số liệu: {{ loadError }}</p>
        <button class="btn btn-sm mt-3" @click="loadMetrics()">Thử lại</button>
      </div>

      <p
        v-else-if="!data || !data.metrics.length || !hasAnyValue"
        class="rounded-lg kinh p-4 chu-phu shadow"
      >
        Chưa có số liệu cho bộ lọc này.
      </p>

      <template v-else>
        <div class="the overflow-hidden">
          <div class="grid grid-cols-2 md:grid-cols-4">
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
        </div>

        <div class="grid gap-4 lg:grid-cols-2">
          <DonutChart title="Hồ sơ theo trạng thái" :items="statusItems" />
          <LineChart title="Hồ sơ theo tháng (6 tháng)" :labels="trendLabels" :series="trendLines" />
        </div>
        <BarChart title="Tải việc theo cán bộ" :items="workloadItems" />

        <div class="grid gap-4 lg:grid-cols-3">
          <div class="the p-4">
            <div class="flex items-center justify-between gap-2">
              <h2 class="text-sm font-semibold chu-phu">Quy hoạch không đạt</h2>
              <span class="tt tt-do">{{ planningFail?.items?.length || 0 }}</span>
            </div>
            <p v-if="!planningFail?.items?.length" class="mt-2 text-sm chu-phu">Không có vùng nào bị đánh không đạt trong kỳ.</p>
            <ul v-else class="mt-2 list-none space-y-1.5 p-0 text-[13px]">
              <li v-for="z in planningFail.items.slice(0, 5)" :key="z.ma_zone || z.ten" class="flex justify-between gap-2 border-b border-vien-nhat pb-1.5 last:border-0">
                <span class="min-w-0 truncate">{{ z.ten || z.ma_zone }}</span>
                <b class="whitespace-nowrap text-son">{{ z.so_lan_fail }} lần</b>
              </li>
            </ul>
          </div>

          <div class="the p-4">
            <div class="flex items-center justify-between gap-2">
              <h2 class="text-sm font-semibold chu-phu">Tiến độ nghiệm thu</h2>
              <span class="mo">{{ acceptanceRows.length }} mốc</span>
            </div>
            <p v-if="!acceptanceRows.length" class="mt-2 text-sm chu-phu">Chưa có mốc nghiệm thu trong kỳ.</p>
            <table v-else class="bang mt-2 w-full text-[12.5px]">
              <thead><tr><th>Mốc</th><th>Đạt</th><th>Không đạt</th></tr></thead>
              <tbody>
                <tr v-for="m in acceptanceRows" :key="m.loai">
                  <td>{{ tenMoc(m.loai) }}</td>
                  <td><span class="tt tt-xanh">{{ m.dat }}</span></td>
                  <td><span class="tt tt-do">{{ m.khong_dat }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="the p-4">
            <div class="flex items-center justify-between gap-2">
              <h2 class="text-sm font-semibold chu-phu">Tỷ lệ đúng hạn</h2>
              <span class="mo">6 tháng gần nhất</span>
            </div>
            <p v-if="!onTimeRecent.length" class="mt-2 text-sm chu-phu">Chưa có dữ liệu đúng hạn.</p>
            <table v-else class="bang mt-2 w-full text-[12.5px]">
              <thead><tr><th>Tháng</th><th>Đã cấp</th><th>Đúng hạn</th><th>Tỷ lệ</th></tr></thead>
              <tbody>
                <tr v-for="m in onTimeRecent" :key="m.thang">
                  <td class="whitespace-nowrap">{{ m.thang }}</td>
                  <td>{{ m.da_cap }}</td>
                  <td>{{ m.dung_han }}</td>
                  <td><b v-if="m.ty_le !== null && m.ty_le !== undefined" :class="Number(m.ty_le) < 80 ? 'text-son' : 'text-xanh'">{{ m.ty_le }}%</b><span v-else class="chu-phu">—</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="dashboardLoading" class="grid gap-4 lg:grid-cols-2" role="status" aria-busy="true">
          <span class="sr-only">Đang tải danh sách hồ sơ</span>
          <div v-for="i in 2" :key="i" class="kinh animate-pulse space-y-3 p-4 shadow" aria-hidden="true">
            <div class="h-3 w-1/3 rounded bg-slate-200 dark:bg-slate-700"></div>
            <div v-for="j in 4" :key="j" class="h-3 w-full rounded bg-slate-200 dark:bg-slate-700"></div>
          </div>
        </div>
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
                <span class="block text-xs text-rose-700 dark:text-rose-300">{{ hanBiLo(h) }} · {{ nhanTrangThai(h.trang_thai) }}</span>
              </li>
            </ul>
          </div>

          <div class="rounded-lg kinh p-4 shadow">
            <div class="flex items-center justify-between gap-2">
              <h2 class="text-sm font-semibold chu-phu">Việc đến hạn hôm nay hoặc đã quá hạn bước</h2>
              <span class="rounded-full bg-amber-100 px-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200">{{ todayTasks?.items?.length || 0 }}</span>
            </div>
            <p v-if="!todayTasks?.items?.length" class="mt-2 text-sm chu-phu">Không có việc đến hạn hôm nay.</p>
            <ul v-else class="mt-2 list-none space-y-2 p-0 text-sm">
              <li v-for="h in todayTasks.items.slice(0, 5)" :key="h.id" class="border-b border-slate-200 pb-2 last:border-0 dark:border-slate-700">
                <a :href="'/?tab=ban-lam-viec'" target="_blank" rel="noopener" class="font-medium underline">{{ h.ma_ho_so }}</a>
                <span class="block chu-phu">{{ h.ho_ten }} · {{ nhanBuoc(h.buoc) }}</span>
                <span
                  :class="['block text-xs', daQua(h.han_buoc_at) ? 'text-rose-700 dark:text-rose-300' : 'text-amber-700 dark:text-amber-300']"
                >{{ daQua(h.han_buoc_at) ? "Quá hạn bước" : "Hạn bước" }}: {{ fmtDate(h.han_buoc_at || h.han_tong_at) }}</span>
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
            <div v-if="lineage.lineage_events.length" class="mt-3 overflow-x-auto border-t border-vien-nhat pt-2">
              <table class="bang w-full text-[12px]">
                <thead>
                  <tr>
                    <th>Thời điểm</th>
                    <th>Tác vụ</th>
                    <th>Dữ liệu vào</th>
                    <th>Dữ liệu ra</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="e in lineage.lineage_events" :key="e.id">
                    <td class="whitespace-nowrap">{{ fmtDate(e.event_time) }}</td>
                    <td class="whitespace-nowrap">{{ e.job || lineage.job }}</td>
                    <td class="max-w-[240px]">{{ tomTatNguon(e.inputs) }}</td>
                    <td class="max-w-[240px]">{{ tomTatNguon(e.outputs) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </template>
    </section>

    <!-- Tab Hiệu quả vận hành (H-METRIC-01) -->
    <section v-if="laHieuQua" v-show="tab === 'hieu-qua'">
      <AutomationMetricsPanel :thang="filter.thang" />
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
          class="rounded bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700 disabled:opacity-50"
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

    <!-- Tab Dữ liệu cá nhân (DSAR: lãnh đạo / quản trị / DPO) -->
    <section v-if="laDsar" v-show="tab === 'du-lieu-ca-nhan'">
      <DsarPanel />
    </section>

    <!-- Tab Kiểm toán (chỉ dx:auditor / quản trị) -->
    <section v-if="laKiemToan" v-show="tab === 'kiem-toan'">
      <AuditorPanel :dia-ban="laQuanTriNenTang ? filter.diaBan : ''" />
    </section>

    <!-- Tab Quản trị địa bàn (dx:platform-admin / dx:tenant-admin) -->
    <section v-if="laQuanTri" v-show="tab === 'quan-tri'">
      <TenantAdminPanel :vai-tro="vaiTro" />
    </section>
    </main>
    <footer class="mx-auto flex w-full max-w-[1320px] flex-wrap justify-between gap-2 px-4 pb-6 pt-2 text-[12.5px] text-phu sm:px-6">
      <span>Hệ thống cấp phép xây dựng, DX-OS Open-Core 1.0</span>
      <span>Phát hành theo giấy phép AGPL-3.0. <a href="/" class="underline underline-offset-2">Trang cấp phép</a></span>
    </footer>
  </div>
</template>


<style scoped>
.nut-tren {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 16px;
  border: 1px solid var(--vien);
  background: var(--mat);
  color: rgb(var(--c-chu));
  display: inline-grid;
  place-items: center;
  transition: background 500ms var(--em), border-color 500ms var(--em), transform 500ms var(--em);
}
.nut-tren:hover {
  background: var(--mat-noi);
  border-color: var(--vien-noi);
  transform: translateY(-1px);
}
.nut-giao-dien svg { transition: transform 500ms var(--em); }
.nut-giao-dien:hover svg { transform: rotate(30deg); }
.nut-chu { width: auto; padding: 0 14px; font-size: 13px; white-space: nowrap; }
.tab-chinh {
  position: relative;
  background: none;
  border: 0;
  padding: 0;
  color: rgb(var(--c-phu));
  transition: color 500ms var(--em);
  font-weight: 500;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
}
.tab-chinh:hover, .tab-dang-mo { color: rgb(var(--c-chu)); }
</style>

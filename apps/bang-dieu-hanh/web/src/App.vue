<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { canViewDashboard, getUser, handleCallbackIfNeeded, login, logout, readRoles } from "./auth";
import { ApiError, apiGet, apiPost } from "./api";
import { dinhDangGiaTri, formatThoiDiem, nhanChiSo } from "./utils/metrics";
import { useTheme } from "./composables/useTheme";

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

const KEY_FILTER = "dxos-bdh-filter";
const APP_CODE = "cap-phep";
type Tab = "chi-so" | "tro-ly";

type AuthState = "dang_kiem_tra" | "chua_dang_nhap" | "khong_quyen" | "ok";
const auth = ref<AuthState>("dang_kiem_tra");
const tab = ref<Tab>("chi-so");

// Bộ lọc giữ nguyên khi chuyển tab và khi tải lại trang (sessionStorage)
const filter = reactive(loadFilter());
function loadFilter(): { thang: string; diaBan: string } {
  try {
    const raw = sessionStorage.getItem(KEY_FILTER);
    if (raw) return JSON.parse(raw);
  } catch {
    /* bỏ qua: dùng giá trị mặc định */
  }
  return { thang: "", diaBan: "" };
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

// Biểu đồ cột (SVG) cho các chỉ số dạng số lượng
const bars = computed(() => {
  const items = (data.value?.metrics ?? []).filter(
    (m) => typeof m.value === "number" && m.unit !== "ngày",
  );
  const max = Math.max(1, ...items.map((m) => Number(m.value)));
  return items.map((m, i) => ({
    code: m.code,
    label: nhanChiSo(m.code),
    value: Number(m.value),
    x: i * 60 + 10,
    h: (Number(m.value) / max) * 120,
  }));
});

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

onMounted(async () => {
  await handleCallbackIfNeeded();
  const user = await getUser();
  if (!user || user.expired) {
    auth.value = "chua_dang_nhap";
    return;
  }
  if (!canViewDashboard(readRoles(user.access_token))) {
    auth.value = "khong_quyen";
    return;
  }
  auth.value = "ok";
  await loadMetrics();
});

// Đổi bộ lọc thì tải lại số liệu, không tải lại trang
watch(
  () => [filter.thang, filter.diaBan],
  () => {
    if (auth.value === "ok") void loadMetrics();
  },
);

function fmtDate(iso?: string): string {
  return iso ? formatThoiDiem(iso) : "—";
}
</script>

<template>
  <div v-if="auth === 'dang_kiem_tra'" class="chu-phu">
    Đang kiểm tra đăng nhập...
  </div>

  <div
    v-else-if="auth === 'chua_dang_nhap'"
    class="rounded-lg kinh p-6 shadow"
  >
    <h1 class="text-xl font-semibold">Cần đăng nhập</h1>
    <p class="mt-2 chu-phu">
      Đăng nhập bằng tài khoản lãnh đạo để xem bảng điều hành.
    </p>
    <button
      class="mt-4 rounded bg-slate-800 px-4 py-2 text-white"
      @click="login()"
    >
      Đăng nhập
    </button>
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

  <div v-else class="space-y-4">
    <header class="flex items-center justify-between">
      <h1 class="text-xl font-semibold">Bảng điều hành lãnh đạo</h1>
      <button class="text-sm chu-phu underline" @click="doiGiaoDien()">
        {{ cheDo === "toi" ? "Giao diện sáng" : "Giao diện tối" }}
      </button>
      <button class="text-sm chu-phu underline" @click="logout()">
        Đăng xuất
      </button>
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
        <label class="text-sm">
          Địa bàn
          <input
            v-model="filter.diaBan"
            type="text"
            maxlength="63"
            placeholder="Mã địa bàn"
            class="ml-2 rounded border px-2 py-1"
          />
        </label>
        <p class="text-xs chu-phu">
          Bộ lọc cần API hỗ trợ tham số thang và dia_ban; hiện số liệu vẫn theo
          toàn bộ địa bàn của bạn.
        </p>
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
          <button
            v-for="m in data.metrics"
            :key="m.code"
            class="rounded-lg kinh p-4 text-left shadow hover:ring-2 hover:ring-slate-300"
            @click="openLineage(m.code)"
          >
            <div class="text-sm chu-phu">{{ nhanChiSo(m.code) }}</div>
            <div class="mt-1 text-2xl font-semibold">
              {{ dinhDangGiaTri(m) }}
            </div>
            <div v-if="m.error" class="mt-1 text-xs text-amber-700">
              Không có số liệu
            </div>
          </button>
        </div>

        <div class="rounded-lg kinh p-4 shadow">
          <h2 class="mb-2 text-sm font-semibold chu-phu">
            Biểu đồ số lượng
          </h2>
          <svg
            viewBox="0 0 520 160"
            class="w-full"
            role="img"
            aria-label="Biểu đồ cột các chỉ số"
          >
            <g v-for="b in bars" :key="b.code">
              <rect
                :x="b.x"
                :y="140 - b.h"
                width="40"
                :height="b.h"
                class="fill-slate-700"
              />
              <text
                :x="b.x + 20"
                :y="155"
                text-anchor="middle"
                font-size="8"
                class="fill-slate-500"
              >
                {{ b.label.slice(0, 12) }}
              </text>
              <text
                :x="b.x + 20"
                :y="136 - b.h"
                text-anchor="middle"
                font-size="9"
                class="fill-slate-800"
              >
                {{ b.value }}
              </text>
            </g>
          </svg>
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

      <div v-if="answer" class="rounded-lg kinh p-4 shadow">
        <p class="whitespace-pre-line">{{ answerText }}</p>
        <ol
          v-if="answer.citations.length"
          class="mt-3 list-decimal space-y-1 pl-5 text-sm chu-phu"
        >
          <li v-for="c in answer.citations" :key="c.chunk_id">
            <span class="font-semibold">{{ c.nguon }}</span
            >: {{ c.trich }}
          </li>
        </ol>
      </div>
    </section>
  </div>
</template>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div class="min-h-screen flex flex-col max-w-full overflow-x-hidden">
    <header class="thanh-tren sticky top-0 z-30 text-chu">
      <div class="max-w-[1320px] mx-auto px-4 sm:px-6 h-[72px] flex items-center gap-3">
        <LogoMark ink="currentColor" frame="var(--vien)" />
        <div class="flex flex-col leading-tight min-w-0">
          <b class="font-semibold text-[15px] truncate">{{ donVi }}</b>
          <span class="text-[12.5px] text-phu truncate">Bảng điều hành</span>
        </div>
        <div class="flex-1"></div>
        <button
          type="button"
          class="nut-tren nut-giao-dien"
          :aria-label="theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'"
          @click="toggle"
        >
          <svg v-if="theme === 'dark'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2" /><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" /></svg>
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M20.5 13.2A8.5 8.5 0 1 1 10.8 3.5a6.6 6.6 0 0 0 9.7 9.7z" /></svg>
        </button>
        <a href="/" class="nut-tren nut-chu hidden sm:inline-grid">Trang cấp phép</a>
        <template v-if="user">
          <div class="hidden md:block leading-tight pl-1.5">
            <div class="text-[13.5px] font-medium">{{ user.profile.name || user.profile.preferred_username }}</div>
            <div class="text-[12px] text-phu">{{ vai }}</div>
          </div>
          <button type="button" class="nut-tren nut-chu" @click="logout">Đăng xuất</button>
        </template>
        <button v-else-if="!loading" type="button" class="btn btn-sm btn-chinh" @click="login">Đăng nhập</button>
      </div>
      <nav v-if="user && allowed" ref="tabNav" class="relative max-w-[1320px] mx-auto px-4 sm:px-6 flex gap-7 h-[46px]" aria-label="Chức năng">
        <button type="button" :class="['tab-chinh', view === 'metrics' && 'tab-dang-mo']" :aria-current="view === 'metrics' ? 'page' : undefined" @click="view = 'metrics'">Chỉ số điều hành</button>
        <button type="button" :class="['tab-chinh', view === 'assistant' && 'tab-dang-mo']" :aria-current="view === 'assistant' ? 'page' : undefined" @click="view = 'assistant'">Hỏi đáp quy định</button>
        <span class="vach-tab" :style="vachTab" aria-hidden="true"></span>
      </nav>
    </header>

    <main class="flex-1 max-w-[1320px] w-full mx-auto px-4 sm:px-6 py-6">
      <div v-if="loading" class="py-20 text-center text-phu" role="status">Đang mở phiên làm việc…</div>

      <section v-else-if="!user" class="max-w-[600px] mx-auto my-12 the p-8 sm:p-10">
        <LogoMark :size="40" ink="rgb(var(--c-cham))" frame="var(--vien)" />
        <h1 class="tieu-de-trang mt-6 mb-3">Bảng điều hành</h1>
        <p class="text-phu leading-relaxed m-0">Số liệu giải quyết hồ sơ cấp phép, cảnh báo công trường và truy cập trái quyền của phường. Dành cho lãnh đạo và cán bộ được giao.</p>
        <p v-if="sessionNote" class="thong-bao-vang mt-4 mb-0" role="status">{{ sessionNote }}</p>
        <button type="button" class="btn btn-chinh mt-6" @click="login">Đăng nhập với tài khoản của bạn</button>
      </section>

      <section v-else-if="!allowed" class="max-w-[600px] mx-auto my-12 the p-8 sm:p-10">
        <h1 class="text-[20px] font-semibold m-0">Bạn chưa được giao xem bảng điều hành</h1>
        <p class="text-phu mt-2 mb-0">Bảng này dành cho lãnh đạo, quản trị và kiểm toán viên của phường. Bạn vẫn dùng được <a href="/" class="btn-lien-ket">trang cấp phép</a>.</p>
      </section>

      <!-- Chỉ số -->
      <section v-else-if="view === 'metrics'" class="trang">
        <div class="flex flex-wrap items-end gap-4 mb-6">
          <div>
            <h1 class="tieu-de-trang">Chỉ số điều hành</h1>
            <p class="text-phu text-[16px] mt-2 mb-0">
              Tính trực tiếp từ dữ liệu của {{ donVi }}<template v-if="updatedAt">, cập nhật lúc {{ updatedAt }}</template>.
            </p>
          </div>
          <div class="flex-1"></div>
          <button type="button" class="btn" :disabled="loadingMetrics" @click="loadMetrics">{{ loadingMetrics ? "Đang tải…" : "Làm mới" }}</button>
        </div>

        <div v-if="metricsError" class="thong-bao-loi mb-4" role="alert">{{ metricsError }}</div>

        <div class="the overflow-hidden">
          <div v-if="metrics.length === 0 && !loadingMetrics" class="px-6 py-12 text-center text-phu">Chưa có chỉ số nào được khai báo cho địa bàn này.</div>
          <div v-else class="grid grid-cols-2 md:grid-cols-4">
            <button
              v-for="m in metrics"
              :key="m.code"
              type="button"
              :aria-pressed="selected === m.code"
              :class="['chi-so', selected === m.code && 'chi-so-chon']"
              @click="selectMetric(m.code)"
            >
              <span class="block nhan-nho min-h-[34px]">{{ m.name }}</span>
              <span :class="['so block text-[40px] font-semibold leading-[1.05] mt-3 tracking-[-0.02em]', isAlarm(m) ? 'text-son' : CHI_SO_CHINH.includes(m.code) ? 'text-cham' : '']">{{ formatVi(m.value, m.unit === '%' || m.unit === 'ngày' ? 1 : 0) }}</span>
              <span class="block text-[13px] text-phu mt-2">{{ m.unit }}</span>
            </button>
          </div>
        </div>

        <div v-if="selectedMetric" class="the mt-6 p-6 sm:p-8">
          <h2 class="text-[16px] font-semibold m-0">{{ selectedMetric.name }}</h2>
          <p class="text-phu mt-1 mb-0">{{ moTa(selectedMetric.code) }}</p>

          <h3 class="text-[14px] font-semibold mt-5 mb-2">Nguồn số liệu</h3>
          <p v-if="loadingLineage" class="text-phu m-0">Đang tải…</p>
          <p v-else-if="lineage.length === 0" class="text-phu m-0">
            Chưa có lần chạy nào được ghi phả hệ dữ liệu cho chỉ số này. Chỉ số vẫn được tính trực tiếp từ cơ sở dữ liệu nghiệp vụ.
          </p>
          <div v-else class="overflow-x-auto -mx-5 border-t border-vien-nhat">
            <table class="bang">
              <thead>
                <tr><th>Thời điểm</th><th>Tác vụ</th><th>Dữ liệu vào</th><th>Dữ liệu ra</th></tr>
              </thead>
              <tbody>
                <tr v-for="e in lineage" :key="e.id">
                  <td class="whitespace-nowrap">{{ ngayGio(e.event_time) }}</td>
                  <td class="whitespace-nowrap">{{ e.job }}</td>
                  <td class="text-[13px]">{{ names(e.inputs) }}</td>
                  <td class="text-[13px]">{{ names(e.outputs) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- Hỏi đáp -->
      <section v-else class="trang max-w-[820px]">
        <h1 class="tieu-de-trang">Hỏi đáp quy định</h1>
        <p class="text-phu text-[16px] mt-2">Câu trả lời trích từ tài liệu quy định đã nạp vào hệ thống. Đối chiếu văn bản gốc trước khi áp dụng.</p>

        <div class="the mt-4">
          <ol ref="chatBox" class="list-none m-0 p-5 max-h-[520px] overflow-y-auto space-y-4" aria-live="polite">
            <li v-if="chat.length === 0" class="text-phu">Đặt câu hỏi về thủ tục, thời hạn hoặc ngưỡng quy chuẩn. Ví dụ bên dưới.</li>
            <li v-for="m in chat" :key="m.id" :class="m.role === 'user' ? 'flex justify-end' : ''">
              <div v-if="m.role === 'user'" class="max-w-[80%] px-4 py-2.5 rounded-[16px] bg-mat-noi border border-vien">{{ m.text }}</div>
              <div v-else class="max-w-[92%]">
                <div class="whitespace-pre-line leading-relaxed">{{ m.text }}</div>
                <div v-if="m.citations && m.citations.length" class="mo mt-1.5">Nguồn: {{ m.citations.join("; ") }}</div>
              </div>
            </li>
            <li v-if="asking" class="text-phu">Đang tra cứu…</li>
          </ol>
          <div class="px-5 py-4 border-t border-vien-nhat">
            <div class="flex flex-wrap gap-2 mb-3">
              <button v-for="q in samples" :key="q" type="button" class="btn btn-sm" :disabled="asking" @click="ask(q)">{{ q }}</button>
            </div>
            <form class="flex gap-2" @submit.prevent="ask(question)">
              <label for="cau-hoi" class="sr-only">Câu hỏi</label>
              <input id="cau-hoi" v-model="question" class="o" placeholder="Nhập câu hỏi" autocomplete="off" />
              <button type="submit" class="btn btn-chinh" :disabled="!question.trim() || asking">Hỏi</button>
            </form>
          </div>
        </div>
      </section>
    </main>

    <footer class="max-w-[1320px] w-full mx-auto px-4 sm:px-6 pb-6 pt-2 text-phu text-[12.5px] flex flex-wrap justify-between gap-2">
      <span>Hệ thống cấp phép xây dựng, DX-OS Open-Core 1.1</span>
      <span>Phát hành theo giấy phép AGPL-3.0. <a :href="SOURCE_URL" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">Mã nguồn</a></span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from "vue";
import type { User } from "oidc-client-ts";
import LogoMark from "./components/LogoMark.vue";
import { useVachTab } from "./composables/useVachTab";
import { useTheme } from "./composables/useTheme";
import { currentUser, login, logout, clearSession } from "./auth";
import { apiFetch } from "./api";

const SOURCE_URL: string = import.meta.env.VITE_SOURCE_URL || "https://github.com/dxos-core/dxos";

const { theme, toggle } = useTheme();
const user = ref<User | null>(null);
const loading = ref(true);
const view = ref<"metrics" | "assistant">("metrics");
const tabNav = ref<HTMLElement | null>(null);
const vachTab = useVachTab(tabNav, view);

const roles = computed<string[]>(() => ((user.value?.profile as any)?.roles || []) as string[]);
const tenant = computed<string>(() => ((user.value?.profile as any)?.tenant || "") as string);
const VIEW_ROLES = ["app:cap-phep:lanh-dao", "dx:tenant-admin", "dx:platform-admin", "dx:auditor"];
const allowed = computed(() => roles.value.some((r) => VIEW_ROLES.includes(r)));

const VAI: Record<string, string> = {
  "app:cap-phep:lanh-dao": "Lãnh đạo phường",
  "dx:tenant-admin": "Quản trị phường",
  "dx:platform-admin": "Quản trị hệ thống",
  "dx:auditor": "Kiểm toán viên",
};
const vai = computed(() => VAI[roles.value.find((r) => VAI[r]) || ""] || "Người dùng");

const donVi = computed(() => {
  const m = /^(phuong|xa)-(.+)$/.exec(tenant.value);
  if (!m) return tenant.value || "Hệ thống cấp phép";
  const ten = m[2].split("-").map((p) => (p.length <= 2 ? p.toUpperCase() : p[0].toUpperCase() + p.slice(1))).join(" ");
  return `UBND ${m[1] === "xa" ? "Xã" : "Phường"} ${ten}`;
});

/** Phiên hết hạn: xoá phiên OIDC, quay về màn đăng nhập kèm lời nhắc. */
const sessionNote = ref("");
async function handleError(e: any): Promise<boolean> {
  if (e?.status === 401) {
    await clearSession();
    user.value = null;
    sessionNote.value = "Phiên đăng nhập đã hết hạn. Đăng nhập lại để xem tiếp.";
    return true;
  }
  return false;
}

// ---- Chỉ số ----
interface Metric { code: string; name: string; value: number; unit: string }
const metrics = ref<Metric[]>([]);
const loadingMetrics = ref(false);
const metricsError = ref("");
const updatedAt = ref("");
const selected = ref("");
const lineage = ref<any[]>([]);
const loadingLineage = ref(false);
const selectedMetric = computed(() => metrics.value.find((m) => m.code === selected.value) || null);

const MO_TA: Record<string, string> = {
  ho_so_moi: "Tổng số hồ sơ cấp phép xây dựng đã nộp vào phường.",
  ho_so_dang_xu_ly: "Hồ sơ đã nộp nhưng chưa có kết quả cấp phép hoặc từ chối.",
  ty_le_dung_han: "Tỷ lệ hồ sơ không bị quá hạn trên tổng số hồ sơ đã nộp.",
  ho_so_qua_han: "Hồ sơ chưa có kết quả đã vượt thời hạn giải quyết.",
  thoi_gian_xu_ly_tb: "Số ngày trung bình từ khi nộp hồ sơ đến khi được cấp phép.",
  phieu_kiem_tra: "Số phiếu kiểm tra hiện trường đã lập trong quá trình hậu kiểm.",
  canh_bao_cong_truong: "Số lần cảm biến tại công trường báo vượt ngưỡng tiếng ồn hoặc bụi.",
  vi_pham: "Số phiếu kiểm tra kết luận công trình có vi phạm.",
  truy_cap_tu_choi: "Số lần hệ thống chặn một người mở hồ sơ hoặc tệp không thuộc quyền của họ.",
};
function moTa(code: string): string {
  return MO_TA[code] || "";
}
// Con số then chốt duy nhất được tô champagne (tỷ lệ đúng hạn hoặc thời gian xử lý, tuỳ app khai báo)
const CHI_SO_CHINH = ["ty_le_dung_han", "thoi_gian_xu_ly_tb"];
function isAlarm(m: Metric): boolean {
  return ["ho_so_qua_han", "truy_cap_tu_choi", "vi_pham"].includes(m.code) && Number(m.value) > 0;
}

async function loadMetrics() {
  loadingMetrics.value = true;
  metricsError.value = "";
  try {
    const data = await apiFetch<{ metrics: Metric[] }>("/api/v1/metrics", user.value?.access_token || "");
    metrics.value = Array.isArray(data.metrics) ? data.metrics : [];
    updatedAt.value = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  } catch (e: any) {
    if (await handleError(e)) return;
    metricsError.value = `Không tải được chỉ số (mã lỗi ${e?.status || e.message}). Bấm Làm mới để thử lại.`;
  } finally {
    loadingMetrics.value = false;
  }
}

async function selectMetric(code: string) {
  selected.value = code;
  loadingLineage.value = true;
  lineage.value = [];
  try {
    const data = await apiFetch<{ lineage_events: any[] }>(
      `/api/v1/metrics/${encodeURIComponent(code)}/lineage`,
      user.value?.access_token || "",
    );
    lineage.value = Array.isArray(data.lineage_events) ? data.lineage_events : [];
  } catch (e: any) {
    await handleError(e);
  } finally {
    loadingLineage.value = false;
  }
}

function names(list: any): string {
  return Array.isArray(list) ? list.map((x) => x?.name || "").filter(Boolean).join(", ") : "";
}

// ---- Hỏi đáp ----
interface ChatMsg { id: number; role: "user" | "assistant"; text: string; citations?: string[] }
const chat = ref<ChatMsg[]>([]);
const question = ref("");
const asking = ref(false);
const chatBox = ref<HTMLElement | null>(null);
const samples = [
  "Thời hạn cấp giấy phép xây dựng nhà ở riêng lẻ là bao lâu?",
  "Ngưỡng tiếng ồn ban ngày tại công trường?",
  "Hồ sơ cấp phép gồm những giấy tờ gì?",
];
let seq = 0;

async function ask(q: string) {
  const text = q.trim();
  if (!text || asking.value) return;
  chat.value.push({ id: ++seq, role: "user", text });
  question.value = "";
  asking.value = true;
  await scrollChat();
  try {
    const data = await apiFetch<{ answer: string; citations: string[] }>("/api/v1/assistant/ask", user.value?.access_token || "", {
      method: "POST",
      body: JSON.stringify({ question: text, app: "cap-phep" }),
    });
    chat.value.push({ id: ++seq, role: "assistant", text: data.answer || "Không có câu trả lời.", citations: data.citations || [] });
  } catch (e: any) {
    if (await handleError(e)) return;
    chat.value.push({ id: ++seq, role: "assistant", text: `Chưa tra cứu được (mã lỗi ${e?.status || e.message}). Thử lại sau.` });
  } finally {
    asking.value = false;
    await scrollChat();
  }
}

async function scrollChat() {
  await nextTick();
  if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight;
}

function formatVi(val: number, digits = 0) {
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: digits }).format(Number(val) || 0);
}
function ngayGio(v: any): string {
  const d = new Date(v);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }) + " " + d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

onMounted(async () => {
  try {
    user.value = await currentUser();
  } finally {
    loading.value = false;
  }
  if (user.value && allowed.value) await loadMetrics();
});
</script>

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
/* Biểu tượng mặt trời / trăng xoay nhẹ, chuông rung một nhịp khi trỏ vào */
.nut-giao-dien svg {
  transition: transform 500ms var(--em);
}
.nut-giao-dien:hover svg {
  transform: rotate(30deg);
}
.nut-chuong:hover svg {
  transform-origin: 50% 10%;
  animation: chuong-lac 700ms var(--em);
}
@keyframes chuong-lac {
  20% { transform: rotate(14deg); }
  45% { transform: rotate(-10deg); }
  70% { transform: rotate(5deg); }
}
.nut-chu {
  width: auto;
  padding: 0 14px;
  font-size: 13px;
  white-space: nowrap;
}
.tab-chinh {
  position: relative;
  background: none;
  border: 0;
  padding: 0;
  color: rgb(var(--c-phu));
  transition: color 500ms cubic-bezier(0.16, 1, 0.3, 1);
  font-weight: 500;
  white-space: nowrap;
}
.tab-chinh:hover,
.tab-dang-mo {
  color: rgb(var(--c-chu));
}
.chi-so {
  text-align: left;
  padding: 24px;
  transition: background 500ms var(--em), box-shadow 500ms var(--em);
  border: 0;
  border-right: 1px solid var(--vien-nhat);
  border-bottom: 1px solid var(--vien-nhat);
  background: transparent;
  color: inherit;
}
.chi-so:hover {
  background: radial-gradient(240px circle at var(--mx, 50%) var(--my, 50%), var(--sang-mat), transparent 70%), var(--mat-2);
}
/* Con số nhấc nhẹ khi trỏ vào ô */
.chi-so .so {
  transition: transform 500ms var(--em);
}
.chi-so:hover .so {
  transform: translateY(-3px);
}
.chi-so-chon,
.chi-so-chon:hover {
  background: var(--mat-noi);
  box-shadow: inset 0 -2px 0 rgb(var(--c-chu));
}
</style>

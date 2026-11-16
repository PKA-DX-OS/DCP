<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div class="min-h-screen flex flex-col max-w-full overflow-x-hidden">
    <Navbar
      :user="user"
      :loading="loading"
      :notifications="notifications"
      :unread-count="unreadCount"
      :tenant="user ? userTenant : ''"
      :roles="userRoles"
      @login="handleLogin"
      @logout="handleLogout"
      @clear-unread="handleMarkAllRead"
      @select-notification="handleSelectNotification"
    >
      <template #tabs>
        <nav v-if="user" ref="tabNav" class="relative max-w-[1320px] mx-auto px-4 sm:px-6 flex gap-7 h-[46px] overflow-x-auto" aria-label="Chức năng">
          <button
            v-for="t in tabs"
            :key="t.key"
            :id="t.id"
            type="button"
            :aria-current="activeTab === t.key ? 'page' : undefined"
            :class="['tab-chinh', activeTab === t.key && 'tab-dang-mo']"
            @click="openTab(t.key)"
          >
            {{ t.label }}
            <span v-if="t.key === 'workspace' && workCount > 0" class="ml-1.5 text-[12px] px-[7px] py-px rounded-full bg-mat-noi">{{ workCount }}</span>
            <span v-if="t.key === 'workspace' && pendingBreakGlassList.length > 0" id="badge-pending-bg" class="sr-only">{{ pendingBreakGlassList.length }}</span>
          </button>
          <span class="vach-tab" :style="vachTab" aria-hidden="true"></span>
        </nav>
      </template>
    </Navbar>

    <main class="flex-1 max-w-[1320px] mx-auto px-4 sm:px-6 py-6 w-full">
      <section v-if="!user && !loading" class="max-w-[600px] mx-auto my-12 the p-8 sm:p-10">
        <LogoMark :size="40" ink="rgb(var(--c-cham))" frame="var(--vien)" />
        <h1 class="tieu-de-trang mt-6 mb-3">Cấp phép xây dựng nhà ở riêng lẻ</h1>
        <p class="text-phu leading-relaxed m-0">
          Người dân nộp hồ sơ, theo dõi tiến độ và nhận giấy phép trực tuyến. Cán bộ phường đăng nhập để xử lý hồ sơ được giao.
        </p>
        <button type="button" class="btn btn-chinh mt-6" @click="handleLogin">Đăng nhập với tài khoản của bạn</button>
        <p class="goi-y mt-5 mb-0">Muốn kiểm tra một giấy phép đã cấp? Quét mã QR in trên giấy phép, không cần đăng nhập.</p>
      </section>

      <div v-else-if="loading" class="py-20 text-center text-phu" role="status">Đang mở phiên làm việc…</div>

      <template v-else>
        <DossiersView
          class="trang"
          v-if="activeTab === 'dossiers'"
          :dossiers="dossiers"
          :error-msg="errorMsg"
          :is-staff="isStaff"
          :is-applicant="isApplicant"
          @create-dossier="showCreateModal = true"
          @refresh="refreshData"
          @view-detail="viewDossierDetail"
          @supplement="openSupplementModal"
          @open-by-code="openDossierByCode"
        />

        <WorkspaceView
          class="trang"
          v-if="activeTab === 'workspace'"
          :tasks="tasks"
          :dossiers="dossiers"
          :user-sub="user?.profile?.sub"
          :user-tenant="userTenant"
          :user-token="user?.access_token"
          :forbidden-error="forbiddenError"
          :pending-break-glass-list="pendingBreakGlassList"
          @complete-task="executeCompleteTask"
          @request-break-glass="openBreakGlassModal"
          @approve-break-glass="handleApproveBreakGlass"
          @deny-break-glass="handleDenyBreakGlass"
        />

        <ConstructionView
          class="trang"
          v-if="activeTab === 'construction'"
          :construction-list="constructionList"
          :inspection-list="inspectionList"
          :user-roles="userRoles"
          :user-token="user?.access_token"
          @refresh="loadConstructionData"
          @create-inspection="handleCreateInspection"
          @demo-sensor="handleTriggerDemoSensor"
        />

        <ConsentView
          class="trang"
          v-if="activeTab === 'consent'"
          :dsar-list="dsarList"
          @save-consents="saveConsents"
          @dsar="handleDsar"
        />
      </template>
    </main>

    <!-- Modal 1: Nộp hồ sơ mới -->
    <CreateDossierModal
      v-if="showCreateModal"
      :submitting="submitting"
      :requirements="documentRequirements"
      :errors="docErrors"
      :loading-requirements="loadingRequirements"
      @close="showCreateModal = false; docErrors = []"
      @submit="submitHoSo"
    />
    <!-- Modal 2: Chi tiết hồ sơ -->
    <DetailDossierModal v-if="detailHoSo" :dossier="detailHoSo" :user-token="user?.access_token" @close="detailHoSo = null" @supplement="openSupplementModal" />
    <SupplementModal v-if="supplementingHoSo" :dossier="supplementingHoSo" :submitting="submitting" @close="supplementingHoSo = null" @submit="handleSupplementHoSo" />
    <BreakGlassModal v-if="showBreakGlassModal" :ho-so-id="breakGlassHoSoId" :ma-ho-so="breakGlassHoSoMa" :submitting="submitting" @close="showBreakGlassModal = false" @confirm="handleRequestBreakGlass" />
    <Forbidden403Modal v-if="show403Modal" :ma-ho-so="forbiddenHoSoMa" @close="show403Modal = false" @request-break-glass="triggerBreakGlassFrom403" />
    <ToastHost />

    <footer class="max-w-[1320px] w-full mx-auto px-4 sm:px-6 pb-6 pt-2 text-phu text-[12.5px] flex flex-wrap justify-between gap-2">
      <span>Hệ thống cấp phép xây dựng, DX-OS Open-Core {{ APP_VERSION }}</span>
      <span>Phát hành theo giấy phép AGPL-3.0. <a :href="SOURCE_URL" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">Mã nguồn</a></span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { login, logout, handleCallbackIfNeeded, clearSession } from "./auth";
import type { User } from "oidc-client-ts";
import type { DocEntry, DocError, DocRequirement, HoSo, NopHoSoPayload } from "./types";
import {
  fetchHoSo,
  fetchDocumentRequirements,
  openHoSo,
  fetchTasks,
  completeTask,
  fetchPendingBreakGlass,
  requestBreakGlass,
  approveBreakGlass,
  fetchCongTrinh,
  fetchPhieuKiemTra,
  createInspection,
  triggerDemoSensor,
  grantConsent,
  withdrawConsent,
  fetchDsarRequests,
  submitDsarRequest,
} from "./api";

// Sub-components & Views
import Navbar from "./components/Navbar.vue";
import CreateDossierModal from "./components/CreateDossierModal.vue";
import DetailDossierModal from "./components/DetailDossierModal.vue";
import SupplementModal from "./components/SupplementModal.vue";
import BreakGlassModal from "./components/BreakGlassModal.vue";
import Forbidden403Modal from "./components/Forbidden403Modal.vue";
import ToastHost from "./components/ToastHost.vue";
import LogoMark from "./components/LogoMark.vue";
import { notify } from "./composables/useToast";
import { tenNhiemVu } from "./utils/labels";
import { SOURCE_URL, APP_VERSION } from "./config";
import DossiersView from "./views/DossiersView.vue";
import WorkspaceView from "./views/WorkspaceView.vue";
import ConstructionView from "./views/ConstructionView.vue";
import ConsentView from "./views/ConsentView.vue";

// Composables
import { useDossierActions } from "./composables/useDossierActions";
import { useNotifications } from "./composables/useNotifications";
import { useVachTab } from "./composables/useVachTab";

const activeTab = ref<"dossiers" | "workspace" | "construction" | "consent">("dossiers");
const tabNav = ref<HTMLElement | null>(null);
const vachTab = useVachTab(tabNav, activeTab);
const errorMsg = ref("");
const submitting = ref(false);
const forbiddenError = ref(false);

const dossiers = ref<HoSo[]>([]);
const documentRequirements = ref<DocRequirement[]>([]);
const docErrors = ref<DocError[]>([]);
const loadingRequirements = ref(false);
const tasks = ref<any[]>([]);
const constructionList = ref<any[]>([]);
const inspectionList = ref<any[]>([]);
const dsarList = ref<any[]>([]);
const pendingBreakGlassList = ref<any[]>([]);

// Modals
const showCreateModal = ref(false);
const detailHoSo = ref<HoSo | null>(null);
const supplementingHoSo = ref<HoSo | null>(null);
const showBreakGlassModal = ref(false);
const breakGlassHoSoId = ref("");
const breakGlassHoSoMa = ref("");
const show403Modal = ref(false);
const forbiddenHoSoId = ref("");
const forbiddenHoSoMa = ref("");

const user = ref<User | null>(null);
const loading = ref(true);

// Notifications & SSE (S-01, T-05, T-09)
const {
  notifications,
  unreadCount,
  initSSE,
  closeSSE,
  loadNotifications,
  handleMarkAllRead,
  handleSelectNotification,
} = useNotifications(user, dossiers, refreshData, openDossierByCode, viewDossierDetail);

// Actions for dossiers
const { submitHoSo: doSubmitHoSo, handleSupplementHoSo: doSupplementHoSo } = useDossierActions(
  user,
  submitting,
  refreshData,
  (errors) => {
    docErrors.value = errors;
  }
);

async function loadDocumentRequirements() {
  if (!user.value?.access_token) return;
  loadingRequirements.value = true;
  try {
    documentRequirements.value = await fetchDocumentRequirements(user.value.access_token);
  } catch (err: any) {
    console.warn("Lỗi tải manifest giấy tờ:", err);
    errorMsg.value = String(err?.message || err);
  } finally {
    loadingRequirements.value = false;
  }
}

async function submitHoSo(form: NopHoSoPayload, docs: DocEntry[]) {
  docErrors.value = [];
  await doSubmitHoSo(form, docs, () => {
    showCreateModal.value = false;
  });
}

async function handleSupplementHoSo(payload: any) {
  await doSupplementHoSo(supplementingHoSo, payload);
}

watch(
  () => user.value?.access_token,
  (newToken, oldToken) => {
    if (newToken !== oldToken) {
      if (newToken) {
        loadDocumentRequirements();
        initSSE();
      } else {
        closeSSE();
      }
    }
  }
);

async function initAuth() {
  loading.value = true;
  try {
    user.value = await handleCallbackIfNeeded();
  } catch (err) {
    console.error("Auth init error", err);
  } finally {
    loading.value = false;
  }
}

const userTenant = computed(() => {
  return (user.value?.profile as any)?.tenant || "";
});

const userRoles = computed(() => {
  return ((user.value?.profile as any)?.roles || []) as string[];
});

const STAFF_ROLES = ["app:cap-phep:mot-cua", "app:cap-phep:tham-dinh", "app:cap-phep:lanh-dao", "app:cap-phep:trat-tu-xd", "dx:tenant-admin", "dx:platform-admin", "dx:auditor"];
const isStaff = computed(() => userRoles.value.some((r) => STAFF_ROLES.includes(r)));
const isApplicant = computed(() => userRoles.value.includes("app:cap-phep:chu-dau-tu"));
const workCount = computed(() => tasks.value.length + pendingBreakGlassList.value.length);

type TabKey = "dossiers" | "workspace" | "construction" | "consent";
const tabs: { key: TabKey; id: string; label: string }[] = [
  { key: "dossiers", id: "tab-dossiers", label: "Hồ sơ" },
  { key: "workspace", id: "tab-workspace", label: "Việc của tôi" },
  { key: "construction", id: "tab-construction", label: "Công trình và hậu kiểm" },
  { key: "consent", id: "tab-consent", label: "Dữ liệu cá nhân" },
];

function openTab(key: TabKey) {
  activeTab.value = key;
  if (key === "workspace") refreshData();
  else if (key === "construction") loadConstructionData();
  else if (key === "consent") loadDsarData();
}

onMounted(async () => {
  await initAuth();
  if (user.value) {
    await loadDocumentRequirements();
    await refreshData();
    initSSE();
  }
});

onUnmounted(() => {
  closeSSE();
});

async function refreshData() {
  if (!user.value?.access_token) return;
  errorMsg.value = "";
  try {
    dossiers.value = await fetchHoSo(user.value.access_token);
    tasks.value = await fetchTasks(user.value.access_token);
    const roles = userRoles.value;
    if (roles.includes("app:cap-phep:lanh-dao") || roles.includes("dx:lanh-dao")) {
      await loadPendingBreakGlass();
    }
    if (activeTab.value === "consent") {
      await loadDsarData();
    }
    if (activeTab.value === "construction" || roles.includes("app:cap-phep:trat-tu-xd") || roles.includes("dx:kiem-tra")) {
      await loadConstructionData();
    }
    await loadNotifications();
  } catch (err: any) {
    console.warn("Lỗi tải dữ liệu:", err);
    if (String(err?.message || "").includes("401")) {
      await clearSession();
      user.value = null;
      errorMsg.value = "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.";
    } else {
      errorMsg.value = String(err?.message || err);
    }
  }
}

async function loadPendingBreakGlass() {
  if (!user.value?.access_token) return;
  try {
    pendingBreakGlassList.value = await fetchPendingBreakGlass(user.value.access_token);
  } catch (err) {
    console.debug("Lỗi tải yêu cầu break-glass:", err);
  }
}

async function loadConstructionData() {
  if (!user.value?.access_token) return;
  try {
    constructionList.value = await fetchCongTrinh(user.value.access_token);
    inspectionList.value = await fetchPhieuKiemTra(user.value.access_token);
  } catch (err) {
    console.debug("Lỗi tải công trình:", err);
  }
}

async function handleCreateInspection(construction: any) {
  if (!user.value?.access_token) return;
  try {
    await createInspection(user.value.access_token, construction.id, "Kiểm tra chủ động hiện trường");
    await loadConstructionData();
    notify("Đã tạo phiếu kiểm tra cho công trình " + (construction.ma_cong_trinh || "") + ".");
  } catch (err: any) {
    notify("Không tạo được phiếu kiểm tra: " + (err.message || err), "loi");
  }
}

async function handleTriggerDemoSensor(maCongTrinh: string) {
  if (!user.value?.access_token) return;
  try {
    await triggerDemoSensor(user.value.access_token, maCongTrinh, 86.5);
    notify(`Đã gửi số đo 86,5 dBA cho công trình ${maCongTrinh}.`);
    await loadConstructionData();
    await refreshData();
  } catch (err: any) {
    notify("Không gửi được số đo mô phỏng: " + (err.message || err), "loi");
  }
}

async function loadDsarData() {
  if (!user.value?.access_token) return;
  try {
    dsarList.value = await fetchDsarRequests(user.value.access_token);
  } catch (err) {
    console.debug("Lỗi tải DSAR:", err);
  }
}

function handleLogin() {
  login();
}

function handleLogout() {
  closeSSE();
  logout();
}

async function viewDossierDetail(d: HoSo) {
  if (!user.value?.access_token) return;
  try {
    const res = await openHoSo(user.value.access_token, d.id);
    detailHoSo.value = res || d;
  } catch (err: any) {
    console.warn("Lỗi mở hồ sơ:", err);
    if (err.status === 403 || err.message?.includes("403") || err.message?.includes("42501")) {
      forbiddenHoSoId.value = d.id;
      forbiddenHoSoMa.value = d.ma_ho_so;
      show403Modal.value = true;
    } else {
      notify(`Không mở được hồ sơ: ${err.message}`, "loi");
    }
  }
}

function triggerBreakGlassFrom403() {
  const targetId = forbiddenHoSoId.value;
  show403Modal.value = false;
  openBreakGlassModal(targetId);
}

function openSupplementModal(d: HoSo) {
  supplementingHoSo.value = d;
}

function openBreakGlassModal(hoSoId: string) {
  breakGlassHoSoId.value = hoSoId;
  breakGlassHoSoMa.value = dossiers.value.find((d) => d.id === hoSoId)?.ma_ho_so || forbiddenHoSoMa.value || "";
  showBreakGlassModal.value = true;
}

async function openDossierByCode(code: string) {
  if (!user.value?.access_token) return;
  try {
    const res = await openHoSo(user.value.access_token, code);
    detailHoSo.value = res;
  } catch (err: any) {
    console.warn("Lỗi mở hồ sơ:", err);
    if (err.status === 403 || err.message?.includes("403") || err.message?.includes("42501")) {
      forbiddenHoSoId.value = err.data?.ho_so_id || code;
      forbiddenHoSoMa.value = err.data?.ma_ho_so || code;
      show403Modal.value = true;
    } else {
      notify(`Không mở được hồ sơ: ${err.message}`, "loi");
    }
  }
}

async function handleApproveBreakGlass(bg: any) {
  if (!user.value?.access_token) return;
  try {
    await approveBreakGlass(user.value.access_token, bg.object_id, bg.requester_sub, true);
    notify("Đã duyệt truy cập khẩn. Cán bộ có thể mở hồ sơ trong thời hạn cho phép.");
    await loadPendingBreakGlass();
  } catch (err: any) {
    notify(`Không duyệt được truy cập khẩn: ${err.message}`, "loi");
  }
}

async function handleDenyBreakGlass(bg: any) {
  if (!user.value?.access_token) return;
  try {
    await approveBreakGlass(user.value.access_token, bg.object_id, bg.requester_sub, false);
    notify("Đã từ chối yêu cầu truy cập khẩn.");
    await loadPendingBreakGlass();
  } catch (err: any) {
    notify(`Không từ chối được yêu cầu: ${err.message}`, "loi");
  }
}

async function handleRequestBreakGlass(hoSoId: string, reason: string) {
  if (!user.value?.access_token || !hoSoId) return;
  submitting.value = true;
  try {
    await requestBreakGlass(user.value.access_token, hoSoId, reason);
    showBreakGlassModal.value = false;
    notify("Đã gửi yêu cầu truy cập khẩn. Lãnh đạo phường sẽ duyệt.");
    forbiddenError.value = false;
    await loadPendingBreakGlass();
  } catch (err: any) {
    notify(`Không gửi được yêu cầu: ${err.message}`, "loi");
  } finally {
    submitting.value = false;
  }
}

async function executeCompleteTask(payload: { taskId: string; variables: Record<string, any> }) {
  if (!user.value?.access_token || !payload?.taskId) return;
  try {
    const task = tasks.value.find((t) => t.id === payload.taskId);
    await completeTask(user.value.access_token, payload.taskId, payload.variables);
    notify(`Đã hoàn thành: ${tenNhiemVu(task)}.`);
    await refreshData();
  } catch (err: any) {
    notify(`Không hoàn thành được nhiệm vụ: ${err.message}`, "loi");
  }
}

async function saveConsents(consentsData: any) {
  if (!user.value?.access_token) return;
  try {
    await grantConsent(user.value.access_token, "xu_ly_ho_so", "v1.0");
  } catch (err) {
    console.debug("Lỗi lưu đồng thuận:", err);
  }
}

async function handleDsar(action: string, note?: string) {
  if (!user.value?.access_token) return;
  const legalNote = note || "Yêu cầu trích xuất toàn bộ dữ liệu cá nhân (mẫu)";
  try {
    if (action === "access") {
      await submitDsarRequest(user.value.access_token, "access", legalNote);
      notify("Đã gửi yêu cầu cung cấp dữ liệu. Phường sẽ xác nhận trong 2 ngày làm việc.");
    } else if (action === "withdraw") {
      await withdrawConsent(user.value.access_token, "xu_ly_ho_so");
      notify("Đã rút đồng thuận xử lý dữ liệu cá nhân.");
    } else if (action === "erase") {
      await submitDsarRequest(user.value.access_token, "erasure", legalNote);
      notify("Đã gửi yêu cầu xóa dữ liệu cá nhân.");
    }
    await loadDsarData();
  } catch (err: any) {
    notify(`Không gửi được yêu cầu: ${err.message}`, "loi");
  }
}
</script>

<style scoped>
.tab-chinh {
  position: relative;
  background: none;
  border: 0;
  padding: 0;
  color: rgb(var(--c-phu));
  transition: color 500ms cubic-bezier(0.16, 1, 0.3, 1);
  font-weight: 500;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
}
.tab-chinh:hover,
.tab-dang-mo {
  color: rgb(var(--c-chu));
}
</style>

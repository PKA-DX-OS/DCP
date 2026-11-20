<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { getUser, getValidToken, handleCallbackIfNeeded, login, logout, readRoles } from "./auth";
import { useNotifications } from "./composables/useNotifications";
import { useCongDan } from "./composables/useCongDan";
import { batAnhSang } from "./utils/anhSang";
import type { DocEntry, HoSo, NopHoSoPayload } from "./types";
import Navbar from "./components/Navbar.vue";
import LogoMark from "./components/LogoMark.vue";
import ToastHost from "./components/ToastHost.vue";
import { useTheme } from "./composables/useTheme";
import CreateDossierModal from "./components/CreateDossierModal.vue";
import DetailDossierModal from "./components/DetailDossierModal.vue";
import SupplementModal from "./components/SupplementModal.vue";
import Forbidden403Modal from "./components/Forbidden403Modal.vue";
import BreakGlassModal from "./components/BreakGlassModal.vue";
import { tabsChoVai } from "./features/registry";
import { provideFeatureContext } from "./features/context";
import { laCanBo as coVaiCanBo, laChuDauTu as coVaiChuDauTu } from "./features/roles";

type TrangThai = "dang_kiem_tra" | "chua_dang_nhap" | "khong_quyen" | "ok";
const trang = ref<TrangThai>("dang_kiem_tra");
const tenNguoiDung = ref("");
const subNguoiDung = ref<string | undefined>(undefined);
const vaiTro = ref<string[]>([]);
const accessToken = ref<string | undefined>(undefined);

const laCanBo = computed(() => coVaiCanBo(vaiTro.value));
const laChuDauTu = computed(() => coVaiChuDauTu(vaiTro.value));

// Tab theo vai lấy từ features/registry.ts; thêm màn hình mới không cần sửa tệp này
const FEATURES_HIEN = computed(() => tabsChoVai(vaiTro.value));
const TABS = computed(() => FEATURES_HIEN.value.map((f) => ({ ma: f.ma, ten: f.ten })));
const thongBao = useNotifications(() => subNguoiDung.value);
const cd = useCongDan(getValidToken, () => subNguoiDung.value);
const { theme, toggle: doiGiaoDien } = useTheme();

const KHOA_URL = "tab";
const tab = ref<string>("");

function docTabTuUrl(): string {
  const t = new URL(window.location.href).searchParams.get(KHOA_URL);
  return TABS.value.some((x) => x.ma === t) ? (t as string) : TABS.value[0]?.ma || "";
}

// Đồng bộ tab với URL bằng replaceState để không làm dày lịch sử
watch(tab, (v) => {
  if (!v) return;
  const u = new URL(window.location.href);
  u.searchParams.set(KHOA_URL, v);
  window.history.replaceState(window.history.state, "", u.toString());
  FEATURES_HIEN.value.find((f) => f.ma === v)?.khiMo?.(ctx);
});


// Hộp thoại
const moNop = ref(false);
const hoSoChiTiet = ref<HoSo | null>(null);
const hoSoBoSung = ref<HoSo | null>(null);
const biChan = ref<{ id: string; ma: string } | null>(null);
const xinKhan = ref<{ id: string; ma: string } | null>(null);

async function moNopHoSo(): Promise<void> {
  moNop.value = true;
  if (!cd.requirements.value.length) await cd.taiGiayTo();
}

async function nopHoSo(form: NopHoSoPayload, docs: DocEntry[]): Promise<void> {
  if (await cd.nop(form, docs)) moNop.value = false;
}

async function guiBoSung(payload: { form: any; file?: File | null }): Promise<void> {
  if (hoSoBoSung.value && (await cd.boSung(hoSoBoSung.value, payload))) hoSoBoSung.value = null;
}

async function moHoSo(idHoacMa: string, ma = ""): Promise<void> {
  const kq = await cd.moHoSo(idHoacMa, ma);
  if (!kq) return;
  if ("hoSo" in kq) {
    accessToken.value = (await getValidToken()) || accessToken.value;
    hoSoChiTiet.value = kq.hoSo;
  }
  else biChan.value = kq.biChan;
}

function moBoSung(d: HoSo): void {
  hoSoChiTiet.value = null;
  hoSoBoSung.value = d;
}

function chuyenSangXinKhan(): void {
  xinKhan.value = biChan.value;
  biChan.value = null;
}

async function guiXinKhan(hoSoId: string, lyDo: string): Promise<void> {
  if (await cd.xinTruyCapKhan(hoSoId, lyDo)) xinKhan.value = null;
}

const ctx = { vaiTro, sub: subNguoiDung, cd, moHoSo, moNopHoSo, moBoSung };
provideFeatureContext(ctx);

onMounted(async () => {
  batAnhSang();
  await handleCallbackIfNeeded();
  const user = await getUser();
  if (!user || user.expired) {
    trang.value = "chua_dang_nhap";
    return;
  }
  vaiTro.value = readRoles(user.access_token);
  if (!laCanBo.value && !laChuDauTu.value) {
    trang.value = "khong_quyen";
    return;
  }
  tenNguoiDung.value = (user.profile?.name as string) || (user.profile?.preferred_username as string) || "";
  subNguoiDung.value = user.profile?.sub as string | undefined;
  accessToken.value = user.access_token;
  tab.value = docTabTuUrl();
  trang.value = "ok";
  thongBao.batDau();
  if (laChuDauTu.value) await cd.taiHoSo();
});
</script>

<template>
  <a
    href="#main"
    class="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded focus:bg-white focus:px-4 focus:py-2 focus:text-slate-900"
  >Bỏ qua điều hướng</a>
  <ToastHost />

  <div v-if="trang === 'dang_kiem_tra'" class="p-6 text-phu" role="status">Đang kiểm tra đăng nhập...</div>

  <div v-else-if="trang === 'chua_dang_nhap'" class="login-shell">
    <button class="btn btn-sm absolute right-4 top-4" :aria-label="theme === 'dark' ? 'Chuyển nền sáng' : 'Chuyển nền tối'" @click="doiGiaoDien()">
      {{ theme === "dark" ? "Nền sáng" : "Nền tối" }}
    </button>
    <main id="main" class="brand-hero the" aria-labelledby="brand-title">
      <div class="flex items-center gap-3">
        <LogoMark :size="52" />
        <div>
          <p class="mo m-0">Nền tảng dịch vụ công</p>
          <h1 id="brand-title" class="m-0 text-[30px] leading-tight sm:text-[38px]">DX-OS Open-Core</h1>
        </div>
      </div>
      <p class="brand-tagline">Nền tảng cấp phép xây dựng số, bảo mật và minh bạch.</p>
      <div class="brand-actions">
        <button type="button" class="brand-choice" @click="login()">
          <span class="brand-choice-icon" aria-hidden="true">🏠</span>
          <span><b>Dành cho công dân</b><span>Nộp hồ sơ, theo dõi tiến độ và nhận kết quả.</span></span>
        </button>
        <button type="button" class="brand-choice" @click="login()">
          <span class="brand-choice-icon" aria-hidden="true">🏛️</span>
          <span><b>Dành cho cán bộ</b><span>Tiếp nhận, thẩm định và phê duyệt hồ sơ.</span></span>
        </button>
      </div>
      <div class="mt-6 flex flex-wrap items-center gap-3 text-sm">
        <button type="button" class="btn-chinh min-h-[44px]" @click="login()">Đăng nhập</button>
        <a class="btn inline-flex min-h-[44px]" href="/kiem-tra/" target="_blank" rel="noopener">Tra cứu công khai</a>
        <a class="btn inline-flex min-h-[44px]" href="/dieu-hanh/" target="_blank" rel="noopener">Bảng điều hành</a>
      </div>
      <p class="mt-6 mb-0 text-xs text-phu">DX-OS Open-Core v1.0.0 · Mã nguồn mở AGPL-3.0</p>
    </main>
  </div>

  <div v-else-if="trang === 'khong_quyen'" class="the m-6 p-6">
    <h1 class="tieu-de-trang">Không có quyền</h1>
    <p class="text-phu mt-2">Tài khoản không có vai trò chủ đầu tư hoặc cán bộ cấp phép.</p>
    <button class="btn mt-4" @click="logout()">Đăng xuất</button>
  </div>

  <div v-else class="min-h-screen">
    <Navbar
      :tab="tab"
      :tabs="TABS"
      :ten-nguoi-dung="tenNguoiDung"
      :chua-doc="thongBao.chuaDoc.value"
      :danh-sach="thongBao.danhSach.value"
      :trang-thai-ket-noi="thongBao.trangThai.value"
      @chuyen-tab="(ma: string) => (tab = ma)"
      @da-doc="thongBao.danhDauDaDoc()"
      @doc-mot="thongBao.danhDauMot"
      @dang-xuat="logout()"
    />

    <!-- v-show giữ trạng thái màn hình khi chuyển tab -->
    <main id="main" class="mx-auto max-w-7xl space-y-4 p-4">
      <div v-for="f in FEATURES_HIEN" v-show="tab === f.ma" :key="f.ma"><component :is="f.component" /></div>
    </main>
  </div>

  <CreateDossierModal
    v-if="moNop"
    :submitting="cd.dangGui.value"
    :requirements="cd.requirements.value"
    :errors="cd.docErrors.value"
    :loading-requirements="cd.dangTaiGiayTo.value"
    @close="moNop = false"
    @submit="nopHoSo"
  />
  <DetailDossierModal
    v-if="hoSoChiTiet"
    :dossier="hoSoChiTiet"
    :user-token="accessToken"
    @close="hoSoChiTiet = null"
    @supplement="moBoSung"
  />
  <SupplementModal
    v-if="hoSoBoSung"
    :dossier="hoSoBoSung"
    :submitting="cd.dangGui.value"
    @close="hoSoBoSung = null"
    @submit="guiBoSung"
  />
  <Forbidden403Modal
    v-if="biChan"
    :ma-ho-so="biChan.ma"
    @close="biChan = null"
    @request-break-glass="chuyenSangXinKhan"
  />
  <BreakGlassModal
    v-if="xinKhan"
    :ho-so-id="xinKhan.id"
    :ma-ho-so="xinKhan.ma"
    :submitting="cd.dangGui.value"
    @close="xinKhan = null"
    @confirm="guiXinKhan"
  />
</template>

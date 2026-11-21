<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { getUser, getValidToken, handleCallbackIfNeeded, login, logout, readRoles, readTenant } from "./auth";
import { useNotifications } from "./composables/useNotifications";
import { useCongDan } from "./composables/useCongDan";
import { batAnhSang } from "./utils/anhSang";
import type { DocEntry, HoSo, NopHoSoPayload } from "./types";
import Navbar from "./components/Navbar.vue";
import LogoMark from "./components/LogoMark.vue";
import ToastHost from "./components/ToastHost.vue";
import { APP_VERSION, SOURCE_URL } from "./config";
import { tenDonVi } from "./utils/labels";
import CreateDossierModal from "./components/CreateDossierModal.vue";
import DetailDossierModal from "./components/DetailDossierModal.vue";
import SupplementModal from "./components/SupplementModal.vue";
import Forbidden403Modal from "./components/Forbidden403Modal.vue";
import BreakGlassModal from "./components/BreakGlassModal.vue";
import GlobalSearch from "./components/GlobalSearch.vue";
import { tabsChoVai } from "./features/registry";
import { provideFeatureContext } from "./features/context";
import { laCanBo as coVaiCanBo, laChuDauTu as coVaiChuDauTu } from "./features/roles";

type TrangThai = "dang_kiem_tra" | "chua_dang_nhap" | "khong_quyen" | "ok";
const trang = ref<TrangThai>("dang_kiem_tra");
const tenNguoiDung = ref("");
const subNguoiDung = ref<string | undefined>(undefined);
const vaiTro = ref<string[]>([]);
const accessToken = ref<string | undefined>(undefined);
const tenant = ref("");
const donVi = computed(() => tenDonVi(tenant.value) || "Hệ thống cấp phép");

const coBangDieuHanh = computed(() =>
  vaiTro.value.some((r) => ["dx:auditor", "dx:tenant-admin", "dx:platform-admin", "dx:dpo"].includes(r)),
);
const laCanBo = computed(() => coVaiCanBo(vaiTro.value));
const laChuDauTu = computed(() => coVaiChuDauTu(vaiTro.value));

// Tab theo vai lấy từ features/registry.ts; thêm màn hình mới không cần sửa tệp này
const FEATURES_HIEN = computed(() => tabsChoVai(vaiTro.value));
const TABS = computed(() => FEATURES_HIEN.value.map((f) => ({ ma: f.ma, ten: f.ten })));
const thongBao = useNotifications(() => subNguoiDung.value);
const cd = useCongDan(getValidToken, () => subNguoiDung.value);

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
const moTimKiem = ref(false);

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

async function moHoSoTuTimKiem(id: string): Promise<void> {
  moTimKiem.value = false;
  // Đóng hộp thoại cũ trước để các panel (360, cảnh báo, nhật ký) nạp lại theo hồ sơ mới.
  hoSoChiTiet.value = null;
  await nextTick();
  await moHoSo(id);
}

function onPhimTat(e: KeyboardEvent): void {
  if (trang.value !== "ok") return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    moTimKiem.value = !moTimKiem.value;
  }
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
  // Đặt tên trước khi kiểm vai: thanh trên cùng hiện "Đăng xuất" cả khi tài khoản không có vai cấp phép
  tenNguoiDung.value = (user.profile?.name as string) || (user.profile?.preferred_username as string) || "";
  if (!laCanBo.value && !laChuDauTu.value) {
    trang.value = "khong_quyen";
    return;
  }
  subNguoiDung.value = user.profile?.sub as string | undefined;
  accessToken.value = user.access_token;
  tenant.value = readTenant(user.access_token);
  tab.value = docTabTuUrl();
  trang.value = "ok";
  thongBao.batDau();
  if (laChuDauTu.value) await cd.taiHoSo();
});

onMounted(() => document.addEventListener("keydown", onPhimTat));
onUnmounted(() => document.removeEventListener("keydown", onPhimTat));
</script>

<template>
  <a
    href="#main"
    class="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded focus:bg-white focus:px-4 focus:py-2 focus:text-slate-900"
  >Bỏ qua điều hướng</a>
  <ToastHost />

  <div class="flex min-h-screen max-w-full flex-col overflow-x-hidden">
    <Navbar
      :tab="tab"
      :tabs="trang === 'ok' ? TABS : []"
      :ten-nguoi-dung="trang === 'ok' ? tenNguoiDung : ''"
      :chua-doc="thongBao.chuaDoc.value"
      :danh-sach="thongBao.danhSach.value"
      :trang-thai-ket-noi="thongBao.trangThai.value"
      :vai-tro="vaiTro"
      :don-vi="donVi"
      @chuyen-tab="(ma: string) => (tab = ma)"
      @da-doc="thongBao.danhDauDaDoc()"
      @doc-mot="thongBao.danhDauMot"
      @mo-tim-kiem="moTimKiem = true"
      @dang-xuat="logout()"
      @dang-nhap="login()"
    />

    <main v-if="trang === 'dang_kiem_tra'" id="main" class="flex-1 py-20 text-center text-phu" role="status">
      Đang kiểm tra đăng nhập...
    </main>

    <main v-else-if="trang === 'chua_dang_nhap'" id="main" class="w-full flex-1">
      <div class="login-shell">
        <section class="brand-hero the" aria-labelledby="brand-title">
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
              <span class="brand-choice-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-7 9 7" /><path d="M5 10v10h14V10" /><path d="M10 20v-5h4v5" /></svg></span>
              <span><b>Dành cho công dân</b><span>Nộp hồ sơ, theo dõi tiến độ và nhận kết quả.</span></span>
            </button>
            <button type="button" class="brand-choice" @click="login()">
              <span class="brand-choice-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-5 9 5" /><path d="M4 9h16" /><path d="M6 9v9" /><path d="M10 9v9" /><path d="M14 9v9" /><path d="M18 9v9" /><path d="M3 20h18" /></svg></span>
              <span><b>Dành cho cán bộ</b><span>Tiếp nhận, thẩm định và phê duyệt hồ sơ.</span></span>
            </button>
          </div>
          <div class="mt-6 flex flex-wrap items-center gap-3 text-sm">
            <button type="button" class="btn btn-chinh min-h-[44px]" @click="login()">Đăng nhập với tài khoản của bạn</button>
            <a class="btn inline-flex min-h-[44px]" href="/kiem-tra/" target="_blank" rel="noopener">Tra cứu công khai</a>
            <a class="btn inline-flex min-h-[44px]" href="/dieu-hanh/" target="_blank" rel="noopener">Bảng điều hành</a>
          </div>
          <p class="mt-6 mb-0 text-xs text-phu">DX-OS Open-Core {{ APP_VERSION }} · Mã nguồn mở AGPL-3.0</p>
        </section>
      </div>
    </main>

    <main v-else-if="trang === 'khong_quyen'" id="main" class="mx-auto my-12 w-full max-w-[600px] px-4">
      <section class="the p-8 sm:p-10">
        <h1 class="tieu-de-trang">Không có quyền</h1>
        <p class="mt-2 text-phu">Tài khoản không có vai trò chủ đầu tư hoặc cán bộ cấp phép.</p>
        <p v-if="coBangDieuHanh" class="mt-2 text-phu">Vai của bạn làm việc trên bảng điều hành (chỉ số, kiểm toán, quản trị).</p>
        <div class="mt-4 flex flex-wrap gap-2">
          <a v-if="coBangDieuHanh" class="btn btn-chinh" href="/dieu-hanh/">Mở bảng điều hành</a>
          <button class="btn" @click="logout()">Đăng xuất</button>
        </div>
      </section>
    </main>

    <main v-else id="main" class="mx-auto w-full max-w-[1320px] flex-1 space-y-4 px-4 py-6 sm:px-6">
      <div v-for="f in FEATURES_HIEN" v-show="tab === f.ma" :key="f.ma"><component :is="f.component" /></div>
    </main>

    <footer class="mx-auto flex w-full max-w-[1320px] flex-wrap justify-between gap-2 px-4 pb-6 pt-2 text-[12.5px] text-phu sm:px-6">
      <span>Hệ thống cấp phép xây dựng, DX-OS Open-Core {{ APP_VERSION }}</span>
      <span>Phát hành theo giấy phép AGPL-3.0. <a :href="SOURCE_URL" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">Mã nguồn</a></span>
    </footer>
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
  <GlobalSearch
    v-if="moTimKiem"
    :token="accessToken || ''"
    @close="moTimKiem = false"
    @mo-ho-so="moHoSoTuTimKiem"
  />
</template>

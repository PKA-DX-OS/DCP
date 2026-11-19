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
import ToastHost from "./components/ToastHost.vue";
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
  <ToastHost />

  <div v-if="trang === 'dang_kiem_tra'" class="p-6 text-phu">Đang kiểm tra đăng nhập...</div>

  <div v-else-if="trang === 'chua_dang_nhap'" class="the m-6 p-6">
    <h1 class="tieu-de-trang">Cần đăng nhập</h1>
    <p class="text-phu mt-2">Người dân nộp và theo dõi hồ sơ; cán bộ phường xử lý hồ sơ được giao.</p>
    <div class="mt-4 flex flex-wrap gap-2">
      <button class="btn-chinh" @click="login()">Đăng nhập</button>
      <a class="btn inline-flex" href="/kiem-tra/" target="_blank" rel="noopener">Tra cứu công khai</a>
    </div>
  </div>

  <div v-else-if="trang === 'khong_quyen'" class="the m-6 p-6">
    <h1 class="tieu-de-trang">Không có quyền</h1>
    <p class="text-phu mt-2">Tài khoản không có vai trò chủ đầu tư hoặc cán bộ cấp phép.</p>
    <button class="btn mt-4" @click="logout()">Đăng xuất</button>
  </div>

  <div v-else class="mx-auto max-w-6xl space-y-4 p-4">
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
    <main>
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

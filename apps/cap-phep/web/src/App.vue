<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { getUser, handleCallbackIfNeeded, login, logout, readRoles } from "./auth";
import { useNotifications } from "./composables/useNotifications";
import { batAnhSang } from "./utils/anhSang";
import Navbar from "./components/Navbar.vue";
import ToastHost from "./components/ToastHost.vue";
import WorkspaceView from "./views/WorkspaceView.vue";
import ConstructionView from "./views/ConstructionView.vue";

type TrangThai = "dang_kiem_tra" | "chua_dang_nhap" | "khong_quyen" | "ok";
const trang = ref<TrangThai>("dang_kiem_tra");
const tenNguoiDung = ref("");
const subNguoiDung = ref<string | undefined>(undefined);

// Cán bộ cấp phép; chủ đầu tư là công dân và dùng giao diện khác
const VAI_CAN_BO = ["app:cap-phep:mot-cua", "app:cap-phep:tham-dinh", "app:cap-phep:lanh-dao", "app:cap-phep:trat-tu-xd"];

const TABS = [
  { ma: "ban-lam-viec", ten: "Bàn làm việc" },
  { ma: "cong-trinh", ten: "Công trình" },
];
const KHOA_URL = "tab";
const tab = ref<string>(docTabTuUrl());

function docTabTuUrl(): string {
  const t = new URL(window.location.href).searchParams.get(KHOA_URL);
  return TABS.some((x) => x.ma === t) ? (t as string) : TABS[0].ma;
}

// Đồng bộ tab với URL bằng replaceState để không làm dày lịch sử
watch(tab, (v) => {
  const u = new URL(window.location.href);
  u.searchParams.set(KHOA_URL, v);
  window.history.replaceState(window.history.state, "", u.toString());
});

const thongBao = useNotifications(() => subNguoiDung.value);

onMounted(async () => {
  batAnhSang();
  await handleCallbackIfNeeded();
  const user = await getUser();
  if (!user || user.expired) {
    trang.value = "chua_dang_nhap";
    return;
  }
  const roles = readRoles(user.access_token);
  if (!roles.some((r) => VAI_CAN_BO.includes(r))) {
    trang.value = "khong_quyen";
    return;
  }
  tenNguoiDung.value = (user.profile?.name as string) || (user.profile?.preferred_username as string) || "";
  subNguoiDung.value = user.profile?.sub as string | undefined;
  trang.value = "ok";
  thongBao.batDau();
});
</script>

<template>
  <ToastHost />

  <div v-if="trang === 'dang_kiem_tra'" class="p-6 text-phu">Đang kiểm tra đăng nhập...</div>

  <div v-else-if="trang === 'chua_dang_nhap'" class="the m-6 p-6">
    <h1 class="tieu-de-trang">Cần đăng nhập</h1>
    <button class="btn-chinh mt-4" @click="login()">Đăng nhập</button>
  </div>

  <div v-else-if="trang === 'khong_quyen'" class="the m-6 p-6">
    <h1 class="tieu-de-trang">Không có quyền</h1>
    <p class="text-phu mt-2">Tài khoản không có vai trò cán bộ cấp phép.</p>
    <button class="btn mt-4" @click="logout()">Đăng xuất</button>
  </div>

  <div v-else class="mx-auto max-w-6xl space-y-4 p-4">
    <Navbar
      :tab="tab"
      :tabs="TABS"
      :ten-nguoi-dung="tenNguoiDung"
      :chua-doc="thongBao.chuaDoc.value"
      :trang-thai-ket-noi="thongBao.trangThai.value"
      @chuyen-tab="(ma: string) => (tab = ma)"
      @da-doc="thongBao.danhDauDaDoc()"
      @dang-xuat="logout()"
    />

    <!-- v-show giữ trạng thái màn hình khi chuyển tab -->
    <main>
      <div v-show="tab === 'ban-lam-viec'"><WorkspaceView /></div>
      <div v-show="tab === 'cong-trinh'"><ConstructionView /></div>
    </main>
  </div>
</template>
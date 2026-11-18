<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { getUser, getValidToken, readRoles } from "../auth";
import { createInspection, fetchCongTrinh, fetchPhieuKiemTra } from "../api/construction";
import { notify } from "../composables/useToast";

// Quyền lập phiếu: trật tự xây dựng hoặc lãnh đạo (theo app.yaml và permissions.js)
const VAI_LAP_PHIEU = [
  "app:cap-phep:trat-tu-xd",
  "app:cap-phep:lanh-dao",
  "trat-tu-xay-dung",
  "lanh-dao",
];

const congTrinh = ref<any[]>([]);
const phieu = ref<any[]>([]);
const dangTai = ref(false);
const loi = ref("");
const quyenLapPhieu = ref(false);
const chon = ref<string | null>(null);

const phieuCuaChon = computed(() => phieu.value.filter((p) => p.cong_trinh_id === chon.value));

async function taiDuLieu(): Promise<void> {
  dangTai.value = true;
  loi.value = "";
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    const [ct, pk] = await Promise.all([fetchCongTrinh(t), fetchPhieuKiemTra(t)]);
    congTrinh.value = ct;
    phieu.value = pk;
  } catch (e) {
    loi.value = e instanceof Error ? e.message : "Không tải được công trình";
  } finally {
    dangTai.value = false;
  }
}

async function lapPhieu(congTrinhId: string): Promise<void> {
  if (!quyenLapPhieu.value) {
    notify("Bạn không có quyền lập phiếu kiểm tra", "loi");
    return;
  }
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    await createInspection(t, congTrinhId);
    notify("Đã lập phiếu kiểm tra", "ok");
    await taiDuLieu();
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không lập được phiếu", "loi");
  }
}

onMounted(async () => {
  const user = await getUser();
  const roles = readRoles(user?.access_token);
  quyenLapPhieu.value = roles.some((r) => VAI_LAP_PHIEU.includes(r));
  await taiDuLieu();
});
</script>

<template>
  <section class="space-y-4">
    <div>
      <h2 class="tieu-de-trang">Công trình</h2>
      <p class="text-phu mt-1">Trạng thái công trình và phiếu kiểm tra hậu kiểm.</p>
    </div>

    <p v-if="dangTai" class="text-phu" role="status">Đang tải công trình...</p>

    <div v-else-if="loi" class="the p-4">
      <p class="canh-bao">{{ loi }}</p>
      <button class="btn mt-2" @click="taiDuLieu()">Thử lại</button>
    </div>

    <p v-else-if="!congTrinh.length" class="the p-4 text-phu">Chưa có công trình nào.</p>

    <ul v-else class="space-y-3">
      <li v-for="c in congTrinh" :key="c.id" class="the p-4">
        <div class="flex flex-wrap items-center gap-3">
          <div class="min-w-0 flex-1">
            <div class="font-semibold">{{ c.ma_cong_trinh }}</div>
            <div class="goi-y">{{ c.dia_chi }}</div>
          </div>
          <button class="btn-sm" @click="chon = chon === c.id ? null : c.id">
            {{ chon === c.id ? "Ẩn phiếu" : "Xem phiếu" }}
          </button>
          <button v-if="quyenLapPhieu" class="btn-sm" @click="lapPhieu(c.id)">Lập phiếu</button>
        </div>

        <ul v-if="chon === c.id" class="mt-3 space-y-1 border-t border-vien-nhat pt-3 text-sm">
          <li v-for="p in phieuCuaChon" :key="p.id">
            {{ p.ma_phieu || p.id }} · {{ p.loai_vi_pham || "Kiểm tra định kỳ" }} · {{ p.trang_thai }}
          </li>
          <li v-if="!phieuCuaChon.length" class="text-phu">Chưa có phiếu kiểm tra.</li>
        </ul>
      </li>
    </ul>
  </section>
</template>
<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { getUser, getValidToken, readRoles } from "../auth";
import { createInspection, fetchCongTrinh, fetchPhieuKiemTra, triggerDemoSensor } from "../api/construction";
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
const dangGuiCamBien = ref<string | null>(null);
const nguonLoc = ref<"tat-ca" | "cam_bien" | "chu_dong">("tat-ca");

function coCanhBao(c: any): boolean {
  const a = c?.canh_bao_gan_nhat;
  if (!a || a.chi_so === "kiem_tra_dinh_ky") return false;
  return Number(a.nguong) > 0;
}

function tenChiSo(value: string): string {
  return { laeq_dba: "Độ ồn LAeq", do_bui: "Bụi", rung_cham: "Rung chấn" }[value] || value || "Chỉ số";
}

const phieuCuaChon = computed(() => phieu.value.filter((p) => p.cong_trinh_id === chon.value));
const phieuLoc = computed(() =>
  phieu.value.filter((p) => nguonLoc.value === "tat-ca" || p.nguon === nguonLoc.value),
);
const soCanhBaoCamBien = computed(() => phieu.value.filter((p) => p.nguon === "cam_bien").length);

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

async function guiSoDo(c: any): Promise<void> {
  if (!quyenLapPhieu.value) {
    notify("Bạn không có quyền gửi số đo cảm biến", "loi");
    return;
  }
  dangGuiCamBien.value = c.id;
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    await triggerDemoSensor(t, c.ma_cong_trinh);
    notify(`Đã gửi số đo 86,5 dBA cho công trình ${c.ma_cong_trinh}`, "ok");
    await taiDuLieu();
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không gửi được số đo cảm biến", "loi");
  } finally {
    dangGuiCamBien.value = null;
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

    <template v-else>
    <section class="mt-6" aria-labelledby="tieu-de-phieu-kiem-tra">
      <div class="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 id="tieu-de-phieu-kiem-tra" class="text-[15px] font-semibold m-0">Phiếu kiểm tra hiện trường</h3>
          <p class="m-0 mt-1 text-[12.5px] text-phu">{{ phieu.length }} phiếu · {{ soCanhBaoCamBien }} cảnh báo cảm biến</p>
        </div>
        <div class="flex flex-wrap gap-1.5" role="group" aria-label="Lọc nguồn phiếu kiểm tra">
          <button type="button" class="btn btn-sm" :class="nguonLoc === 'tat-ca' && 'btn-chinh'" @click="nguonLoc = 'tat-ca'">Tất cả</button>
          <button type="button" class="btn btn-sm" :class="nguonLoc === 'cam_bien' && 'btn-chinh'" @click="nguonLoc = 'cam_bien'">Cảnh báo cảm biến</button>
          <button type="button" class="btn btn-sm" :class="nguonLoc === 'chu_dong' && 'btn-chinh'" @click="nguonLoc = 'chu_dong'">Kiểm tra chủ động</button>
        </div>
      </div>
      <div class="the overflow-hidden">
        <div class="overflow-x-auto">
          <table id="table-phieu-kiem-tra" class="bang w-full text-[13px]">
            <thead>
              <tr>
                <th>Công trình</th>
                <th>Địa chỉ</th>
                <th>Nguồn</th>
                <th>Người kiểm tra</th>
                <th>Kết luận</th>
                <th>Biên bản</th>
                <th>Ngày lập</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in phieuLoc" :key="p.id">
                <td class="whitespace-nowrap font-medium">{{ p.ma_cong_trinh || "—" }}</td>
                <td class="max-w-[240px]">{{ p.dia_chi || "—" }}</td>
                <td class="whitespace-nowrap">{{ p.nguon === "cam_bien" ? "Cảnh báo cảm biến" : "Kiểm tra chủ động" }}</td>
                <td class="whitespace-nowrap">{{ p.nguoi_kiem_tra_ten || "Chưa phân công" }}</td>
                <td class="whitespace-nowrap">
                  <span :class="p.ket_luan === 'Có vi phạm' ? 'tt tt-do' : p.ket_luan ? 'tt tt-xanh' : 'tt tt-xam'">
                    {{ p.ket_luan || "Chờ kiểm tra" }}
                  </span>
                </td>
                <td class="whitespace-nowrap">
                  <span v-if="p.bien_ban_file_id" class="text-xanh">Đã có</span>
                  <span v-else class="text-phu">Chưa có</span>
                </td>
                <td class="whitespace-nowrap text-phu">{{ p.created_at ? new Date(p.created_at).toLocaleString("vi-VN") : "—" }}</td>
              </tr>
              <tr v-if="!phieuLoc.length">
                <td colspan="7" class="py-6 text-center text-phu">
                  {{ nguonLoc === "tat-ca" ? "Chưa có phiếu kiểm tra nào." : "Không có phiếu thuộc nguồn đang lọc." }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <p v-if="!congTrinh.length" class="the p-4 text-phu">Chưa có công trình nào.</p>
    <ul v-else class="space-y-3">
      <li v-for="c in congTrinh" :key="c.id" class="the p-4">
        <div class="flex flex-wrap items-center gap-3">
          <div class="min-w-0 flex-1">
            <div class="font-semibold">{{ c.ma_cong_trinh }}</div>
            <div class="goi-y">{{ c.dia_chi }}</div>
            <div v-if="coCanhBao(c)" class="mt-1 text-[12.5px] text-son">
              Cảnh báo {{ tenChiSo(c.canh_bao_gan_nhat.chi_so) }}: {{ c.canh_bao_gan_nhat.gia_tri }} (ngưỡng {{ c.canh_bao_gan_nhat.nguong }})
            </div>
          </div>
          <button class="btn-sm" @click="chon = chon === c.id ? null : c.id">
            {{ chon === c.id ? "Ẩn phiếu" : "Xem phiếu" }}
          </button>
          <button v-if="quyenLapPhieu" class="btn-sm" :disabled="dangGuiCamBien === c.id" @click="guiSoDo(c)">
            {{ dangGuiCamBien === c.id ? "Đang gửi…" : "Gửi số đo thử" }}
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
    </template>
  </section>
</template>
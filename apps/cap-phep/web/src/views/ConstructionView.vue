<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <section>
    <div class="flex flex-wrap items-end gap-4 mb-6">
      <div>
        <h1 class="tieu-de-trang">Công trình và hậu kiểm</h1>
        <p class="text-phu text-[16px] mt-2 mb-0">Công trình đã cấp phép đang thi công, cảnh báo từ cảm biến và phiếu kiểm tra hiện trường.</p>
      </div>
      <div class="flex-1"></div>
      <button type="button" class="btn" @click="$emit('refresh')">Làm mới</button>
    </div>

    <div class="the overflow-hidden">
      <div class="overflow-x-auto">
        <table class="bang" id="table-cong-trinh">
          <thead>
            <tr>
              <th>Mã công trình</th>
              <th>Hồ sơ</th>
              <th>Địa chỉ</th>
              <th>Thi công</th>
              <th>Cảnh báo gần nhất</th>
              <th v-if="canAct"><span class="sr-only">Thao tác</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in constructionList" :key="c.id">
              <td class="whitespace-nowrap font-medium">{{ c.ma_cong_trinh }}</td>
              <td class="ma whitespace-nowrap">{{ c.ma_ho_so || "" }}</td>
              <td class="max-w-[260px]">{{ c.dia_chi || "" }}</td>
              <td class="whitespace-nowrap"><span class="tt tt-lam">{{ trangThaiThiCong(c.trang_thai_thi_cong) }}</span></td>
              <td>
                <template v-if="c.canh_bao_gan_nhat">
                  <span class="text-son font-medium">Cảnh báo {{ tenChiSo(c.canh_bao_gan_nhat.chi_so) }}: {{ formatNumberVi(c.canh_bao_gan_nhat.gia_tri, 1) }} dBA</span>
                  <div class="mo">Ngưỡng {{ formatNumberVi(c.canh_bao_gan_nhat.nguong, 1) }} dBA, {{ ngayGio(c.canh_bao_gan_nhat.created_at) }}</div>
                </template>
                <span v-else class="text-phu">Không có</span>
              </td>
              <td v-if="canAct" class="text-right whitespace-nowrap">
                <button
                  type="button"
                  :id="'btn-demo-sensor-' + c.ma_cong_trinh"
                  class="btn-demo-sensor btn btn-sm mr-1.5"
                  title="Chỉ có ở môi trường thử nghiệm: gửi số đo 86,5 dBA cho công trình này"
                  @click="$emit('demo-sensor', c.ma_cong_trinh)"
                >Gửi số đo thử</button>
                <button
                  type="button"
                  :id="'btn-create-inspection-' + c.ma_cong_trinh"
                  class="btn-create-inspection btn btn-sm"
                  @click="$emit('create-inspection', c)"
                >Tạo phiếu kiểm tra</button>
              </td>
            </tr>
            <tr v-if="constructionList.length === 0">
              <td :colspan="canAct ? 6 : 5" class="text-center text-phu py-8">Chưa có công trình nào đang thi công trong địa bàn của bạn.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <h2 class="text-[17px] font-semibold mt-8 mb-3">Phiếu kiểm tra hiện trường</h2>
    <div class="the overflow-hidden">
      <div class="overflow-x-auto">
        <table class="bang" id="table-phieu-kiem-tra">
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
            <tr v-for="p in inspectionList" :key="p.id">
              <td class="whitespace-nowrap font-medium">{{ p.ma_cong_trinh || p.cong_trinh_ma || "" }}</td>
              <td class="max-w-[240px]">{{ p.dia_chi || "" }}</td>
              <td class="whitespace-nowrap">{{ p.nguon === "cam_bien" ? "Cảnh báo cảm biến" : "Kiểm tra chủ động" }}</td>
              <td class="whitespace-nowrap">{{ p.nguoi_kiem_tra_ten || "Chưa phân công" }}</td>
              <td class="whitespace-nowrap">
                <span :class="p.ket_luan === 'Có vi phạm' ? 'tt tt-do' : p.ket_luan ? 'tt tt-xanh' : 'tt tt-xam'">{{ p.ket_luan || "Chờ kiểm tra" }}</span>
              </td>
              <td class="whitespace-nowrap">
                <button v-if="p.bien_ban_file_id" type="button" class="btn-lien-ket" @click="viewBienBan(p.bien_ban_file_id)">Xem biên bản</button>
                <span v-else class="text-phu">Chưa có</span>
              </td>
              <td class="whitespace-nowrap text-phu">{{ ngayNgan(p.created_at) }}</td>
            </tr>
            <tr v-if="inspectionList.length === 0">
              <td colspan="7" class="text-center text-phu py-8">Chưa có phiếu kiểm tra nào.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { formatNumberVi } from "../utils/formatters";
import { ngayGio, ngayNgan } from "../utils/labels";
import { notify } from "../composables/useToast";

const props = defineProps<{
  constructionList: any[];
  inspectionList: any[];
  userRoles?: string[];
  userToken?: string;
}>();

// U-07: tải biên bản kèm token đăng nhập (liên kết trần sẽ luôn bị 401)
async function viewBienBan(fileId: string) {
  if (!props.userToken) return;
  try {
    const resp = await fetch(`/api/v1/files/${fileId}/download`, {
      headers: { Authorization: `Bearer ${props.userToken}` },
    });
    if (!resp.ok) {
      notify(`Không mở được biên bản (mã lỗi ${resp.status}).`, "loi");
      return;
    }
    const url = window.URL.createObjectURL(await resp.blob());
    window.open(url, "_blank");
    setTimeout(() => window.URL.revokeObjectURL(url), 60000);
  } catch (err: any) {
    notify(`Không mở được biên bản: ${err.message}`, "loi");
  }
}

defineEmits<{
  (e: "refresh"): void;
  (e: "create-inspection", construction: any): void;
  (e: "demo-sensor", maCongTrinh: string): void;
}>();

function trangThaiThiCong(v: string | undefined): string {
  const map: Record<string, string> = { DANG_THI_CONG: "Đang thi công", TAM_DUNG: "Tạm dừng", HOAN_THANH: "Hoàn thành" };
  return (v && map[v]) || v || "Đang thi công";
}

function tenChiSo(v: string | undefined): string {
  const map: Record<string, string> = { laeq_dba: "tiếng ồn", pm10: "bụi PM10", pm25: "bụi PM2.5" };
  return (v && map[v]) || v || "";
}

const canAct = computed(() => {
  const roles = props.userRoles || [];
  return (
    roles.includes("app:cap-phep:trat-tu-xd") ||
    roles.includes("dx:tenant-admin") ||
    roles.includes("dx:platform-admin")
  );
});
</script>

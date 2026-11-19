<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { getUser, getValidToken, readRoles } from "../auth";
import { fetchTasks } from "../api/flow";
import { useDossierActions, type NguoiDung } from "../composables/useDossierActions";
import type { FlowTask } from "../types";

type BoLoc = "tat-ca" | "qua-han" | "sap-han";
type LoaiViec = "tat-ca" | "tiep-nhan" | "tham-dinh" | "phe-duyet" | "nghiem-thu" | "khac";

const nguoi = ref<NguoiDung | null>(null);
const tasks = ref<FlowTask[]>([]);
const dangTai = ref(false);
const loi = ref("");
const boLoc = ref<BoLoc>("tat-ca");
const loaiViec = ref<LoaiViec>("tat-ca");
const dangLam = ref<string | null>(null);

const actions = useDossierActions(getValidToken, () => nguoi.value);
const emit = defineEmits<{ (e: "mo-ho-so", idHoacMa: string, ma: string): void }>();

function bien(t: FlowTask, ten: string): any {
  return ((t.variables as any[] | undefined) || []).find((v: any) => v.name === ten)?.value;
}

function thongTin(t: FlowTask): { id: string; ma: string; diaChi: string; trangThai: string; uuTien: string } {
  const ma = bien(t, "ma_ho_so") || t.businessKey || "";
  const id = bien(t, "ho_so_id") || ma;
  return {
    id,
    ma,
    diaChi: bien(t, "dia_chi_cong_trinh") || "",
    trangThai: bien(t, "trang_thai_ho_so") || "",
    uuTien: bien(t, "do_uu_tien") || "binh_thuong",
  };
}

function hanCuaViec(t: FlowTask): number | null {
  return t.dueDate ? new Date(t.dueDate).getTime() : null;
}

function nhomViec(t: FlowTask): LoaiViec {
  const key = t.taskDefinitionKey || "";
  if (key === "taskKiemTraHopLe" || key === "taskChoBoSung") return "tiep-nhan";
  if (key.startsWith("taskThamDinh") || key === "taskPhanCong" || key === "taskKiemTraQuyHoach") return "tham-dinh";
  if (key === "taskDuyetCapPhep" || key === "taskPheDuyet") return "phe-duyet";
  if (key.startsWith("taskNghiemThu") || key === "taskHoanCong" || key === "taskKhacPhucMong") return "nghiem-thu";
  return "khac";
}

const danhSachLoc = computed(() => {
  const now = Date.now();
  const ngay = 24 * 3600 * 1000;
  return tasks.value.filter((t) => {
    const info = thongTin(t);
    if (!info.ma) return false;
    if (loaiViec.value !== "tat-ca" && nhomViec(t) !== loaiViec.value) return false;
    const han = hanCuaViec(t);
    if (boLoc.value === "qua-han") return han !== null && han < now;
    if (boLoc.value === "sap-han") return han !== null && han >= now && han - now <= ngay;
    return true;
  });
});

function mucUuTien(t: FlowTask): { nhan: string; lop: string } {
  const info = thongTin(t);
  const han = hanCuaViec(t);
  const now = Date.now();
  if (han !== null && han < now) return { nhan: "Quá hạn", lop: "tt tt-do" };
  if (han !== null && han - now <= 24 * 3600 * 1000) return { nhan: "Sắp hạn", lop: "tt tt-vang" };
  if (info.uuTien === "cao") return { nhan: "Ưu tiên cao", lop: "tt tt-lam" };
  return { nhan: "Bình thường", lop: "tt tt-xam" };
}

async function taiViec(): Promise<void> {
  dangTai.value = true;
  loi.value = "";
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    tasks.value = await fetchTasks(t);
  } catch (e) {
    loi.value = e instanceof Error ? e.message : "Không tải được việc";
  } finally {
    dangTai.value = false;
  }
}

async function hoanThanh(t: FlowTask): Promise<void> {
  dangLam.value = t.id;
  const ok = await actions.hoanThanhViec(t);
  dangLam.value = null;
  if (ok) await taiViec();
}

function dinhDangHan(t: FlowTask): string {
  const han = hanCuaViec(t);
  return han ? new Date(han).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "Không có hạn";
}

onMounted(async () => {
  const user = await getUser();
  const roles = readRoles(user?.access_token);
  nguoi.value = { sub: user?.profile?.sub as string | undefined, roles };
  await taiViec();
});

defineExpose({ taiViec });
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-end gap-3">
      <div class="min-w-0">
        <h2 class="tieu-de-trang">Bàn làm việc</h2>
        <p class="text-phu mt-1">Việc được giao cho bạn, có hạn xử lý và mức ưu tiên.</p>
      </div>
      <div class="flex-1"></div>
      <label class="nhan" for="loc-viec">Hạn</label>
      <select id="loc-viec" v-model="boLoc" class="o">
        <option value="tat-ca">Tất cả</option>
        <option value="qua-han">Quá hạn</option>
        <option value="sap-han">Sắp đến hạn (24 giờ)</option>
      </select>
      <label class="nhan" for="loc-loai-viec">Loại việc</label>
      <select id="loc-loai-viec" v-model="loaiViec" class="o">
        <option value="tat-ca">Tất cả</option>
        <option value="tiep-nhan">Tiếp nhận</option>
        <option value="tham-dinh">Thẩm định / quy hoạch</option>
        <option value="phe-duyet">Phê duyệt</option>
        <option value="nghiem-thu">Nghiệm thu</option>
        <option value="khac">Khác</option>
      </select>
      <button class="btn" @click="taiViec()">Làm mới</button>
    </div>

    <p v-if="dangTai" class="text-phu" role="status">Đang tải việc...</p>

    <div v-else-if="loi" class="the p-4">
      <p class="canh-bao">{{ loi }}</p>
      <button class="btn mt-2" @click="taiViec()">Thử lại</button>
    </div>

    <p v-else-if="!danhSachLoc.length" class="the p-4 text-phu">Không có việc nào cần xử lý.</p>

    <ul v-else class="space-y-3">
      <li v-for="t in danhSachLoc" :key="t.id" class="the p-4">
        <div class="flex flex-wrap items-start gap-3">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-semibold">{{ t.name || t.taskDefinitionKey || "Nhiệm vụ" }}</span>
              <span :class="mucUuTien(t).lop">{{ mucUuTien(t).nhan }}</span>
            </div>
            <div class="goi-y mt-1">
              Hồ sơ <b>{{ thongTin(t).ma }}</b><template v-if="thongTin(t).diaChi"> · {{ thongTin(t).diaChi }}</template>
            </div>
            <div class="goi-y">Hạn: {{ dinhDangHan(t) }}<template v-if="thongTin(t).trangThai"> · Trạng thái: {{ thongTin(t).trangThai }}</template></div>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="btn btn-sm" @click="emit('mo-ho-so', thongTin(t).id, thongTin(t).ma)">Xem &amp; xử lý</button>
            <button
              v-if="actions.laNguoiDuocGiao(t)"
              class="btn btn-sm btn-chinh"
              :disabled="dangLam === t.id"
              @click="hoanThanh(t)"
            >{{ dangLam === t.id ? "Đang xử lý..." : "Hoàn thành" }}</button>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>

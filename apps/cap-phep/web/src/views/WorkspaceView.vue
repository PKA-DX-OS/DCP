<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { getUser, getValidToken, readRoles } from "../auth";
import { fetchEscalations, fetchTasks, remindTask } from "../api/flow";
import { useDossierActions, type NguoiDung } from "../composables/useDossierActions";
import { notify } from "../composables/useToast";
import { EmptyState, Skeleton } from "../design-system";
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
const dangNhac = ref<string | null>(null);
const escalations = ref<any[]>([]);
const loadingEscalations = ref(false);

const actions = useDossierActions(getValidToken, () => nguoi.value);
const emit = defineEmits<{ (e: "mo-ho-so", idHoacMa: string, ma: string): void }>();
const laQuanLy = computed(() => (nguoi.value?.roles || []).some((r) => ["app:cap-phep:lanh-dao", "app:cap-phep:mot-cua", "dx:tenant-admin", "dx:platform-admin"].includes(r)));

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

function thongTinEsc(e: any): { id: string; ma: string; diaChi: string } {
  const v = (ten: string) => ((e?.variables as any[] | undefined) || []).find((x: any) => x.name === ten)?.value;
  return { id: v("ho_so_id") || "", ma: v("ma_ho_so") || e?.businessKey || "", diaChi: v("dia_chi_cong_trinh") || "" };
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
    if (laQuanLy.value) {
      loadingEscalations.value = true;
      try {
        const esc = await fetchEscalations(t, 24);
        escalations.value = Array.isArray(esc?.items) ? esc.items : [];
      } catch {
        escalations.value = [];
      } finally {
        loadingEscalations.value = false;
      }
    }
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

async function nhacViec(t: FlowTask): Promise<void> {
  dangNhac.value = t.id;
  try {
    const token = await getValidToken();
    if (!token) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    await remindTask(token, t.id);
    notify("Đã gửi nhắc việc cho cán bộ đang xử lý", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không gửi được nhắc việc", "loi");
  } finally {
    dangNhac.value = null;
  }
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

    <div v-if="dangTai" class="the p-4" role="status" aria-busy="true">
      <p class="sr-only">Đang tải việc…</p>
      <Skeleton :lines="5" height="2rem" />
    </div>

    <section v-if="laQuanLy && !dangTai && escalations.length" class="the p-4" aria-labelledby="tieu-de-qua-han">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
        <h3 id="tieu-de-qua-han" class="text-[14px] font-semibold m-0">Việc quá hạn / sắp hạn toàn địa bàn</h3>
        <span class="tt tt-do">{{ escalations.length }}</span>
      </div>
      <ul class="list-none m-0 p-0 text-[13px]">
        <li v-for="e in escalations.slice(0, 5)" :key="e.id" class="flex flex-wrap items-center justify-between gap-2 py-1 border-b border-vien-nhat">
          <span>
            {{ e.name || e.taskDefinitionKey }} · <b>{{ thongTinEsc(e).ma || "—" }}</b>
            <span v-if="thongTinEsc(e).diaChi"> · {{ thongTinEsc(e).diaChi }}</span>
          </span>
          <span :class="e.qua_han ? 'tt tt-do' : 'tt tt-vang'">{{ e.qua_han ? "Quá hạn" : `Còn ${e.con_lai_gio} giờ` }}</span>
        </li>
      </ul>
      <p v-if="escalations.length > 5" class="goi-y mt-2 mb-0">Hiển thị 5 việc gần hạn nhất trong {{ escalations.length }} việc.</p>
    </section>

    <div v-else-if="loi" class="the p-4">
      <p class="canh-bao">{{ loi }}</p>
      <button class="btn mt-2" @click="taiViec()">Thử lại</button>
    </div>

    <EmptyState
      v-else-if="!danhSachLoc.length"
      class="the p-4"
      title="Không có việc nào cần xử lý"
      description="Việc được giao từ quy trình sẽ xuất hiện ở đây."
    >
      <button type="button" class="btn min-h-[44px]" @click="taiViec()">Tải lại</button>
    </EmptyState>

    <ul v-else class="space-y-3">
      <li v-for="t in danhSachLoc" :key="t.id" class="the p-4">
        <div class="flex flex-wrap items-start gap-3">
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-semibold">{{ t.name || t.taskDefinitionKey || "Nhiệm vụ" }}</span>
              <span :class="mucUuTien(t).lop">{{ mucUuTien(t).nhan }}</span>
            </div>
            <div class="goi-y mt-1">
              Mã hồ sơ: <b>{{ thongTin(t).ma }}</b><template v-if="thongTin(t).diaChi"> · {{ thongTin(t).diaChi }}</template>
            </div>
            <div class="goi-y">Hạn: {{ dinhDangHan(t) }}<template v-if="thongTin(t).trangThai"> · Trạng thái: {{ thongTin(t).trangThai }}</template></div>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-if="laQuanLy && hanCuaViec(t) !== null && hanCuaViec(t)! < Date.now()"
              class="btn btn-sm text-vang"
              :disabled="dangNhac === t.id"
              @click="nhacViec(t)"
            >{{ dangNhac === t.id ? "Đang nhắc…" : "Nhắc việc" }}</button>
            <button class="btn btn-sm" @click="emit('mo-ho-so', thongTin(t).id, thongTin(t).ma)">Xem hồ sơ</button>
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

<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { getUser, getValidToken, readRoles } from "../auth";
import { fetchEscalations, fetchTasks, remindTask } from "../api/flow";
import { fetchDossierFiles, fetchDossierHistory, openHoSo } from "../api/dossiers";
import { useDossierActions, type NguoiDung } from "../composables/useDossierActions";
import { notify } from "../composables/useToast";
import { EmptyState, Skeleton } from "../design-system";
import DossierActionBar from "../components/DossierActionBar.vue";
import { formatStatus } from "../utils/formatters";
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

const selectedTask = ref<FlowTask | null>(null);
const selectedDossier = ref<any | null>(null);
const accessToken = ref("");
const files = ref<any[]>([]);
const audit = ref<any[]>([]);
const loadingDetail = ref(false);
const detailError = ref("");

const actions = useDossierActions(getValidToken, () => nguoi.value);
const emit = defineEmits<{ (e: "mo-ho-so", idHoacMa: string, ma: string): void }>();
const laQuanLy = computed(() =>
  (nguoi.value?.roles || []).some((r) =>
    ["app:cap-phep:lanh-dao", "app:cap-phep:mot-cua", "dx:tenant-admin", "dx:platform-admin"].includes(r),
  ),
);

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

function dinhDangHan(t: FlowTask): string {
  const han = hanCuaViec(t);
  return han ? new Date(han).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "Không có hạn";
}

function ngayGio(value: string | null): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "";
}

async function taiViec(): Promise<void> {
  dangTai.value = true;
  loi.value = "";
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    accessToken.value = t;
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

function fallbackDossier(t: FlowTask): any {
  const info = thongTin(t);
  return {
    id: info.id,
    ma_ho_so: info.ma,
    ho_ten: bien(t, "ho_ten") || "",
    cccd: bien(t, "cccd") || "",
    dien_thoai: bien(t, "dien_thoai") || "",
    tenant: bien(t, "tenant") || "",
    dia_chi_cong_trinh: info.diaChi,
    thua_dat: bien(t, "thua_dat") || "",
    so_tang: bien(t, "so_tang") || "",
    dien_tich_san_m2: bien(t, "dien_tich_san_m2") || "",
    trang_thai: info.trangThai,
    buoc: bien(t, "buoc") || "",
  };
}

async function taiChiTiet(): Promise<void> {
  if (!selectedTask.value) return;
  loadingDetail.value = true;
  detailError.value = "";
  files.value = [];
  audit.value = [];
  const info = thongTin(selectedTask.value);
  try {
    const t = accessToken.value || (await getValidToken()) || "";
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    accessToken.value = t;
    let d: any = null;
    try {
      d = await openHoSo(t, info.id || info.ma);
    } catch (e) {
      detailError.value = e instanceof Error ? e.message : "Không mở được chi tiết hồ sơ";
    }
    selectedDossier.value = d || fallbackDossier(selectedTask.value);
    if (d?.id) {
      const [f, a] = await Promise.allSettled([fetchDossierFiles(t, d.id), fetchDossierHistory(t, d.id)]);
      files.value = f.status === "fulfilled" ? f.value : [];
      audit.value = a.status === "fulfilled" ? a.value : [];
    }
  } catch (e) {
    detailError.value = e instanceof Error ? e.message : "Không tải được chi tiết";
    selectedDossier.value = fallbackDossier(selectedTask.value);
  } finally {
    loadingDetail.value = false;
  }
}

async function chonViec(t: FlowTask): Promise<void> {
  selectedTask.value = t;
  await taiChiTiet();
}

async function hoanThanh(t: FlowTask): Promise<void> {
  dangLam.value = t.id;
  const ok = await actions.hoanThanhViec(t);
  dangLam.value = null;
  if (ok) {
    await taiViec();
    await taiChiTiet();
  }
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

async function sauKhiXuLy(d: any): Promise<void> {
  if (d) selectedDossier.value = d;
  await taiViec();
  await taiChiTiet();
}

function moHoSoDayDu(): void {
  if (!selectedDossier.value) return;
  emit("mo-ho-so", selectedDossier.value.id || selectedDossier.value.ma_ho_so, selectedDossier.value.ma_ho_so || "");
}

onMounted(async () => {
  const user = await getUser();
  const roles = readRoles(user?.access_token);
  nguoi.value = { sub: user?.profile?.sub as string | undefined, roles };
  await taiViec();
  if (!selectedTask.value && danhSachLoc.value.length) await chonViec(danhSachLoc.value[0]);
});

defineExpose({ taiViec });
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-end gap-3">
      <div class="min-w-0">
        <h2 class="text-2xl font-bold text-slate-800">Bàn làm việc</h2>
        <p class="mt-1 text-sm text-slate-500">Hàng đợi công việc, chi tiết hồ sơ và thao tác xử lý trong một màn hình.</p>
      </div>
      <div class="flex-1"></div>
      <label class="text-xs font-semibold text-slate-600" for="loc-viec">Hạn</label>
      <select id="loc-viec" v-model="boLoc" class="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800">
        <option value="tat-ca">Tất cả</option>
        <option value="qua-han">Quá hạn</option>
        <option value="sap-han">Sắp đến hạn (24 giờ)</option>
      </select>
      <label class="text-xs font-semibold text-slate-600" for="loc-loai-viec">Loại việc</label>
      <select id="loc-loai-viec" v-model="loaiViec" class="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800">
        <option value="tat-ca">Tất cả</option>
        <option value="tiep-nhan">Tiếp nhận</option>
        <option value="tham-dinh">Thẩm định / quy hoạch</option>
        <option value="phe-duyet">Phê duyệt</option>
        <option value="nghiem-thu">Nghiệm thu</option>
        <option value="khac">Khác</option>
      </select>
      <button class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50" @click="taiViec()">
        Làm mới
      </button>
    </div>

    <section v-if="laQuanLy && !dangTai && escalations.length" class="rounded-xl border border-amber-200 bg-amber-50 p-4 shadow-sm" aria-labelledby="tieu-de-qua-han">
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 id="tieu-de-qua-han" class="m-0 text-sm font-bold text-amber-900">Việc quá hạn / sắp hạn toàn địa bàn</h3>
        <span class="tt tt-vang">{{ escalations.length }}</span>
      </div>
      <ul class="m-0 list-none p-0 text-[13px]">
        <li v-for="e in escalations.slice(0, 5)" :key="e.id" class="flex flex-wrap items-center justify-between gap-2 border-b border-amber-200 py-1.5 last:border-0">
          <span class="text-amber-900">
            {{ e.name || e.taskDefinitionKey }} · <b>{{ thongTinEsc(e).ma || "-" }}</b>
            <span v-if="thongTinEsc(e).diaChi"> · {{ thongTinEsc(e).diaChi }}</span>
          </span>
          <span :class="e.qua_han ? 'tt tt-do' : 'tt tt-vang'">{{ e.qua_han ? "Quá hạn" : `Còn ${e.con_lai_gio} giờ` }}</span>
        </li>
      </ul>
    </section>

    <div v-if="dangTai" class="rounded-xl border border-slate-200 bg-white p-4" role="status" aria-busy="true">
      <p class="sr-only">Đang tải việc.</p>
      <Skeleton :lines="5" height="2rem" />
    </div>

    <div v-else-if="loi" class="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
      <p class="m-0">{{ loi }}</p>
      <button class="mt-3 rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-sm font-medium text-rose-700" @click="taiViec()">Thử lại</button>
    </div>

    <EmptyState
      v-else-if="!danhSachLoc.length"
      class="rounded-xl border border-slate-200 bg-white p-6"
      title="Không có việc nào cần xử lý"
      description="Việc được giao từ quy trình sẽ xuất hiện ở đây."
    >
      <button type="button" class="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700" @click="taiViec()">Tải lại</button>
    </EmptyState>

    <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <!-- Cột 1: hàng đợi công việc -->
      <aside class="flex max-h-[760px] flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-4">
        <div class="mb-3 flex items-center justify-between border-b border-slate-200 pb-3">
          <h3 class="m-0 text-sm font-bold text-slate-800">Hàng đợi công việc</h3>
          <span class="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-bold text-indigo-700">{{ danhSachLoc.length }}</span>
        </div>
        <div class="flex-1 space-y-2 overflow-y-auto pr-1">
          <button
            v-for="t in danhSachLoc"
            :key="t.id"
            type="button"
            class="w-full rounded-lg border p-3 text-left transition"
            :class="
              selectedTask?.id === t.id
                ? 'border-indigo-500 bg-indigo-50/70 shadow-sm'
                : 'border-slate-200 bg-white hover:border-slate-300'
            "
            @click="chonViec(t)"
          >
            <div class="flex items-start justify-between gap-2">
              <span class="min-w-0">
                <span class="block text-sm font-bold leading-tight text-slate-800">{{ t.name || t.taskDefinitionKey || "Nhiệm vụ" }}</span>
                <span class="mt-0.5 block font-mono text-[11px] font-semibold text-indigo-700">{{ thongTin(t).ma }}</span>
                <span v-if="thongTin(t).diaChi" class="mt-0.5 block truncate text-[11px] text-slate-500">{{ thongTin(t).diaChi }}</span>
              </span>
              <span :class="mucUuTien(t).lop">{{ mucUuTien(t).nhan }}</span>
            </div>
            <div class="mt-2 flex items-center justify-between gap-2 text-[11px] text-slate-500">
              <span>Hạn: {{ dinhDangHan(t) }}</span>
              <span>{{ formatStatus(thongTin(t).trangThai) }}</span>
            </div>
          </button>
        </div>
      </aside>

      <!-- Cột 2: chi tiết hồ sơ -->
      <section class="max-h-[760px] overflow-y-auto rounded-xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-5">
        <div v-if="loadingDetail" class="space-y-3" role="status" aria-busy="true">
          <p class="sr-only">Đang tải chi tiết hồ sơ.</p>
          <Skeleton :lines="6" height="1.8rem" />
        </div>
        <div v-else-if="!selectedDossier" class="flex h-full min-h-[320px] items-center justify-center text-sm text-slate-400">
          Chọn một việc ở cột bên trái để xem chi tiết.
        </div>
        <template v-else>
          <div class="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 pb-3">
            <div>
              <p class="m-0 text-[11px] font-bold uppercase tracking-wide text-indigo-600">Hồ sơ công trình</p>
              <h3 class="m-0 font-mono text-lg font-bold text-slate-900">{{ selectedDossier.ma_ho_so }}</h3>
              <p class="m-0 mt-1 text-xs text-slate-500">{{ selectedDossier.dia_chi_cong_trinh }}</p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <span class="tt tt-lam">{{ formatStatus(selectedDossier.trang_thai || "") || "Đang xử lý" }}</span>
              <span v-if="selectedDossier.buoc" class="text-xs text-slate-500">Bước: {{ selectedDossier.buoc }}</span>
            </div>
          </div>

          <div v-if="detailError" class="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            {{ detailError }}
          </div>

          <dl class="mt-4 grid grid-cols-1 gap-x-4 gap-y-3 text-sm sm:grid-cols-2">
            <div>
              <dt class="text-xs font-medium text-slate-500">Chủ đầu tư</dt>
              <dd class="m-0 font-semibold text-slate-900">{{ selectedDossier.ho_ten || "—" }}</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-slate-500">CCCD / Điện thoại</dt>
              <dd class="m-0 font-mono text-slate-800">{{ selectedDossier.cccd || "—" }} / {{ selectedDossier.dien_thoai || "—" }}</dd>
            </div>
            <div class="sm:col-span-2">
              <dt class="text-xs font-medium text-slate-500">Địa chỉ xây dựng</dt>
              <dd class="m-0 font-semibold text-slate-900">{{ selectedDossier.dia_chi_cong_trinh || "—" }}</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-slate-500">Thửa đất</dt>
              <dd class="m-0 text-slate-800">{{ selectedDossier.thua_dat || "—" }}</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-slate-500">Quy mô</dt>
              <dd class="m-0 text-slate-800">{{ selectedDossier.so_tang || "—" }} tầng, {{ selectedDossier.dien_tich_san_m2 || "—" }} m²</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-slate-500">Địa bàn</dt>
              <dd class="m-0 text-slate-800">{{ selectedDossier.tenant || "—" }}</dd>
            </div>
            <div>
              <dt class="text-xs font-medium text-slate-500">Hạn xử lý</dt>
              <dd
                class="m-0 font-semibold"
                :class="
                  selectedTask && hanCuaViec(selectedTask) !== null && hanCuaViec(selectedTask)! < Date.now()
                    ? 'text-rose-600'
                    : 'text-slate-800'
                "
              >
                {{ selectedTask ? dinhDangHan(selectedTask) : "—" }}
              </dd>
            </div>
          </dl>

          <div class="mt-5 border-t border-slate-200 pt-4">
            <div class="mb-2 flex items-center justify-between">
              <h4 class="m-0 text-sm font-bold text-slate-800">Tệp đính kèm hồ sơ</h4>
              <span class="text-xs text-slate-500">{{ files.length }} tệp</span>
            </div>
            <p v-if="!files.length" class="m-0 text-xs italic text-slate-400">Chưa có tệp đính kèm hoặc chưa tải được danh sách.</p>
            <ul v-else class="m-0 list-none space-y-2 p-0">
              <li v-for="f in files" :key="f.id || f.file_id" class="rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-xs">
                <div class="flex items-center justify-between gap-2">
                  <span class="min-w-0">
                    <span class="block font-semibold text-slate-800">{{ f.ten_loai || f.loai || "Tệp" }}</span>
                    <span class="block truncate text-[11px] text-slate-500">{{ f.ten_file || f.file_name || f.loai || "Tệp đính kèm" }}</span>
                  </span>
                  <span :class="f.trang_thai_kiem_tra === 'dat' ? 'tt tt-xanh' : f.trang_thai_kiem_tra === 'khong_dat' ? 'tt tt-do' : 'tt tt-xam'">
                    {{ f.trang_thai_kiem_tra === "dat" ? "Đạt" : f.trang_thai_kiem_tra === "khong_dat" ? "Không đạt" : "Chờ kiểm tra" }}
                  </span>
                </div>
                <p v-if="f.ly_do" class="m-0 mt-1 text-[11px] text-rose-700">Lý do: {{ f.ly_do }}</p>
              </li>
            </ul>
          </div>

          <div class="mt-5 border-t border-slate-200 pt-4">
            <div class="mb-2 flex items-center justify-between">
              <h4 class="m-0 text-sm font-bold text-slate-800">Lịch sử xử lý gần đây</h4>
              <span class="text-xs text-slate-500">{{ audit.length }} ghi nhận</span>
            </div>
            <p v-if="!audit.length" class="m-0 text-xs italic text-slate-400">Chưa có ghi nhận nào.</p>
            <ul v-else class="m-0 max-h-48 list-none space-y-1.5 overflow-y-auto p-0">
              <li v-for="(a, idx) in audit.slice(0, 8)" :key="idx" class="rounded-lg border border-slate-100 bg-white p-2 text-xs">
                <div class="flex items-center justify-between gap-2">
                  <span class="font-semibold text-slate-800">{{ a.action || a.hanh_dong || "Thao tác" }}</span>
                  <span class="text-[10px] text-slate-400">{{ ngayGio(a.at || a.created_at) }}</span>
                </div>
                <p class="m-0 mt-0.5 text-[11px] text-slate-500">{{ a.actor_name || a.actor_sub || "Hệ thống" }}</p>
              </li>
            </ul>
          </div>

          <div class="mt-5 flex flex-wrap gap-2">
            <button class="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50" @click="moHoSoDayDu">
              Mở hồ sơ đầy đủ
            </button>
            <button
              v-if="selectedTask && actions.laNguoiDuocGiao(selectedTask)"
              class="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
              :disabled="dangLam === selectedTask.id"
              @click="hoanThanh(selectedTask)"
            >
              {{ dangLam === selectedTask.id ? "Đang xử lý..." : "Hoàn thành việc" }}
            </button>
            <button
              v-if="laQuanLy && selectedTask && hanCuaViec(selectedTask) !== null && hanCuaViec(selectedTask)! < Date.now()"
              class="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100"
              :disabled="dangNhac === selectedTask.id"
              @click="nhacViec(selectedTask)"
            >
              {{ dangNhac === selectedTask.id ? "Đang nhắc..." : "Nhắc việc" }}
            </button>
          </div>
        </template>
      </section>

      <!-- Cột 3: thao tác xử lý -->
      <aside class="max-h-[760px] overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm xl:col-span-3">
        <h3 class="m-0 border-b border-slate-200 pb-3 text-sm font-bold text-slate-800">Thao tác xử lý</h3>
        <p v-if="!selectedDossier" class="mt-4 text-xs italic text-slate-400">Chọn một việc để xem thao tác.</p>
        <template v-else>
          <DossierActionBar
            v-if="accessToken"
            id="workspace-dossier-actions"
            compact
            :dossier="selectedDossier"
            :token="accessToken"
            @done="sauKhiXuLy"
          />
          <p v-else class="mt-4 text-xs text-amber-700">Chưa có phiên đăng nhập hợp lệ.</p>
          <div class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
            <p class="m-0 font-semibold text-slate-800">Gợi ý</p>
            <p class="m-0 mt-1">Dùng cột giữa để kiểm tra hồ sơ, tệp đính kèm và lịch sử trước khi ra quyết định.</p>
          </div>
        </template>
      </aside>
    </div>
  </section>
</template>

<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { getUser, getValidToken, readRoles } from "../auth";
import { assignTask, fetchEscalations, fetchOfficers, fetchTasks, remindTask } from "../api/flow";
import { fetchDossierFiles, fetchDossierHistory, openHoSo, reviewDossierFile } from "../api/dossiers";
import { useDossierActions, type NguoiDung } from "../composables/useDossierActions";
import { notify } from "../composables/useToast";
import { EmptyState, Skeleton } from "../design-system";
import DossierActionBar from "../components/DossierActionBar.vue";
import { formatStatus } from "../utils/formatters";
import { cheCccd, ngayLamViecDaQua, tenBuoc, tenHanhDong } from "../utils/labels";
import {
  docBoLoc,
  luuBoLoc,
  xoaBoLoc,
  type BoLocDaLuu,
  type LocHan,
  type LocLoaiViec,
} from "../utils/workspace-filters";
import { taiCsv } from "../utils/csv";
import type { FlowTask } from "../types";

type BoLoc = LocHan;
type LoaiViec = LocLoaiViec;

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

// Chọn nhiều việc và thao tác hàng loạt
const daChon = ref<string[]>([]);
const xacNhanNhom = ref<"" | "nhac" | "phan-cong">("");
const dangChayNhom = ref(false);
const canBo = ref<any[]>([]);
const dangTaiCanBo = ref(false);
const loiCanBo = ref("");
const vaiCanBo = ref("tham-dinh");
const canBoChon = ref("");
const lyDoPhanCong = ref("");

// Bộ lọc đã lưu trong trình duyệt (không chứa PII)
const luuTruLoc: Storage | null = (() => {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
})();
const dsBoLoc = ref<BoLocDaLuu[]>([]);
const boLocDangChon = ref("");
const hienLuuLoc = ref(false);
const tenBoLoc = ref("");

const selectedTask = ref<FlowTask | null>(null);
const selectedDossier = ref<any | null>(null);
const accessToken = ref("");
const files = ref<any[]>([]);
const audit = ref<any[]>([]);
const loadingDetail = ref(false);
const detailError = ref("");
const dangDanhGia = ref("");
const lyDoTep = ref("");
const dangLuuTep = ref("");

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

const daChonSet = computed(() => new Set(daChon.value));
const soChon = computed(() => daChon.value.length);
const chonTatCa = computed(
  () => danhSachLoc.value.length > 0 && daChon.value.length === danhSachLoc.value.length,
);
const dsDangChon = computed(() => danhSachLoc.value.filter((t) => daChonSet.value.has(t.id)));

function laChon(t: FlowTask): boolean {
  return daChonSet.value.has(t.id);
}

function batTatChon(t: FlowTask): void {
  daChon.value = laChon(t)
    ? daChon.value.filter((id) => id !== t.id)
    : [...daChon.value, t.id];
}

function chonTatCaHienTai(): void {
  daChon.value = chonTatCa.value ? [] : danhSachLoc.value.map((t) => t.id);
}

function boChon(): void {
  daChon.value = [];
  xacNhanNhom.value = "";
}

watch(danhSachLoc, (ds) => {
  const ids = new Set(ds.map((t) => t.id));
  const conLai = daChon.value.filter((id) => ids.has(id));
  if (conLai.length !== daChon.value.length) daChon.value = conLai;
});

function apDungBoLoc(): void {
  const x = dsBoLoc.value.find((b) => b.ten === boLocDangChon.value);
  if (!x) return;
  boLoc.value = x.boLoc;
  loaiViec.value = x.loaiViec;
}

function luuBoLocHienTai(): void {
  const ten = tenBoLoc.value.trim();
  if (!ten) {
    notify("Nhập tên bộ lọc trước khi lưu", "canh_bao");
    return;
  }
  dsBoLoc.value = luuBoLoc(luuTruLoc, dsBoLoc.value, ten, boLoc.value, loaiViec.value);
  boLocDangChon.value = ten;
  tenBoLoc.value = "";
  hienLuuLoc.value = false;
  notify(`Đã lưu bộ lọc “${ten}” trên trình duyệt này`, "ok");
}

function xoaBoLocHienTai(): void {
  const ten = boLocDangChon.value;
  if (!ten) return;
  dsBoLoc.value = xoaBoLoc(luuTruLoc, dsBoLoc.value, ten);
  boLocDangChon.value = "";
  notify(`Đã xóa bộ lọc “${ten}”`, "ok");
}

watch([boLoc, loaiViec], () => {
  xacNhanNhom.value = "";
  const x = dsBoLoc.value.find((b) => b.ten === boLocDangChon.value);
  if (!x || x.boLoc !== boLoc.value || x.loaiViec !== loaiViec.value) boLocDangChon.value = "";
});

function moNhacNhom(): void {
  if (!laQuanLy.value || !soChon.value) return;
  xacNhanNhom.value = "nhac";
}

async function taiCanBo(): Promise<void> {
  dangTaiCanBo.value = true;
  loiCanBo.value = "";
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    const kq = await fetchOfficers(t, vaiCanBo.value);
    canBo.value = Array.isArray(kq) ? kq : Array.isArray((kq as any)?.items) ? (kq as any).items : [];
    canBoChon.value = "";
    if (!canBo.value.length) loiCanBo.value = "Chưa có cán bộ phù hợp trong địa bàn.";
  } catch (e) {
    loiCanBo.value = e instanceof Error ? e.message : "Không tải được danh sách cán bộ";
  } finally {
    dangTaiCanBo.value = false;
  }
}

async function moPhanCongNhom(): Promise<void> {
  if (!laQuanLy.value || !soChon.value) return;
  xacNhanNhom.value = "phan-cong";
  if (!canBo.value.length) await taiCanBo();
}

watch(vaiCanBo, () => {
  canBo.value = [];
  canBoChon.value = "";
  if (xacNhanNhom.value === "phan-cong") void taiCanBo();
});

async function thucHienNhacNhom(): Promise<void> {
  const ds = dsDangChon.value.slice();
  if (!ds.length) return;
  dangChayNhom.value = true;
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    const thatBai: string[] = [];
    let loiDau = "";
    for (const task of ds) {
      try {
        await remindTask(t, task.id);
      } catch (e) {
        thatBai.push(task.id);
        if (!loiDau) loiDau = e instanceof Error ? e.message : "Lỗi không xác định";
      }
    }
    const thanhCong = ds.length - thatBai.length;
    daChon.value = thatBai;
    xacNhanNhom.value = "";
    const muc = thatBai.length === 0 ? "ok" : thanhCong === 0 ? "loi" : "canh_bao";
    notify(
      `Đã gửi nhắc ${thanhCong}/${ds.length} việc${thatBai.length ? `; ${thatBai.length} lỗi${loiDau ? `: ${loiDau}` : ""}` : ""}`,
      muc,
    );
    await taiViec();
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không gửi được nhắc việc hàng loạt", "loi");
  } finally {
    dangChayNhom.value = false;
  }
}

async function thucHienPhanCongNhom(): Promise<void> {
  const ds = dsDangChon.value.slice();
  if (!ds.length) return;
  if (!canBoChon.value) {
    notify("Chọn cán bộ trước khi phân công", "canh_bao");
    return;
  }
  dangChayNhom.value = true;
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    const lyDo = lyDoPhanCong.value.trim();
    const thatBai: string[] = [];
    let loiDau = "";
    for (const task of ds) {
      try {
        await assignTask(t, task.id, canBoChon.value, lyDo);
      } catch (e) {
        thatBai.push(task.id);
        if (!loiDau) loiDau = e instanceof Error ? e.message : "Lỗi không xác định";
      }
    }
    const thanhCong = ds.length - thatBai.length;
    daChon.value = thatBai;
    xacNhanNhom.value = "";
    lyDoPhanCong.value = "";
    const muc = thatBai.length === 0 ? "ok" : thanhCong === 0 ? "loi" : "canh_bao";
    notify(
      `Đã phân công ${thanhCong}/${ds.length} việc${thatBai.length ? `; ${thatBai.length} lỗi${loiDau ? `: ${loiDau}` : ""}` : ""}`,
      muc,
    );
    await taiViec();
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không phân công được hàng loạt", "loi");
  } finally {
    dangChayNhom.value = false;
  }
}

function xuatCsvNhom(): void {
  const ds = dsDangChon.value;
  if (!ds.length) return;
  try {
    const headers = ["Mã hồ sơ", "Tên việc", "Địa chỉ", "Hạn xử lý", "Trạng thái", "Mức ưu tiên"];
    const rows = ds.map((t) => {
      const info = thongTin(t);
      return [
        info.ma,
        t.name || t.taskDefinitionKey || "Nhiệm vụ",
        info.diaChi,
        dinhDangHan(t),
        formatStatus(info.trangThai),
        mucUuTien(t).nhan,
      ];
    });
    taiCsv(`viec-da-chon-${new Date().toISOString().slice(0, 10)}.csv`, headers, rows);
    notify(`Đã xuất ${ds.length} việc ra CSV trên máy này`, "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không xuất được CSV", "loi");
  }
}

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

function moDanhGiaTep(f: any): void {
  dangDanhGia.value = f.id;
  lyDoTep.value = "";
}

async function danhGiaTep(f: any, trangThai: "dat" | "khong_dat"): Promise<void> {
  const token = accessToken.value || (await getValidToken()) || "";
  if (!token) {
    notify("Hết phiên, vui lòng đăng nhập lại", "loi");
    return;
  }
  if (trangThai === "khong_dat" && !lyDoTep.value.trim()) {
    notify("Nhập lý do không đạt", "canh_bao");
    return;
  }
  dangLuuTep.value = f.id;
  try {
    await reviewDossierFile(token, f.id, trangThai, trangThai === "khong_dat" ? lyDoTep.value.trim() : "");
    f.trang_thai_kiem_tra = trangThai;
    f.ly_do = trangThai === "khong_dat" ? lyDoTep.value.trim() : null;
    notify(trangThai === "dat" ? "Đã đánh giá tệp đạt" : "Đã ghi nhận tệp không đạt", "ok");
    dangDanhGia.value = "";
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không đánh giá được tệp", "loi");
  } finally {
    dangLuuTep.value = "";
  }
}

async function sauKhiXuLy(d: any): Promise<void> {
  if (d) selectedDossier.value = d;
  await taiViec();
  await taiChiTiet();
}

const STEPS = [
  { key: "tiep_nhan", label: "Tiếp nhận", days: 3 },
  { key: "phan_cong", label: "Phân công", days: 2 },
  { key: "tham_dinh", label: "Thẩm định", days: 7 },
  { key: "phe_duyet", label: "Phê duyệt", days: 2 },
  { key: "hoan_thanh", label: "Cấp phép", days: 1 },
];

const deadline = computed(() => {
  const total = STEPS.reduce((n, s) => n + s.days, 0);
  const d = selectedDossier.value;
  const done = d?.trang_thai === "DA_CAP" || d?.trang_thai === "TU_CHOI";
  const used = Math.min(total, Math.max(1, ngayLamViecDaQua(d?.created_at)));
  const idx = done ? STEPS.length : Math.max(0, STEPS.findIndex((s) => s.key === d?.buoc));
  return {
    total,
    used,
    cols: STEPS.map((s, i) => (i === STEPS.length - 1 ? "minmax(max-content, 1fr)" : `${s.days}fr`)).join(" "),
    steps: STEPS.map((s, i) => ({ ...s, state: i < idx ? "xong" : i === idx ? "dang" : "chua" })),
  };
});

const countdownText = computed(() => {
  const d = selectedDossier.value;
  const value = d?.han_tong_at || d?.han_buoc_at;
  if (!value) return "";
  const t = new Date(value);
  if (Number.isNaN(t.getTime())) return "";
  const left = Math.ceil((t.getTime() - Date.now()) / 86400000);
  const ngay = t.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
  return left < 0 ? `Đã quá hạn từ ${ngay}` : `Hạn cuối ${ngay}`;
});

function moHoSoDayDu(): void {
  if (!selectedDossier.value) return;
  emit("mo-ho-so", selectedDossier.value.id || selectedDossier.value.ma_ho_so, selectedDossier.value.ma_ho_so || "");
}

onMounted(async () => {
  dsBoLoc.value = docBoLoc(luuTruLoc);
  const user = await getUser();
  const roles = readRoles(user?.access_token);
  nguoi.value = { sub: user?.profile?.sub as string | undefined, roles };
  // Không tự mở hồ sơ: mo_ho_so ghi nhật ký truy cập dữ liệu cá nhân, nên chỉ mở khi cán bộ chọn việc
  await taiViec();
});

defineExpose({ taiViec });
</script>

<template>
  <section class="space-y-5">
    <div class="flex flex-wrap items-end gap-3">
      <div class="min-w-0">
        <h1 class="tieu-de-trang">Bàn làm việc</h1>
        <p class="mt-2 text-[16px] text-phu">Hàng đợi công việc, chi tiết hồ sơ và thao tác xử lý trong một màn hình.</p>
      </div>
      <div class="flex-1"></div>
      <!-- Nhãn và ô chọn đi cùng một khối để khi hàng xuống dòng nhãn không tách khỏi ô của nó -->
      <div class="flex items-center gap-2">
        <label class="nhan mb-0" for="loc-viec">Hạn</label>
        <select id="loc-viec" v-model="boLoc" class="o w-auto">
          <option value="tat-ca">Tất cả</option>
          <option value="qua-han">Quá hạn</option>
          <option value="sap-han">Sắp đến hạn (24 giờ)</option>
        </select>
      </div>
      <div class="flex items-center gap-2">
        <label class="nhan mb-0" for="loc-loai-viec">Loại việc</label>
        <select id="loc-loai-viec" v-model="loaiViec" class="o w-auto">
          <option value="tat-ca">Tất cả</option>
          <option value="tiep-nhan">Tiếp nhận</option>
          <option value="tham-dinh">Thẩm định / quy hoạch</option>
          <option value="phe-duyet">Phê duyệt</option>
          <option value="nghiem-thu">Nghiệm thu</option>
          <option value="khac">Khác</option>
        </select>
      </div>
      <button class="btn" @click="taiViec()">Làm mới</button>
      <div class="flex flex-wrap items-center gap-2">
        <select
          v-if="dsBoLoc.length"
          v-model="boLocDangChon"
          class="o w-auto min-w-[180px]"
          aria-label="Bộ lọc đã lưu"
          @change="apDungBoLoc"
        >
          <option value="">Bộ lọc đã lưu</option>
          <option v-for="b in dsBoLoc" :key="b.ten" :value="b.ten">{{ b.ten }}</option>
        </select>
        <button
          v-if="boLocDangChon"
          type="button"
          class="btn btn-sm text-son"
          @click="xoaBoLocHienTai"
        >Xóa bộ lọc</button>
        <button type="button" class="btn" @click="hienLuuLoc = !hienLuuLoc">
          {{ hienLuuLoc ? "Đóng lưu bộ lọc" : "Lưu bộ lọc" }}
        </button>
      </div>
      <div v-if="hienLuuLoc" class="flex w-full flex-wrap items-end gap-2 sm:w-auto">
        <label class="block">
          <span class="nhan">Tên bộ lọc</span>
          <input
            v-model="tenBoLoc"
            class="o sm:w-64"
            maxlength="50"
            placeholder="Ví dụ: Quá hạn thẩm định"
            aria-label="Tên bộ lọc"
            @keydown.enter.prevent="luuBoLocHienTai"
          />
        </label>
        <button type="button" class="btn btn-sm btn-chinh" @click="luuBoLocHienTai">Lưu</button>
      </div>
    </div>

    <section v-if="laQuanLy && !dangTai && escalations.length" class="the p-4" aria-labelledby="tieu-de-qua-han">
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 id="tieu-de-qua-han" class="m-0 text-[14px] font-semibold text-chu">Việc quá hạn / sắp hạn toàn địa bàn</h2>
        <span class="tt tt-vang">{{ escalations.length }}</span>
      </div>
      <ul class="m-0 list-none p-0 text-[13px]">
        <li v-for="e in escalations.slice(0, 5)" :key="e.id" class="flex flex-wrap items-center justify-between gap-2 border-b border-vien-nhat py-1.5 last:border-0">
          <span class="text-chu">
            {{ e.name || e.taskDefinitionKey }} · <b>{{ thongTinEsc(e).ma || "-" }}</b>
            <span v-if="thongTinEsc(e).diaChi" class="text-phu"> · {{ thongTinEsc(e).diaChi }}</span>
          </span>
          <span :class="e.qua_han ? 'tt tt-do' : 'tt tt-vang'">{{ e.qua_han ? "Quá hạn" : `Còn ${e.con_lai_gio} giờ` }}</span>
        </li>
      </ul>
    </section>

    <div v-if="dangTai" class="the p-4" role="status" aria-busy="true">
      <p class="sr-only">Đang tải việc.</p>
      <Skeleton :lines="5" height="2rem" />
    </div>

    <div v-else-if="loi" class="thong-bao-loi">
      <p class="m-0">{{ loi }}</p>
      <button class="btn mt-3" @click="taiViec()">Thử lại</button>
    </div>

    <EmptyState
      v-else-if="!danhSachLoc.length"
      class="the p-6"
      title="Không có việc nào cần xử lý"
      description="Việc được giao từ quy trình sẽ xuất hiện ở đây."
    >
      <button type="button" class="btn" @click="taiViec()">Tải lại</button>
    </EmptyState>

    <div v-else class="grid grid-cols-1 gap-5 lg:grid-cols-12">
      <!-- Cột 1: hàng đợi công việc -->
      <aside class="the flex max-h-[760px] flex-col p-4 lg:col-span-4">
        <div class="mb-3 flex items-center justify-between border-b border-vien-nhat pb-3">
          <h2 class="nhan-nho m-0">Hàng đợi công việc</h2>
          <span class="tt tt-xam">{{ danhSachLoc.length }}</span>
        </div>

        <div class="mb-2 flex flex-wrap items-center justify-between gap-2 text-[12.5px]">
          <label class="inline-flex items-center gap-1.5">
            <input
              type="checkbox"
              class="h-4 w-4 accent-[rgb(var(--c-cham))]"
              :checked="chonTatCa"
              aria-label="Chọn tất cả việc đang lọc"
              @change="chonTatCaHienTai"
            />
            Chọn tất cả
          </label>
          <span v-if="soChon" class="text-phu">Đã chọn {{ soChon }} việc</span>
        </div>

        <div v-if="soChon" class="mb-2 rounded-[14px] border border-vien-nhat bg-mat-2 p-2" role="region" aria-label="Thao tác hàng loạt">
          <div class="flex flex-wrap gap-1.5">
            <button v-if="laQuanLy" type="button" class="btn btn-sm" :disabled="dangChayNhom" @click="moNhacNhom">Nhắc việc</button>
            <button v-if="laQuanLy" type="button" class="btn btn-sm" :disabled="dangChayNhom" @click="moPhanCongNhom">Phân công</button>
            <button type="button" class="btn btn-sm" :disabled="dangChayNhom" @click="xuatCsvNhom">Xuất CSV</button>
            <button type="button" class="btn btn-sm ml-auto" :disabled="dangChayNhom" @click="boChon">Bỏ chọn</button>
          </div>
          <p class="m-0 mt-2 text-[11.5px] text-phu">
            Nhắc/phân công được ghi nhật ký phía máy chủ. CSV chỉ tải trên máy, không gửi dữ liệu đi.
          </p>
        </div>

        <div v-if="xacNhanNhom === 'nhac'" class="mb-2 rounded-[14px] border border-vien-nhat bg-mat-2 p-3 text-[13px]" role="alert">
          <p class="m-0 font-semibold">Gửi nhắc {{ soChon }} việc đã chọn?</p>
          <p class="m-0 mt-1 text-phu">Việc chưa có cán bộ xử lý sẽ báo lỗi và được giữ chọn để thử lại.</p>
          <div class="mt-2 flex flex-wrap gap-2">
            <button type="button" class="btn btn-sm btn-chinh" :disabled="dangChayNhom" @click="thucHienNhacNhom">
              {{ dangChayNhom ? "Đang gửi…" : "Xác nhận nhắc" }}
            </button>
            <button type="button" class="btn btn-sm" :disabled="dangChayNhom" @click="xacNhanNhom = ''">Hủy</button>
          </div>
        </div>

        <div v-if="xacNhanNhom === 'phan-cong'" class="mb-2 rounded-[14px] border border-vien-nhat bg-mat-2 p-3 text-[13px]" role="alert">
          <p class="m-0 font-semibold">Phân công {{ soChon }} việc đã chọn</p>
          <p v-if="dangTaiCanBo" class="m-0 mt-1 text-phu" role="status">Đang tải cán bộ…</p>
          <div v-else-if="loiCanBo" class="mt-1">
            <p class="m-0 text-son">{{ loiCanBo }}</p>
            <button type="button" class="btn btn-sm mt-2" @click="taiCanBo">Thử lại</button>
          </div>
          <label class="mt-2 block">
            <span class="nhan">Nhóm cán bộ</span>
            <select v-model="vaiCanBo" class="o w-full" aria-label="Nhóm cán bộ phân công">
              <option value="tham-dinh">Thẩm định</option>
              <option value="mot-cua">Một cửa</option>
              <option value="lanh-dao">Lãnh đạo</option>
              <option value="trat-tu-xd">Trật tự xây dựng</option>
            </select>
          </label>
          <label v-if="!dangTaiCanBo && !loiCanBo" class="mt-2 block">
            <span class="nhan">Cán bộ</span>
            <select v-model="canBoChon" class="o w-full" aria-label="Cán bộ được phân công">
              <option value="">Chọn cán bộ</option>
              <option v-for="c in canBo" :key="c.sub" :value="c.sub">
                {{ c.ho_ten || c.username || c.sub }}
              </option>
            </select>
          </label>
          <label class="mt-2 block">
            <span class="nhan">Lý do (không bắt buộc)</span>
            <input v-model="lyDoPhanCong" class="o w-full" maxlength="500" aria-label="Lý do phân công" placeholder="Ví dụ: cân bằng tải việc" />
          </label>
          <div class="mt-2 flex flex-wrap gap-2">
            <button type="button" class="btn btn-sm btn-chinh" :disabled="dangChayNhom || dangTaiCanBo || !canBoChon" @click="thucHienPhanCongNhom">
              {{ dangChayNhom ? "Đang phân công…" : "Xác nhận phân công" }}
            </button>
            <button type="button" class="btn btn-sm" :disabled="dangChayNhom" @click="xacNhanNhom = ''">Hủy</button>
          </div>
        </div>

        <div class="flex-1 space-y-2 overflow-y-auto pr-1">
          <div v-for="t in danhSachLoc" :key="t.id" class="flex items-start gap-1.5">
            <input
              type="checkbox"
              class="mt-4 ml-1 h-4 w-4 shrink-0 accent-[rgb(var(--c-cham))]"
              :checked="laChon(t)"
              :aria-label="`Chọn việc ${thongTin(t).ma || t.name || t.id}`"
              @change="batTatChon(t)"
            />
            <button
              type="button"
              class="min-w-0 flex-1 rounded-[18px] border p-3 text-left transition"
              :class="
                selectedTask?.id === t.id
                  ? 'border-[rgb(var(--c-cham))] bg-mat-2'
                  : 'border-vien-nhat bg-transparent hover:bg-mat-2'
              "
              @click="chonViec(t)"
            >
              <div class="flex items-start justify-between gap-2">
                <span class="min-w-0">
                  <span class="block text-[14px] font-semibold leading-tight text-chu">{{ t.name || t.taskDefinitionKey || "Nhiệm vụ" }}</span>
                  <span class="ma mt-0.5 block text-[12.5px]">{{ thongTin(t).ma }}</span>
                  <span v-if="thongTin(t).diaChi" class="mt-0.5 block truncate text-[12px] text-phu">{{ thongTin(t).diaChi }}</span>
                </span>
                <span :class="mucUuTien(t).lop">{{ mucUuTien(t).nhan }}</span>
              </div>
              <div class="mt-2 flex items-center justify-between gap-2 text-[11.5px] text-phu">
                <span>Hạn: {{ dinhDangHan(t) }}</span>
                <span>{{ formatStatus(thongTin(t).trangThai) }}</span>
              </div>
            </button>
          </div>
        </div>
      </aside>

      <!-- Cột 2: chi tiết hồ sơ -->
      <section class="the max-h-[760px] overflow-y-auto p-5 lg:col-span-8 xl:col-span-5">
        <div v-if="loadingDetail" class="space-y-3" role="status" aria-busy="true">
          <p class="sr-only">Đang tải chi tiết hồ sơ.</p>
          <Skeleton :lines="6" height="1.8rem" />
        </div>
        <div v-else-if="!selectedDossier" class="flex h-full min-h-[320px] items-center justify-center text-[13.5px] text-phu">
          Chọn một việc ở cột bên trái để mở hồ sơ. Mỗi lần mở được ghi vào nhật ký truy cập.
        </div>
        <template v-else>
          <div class="flex flex-wrap items-start justify-between gap-3 border-b border-vien-nhat pb-3">
            <div>
              <p class="nhan-nho m-0">Hồ sơ công trình</p>
              <h2 class="ma m-0 text-[22px] font-semibold">{{ selectedDossier.ma_ho_so }}</h2>
              <p class="m-0 mt-1 text-[12.5px] text-phu">{{ selectedDossier.dia_chi_cong_trinh }}</p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <span class="tt tt-lam">{{ formatStatus(selectedDossier.trang_thai || "") || "Đang xử lý" }}</span>
              <span v-if="selectedDossier.buoc" class="text-[12.5px] text-phu">Bước: {{ tenBuoc(selectedDossier.buoc) }}</span>
              <button type="button" class="btn btn-sm btn-chinh" @click="moHoSoDayDu">Mở hồ sơ đầy đủ</button>
            </div>
          </div>

          <div v-if="selectedDossier" class="mt-4" :aria-label="`Ngày làm việc thứ ${deadline.used} trên ${deadline.total}`">
            <div class="grid gap-[3px]" :style="{ gridTemplateColumns: `repeat(${deadline.total}, 1fr)` }">
              <i
                v-for="n in deadline.total"
                :key="n"
                :class="['h-1.5 rounded-full', n < deadline.used ? 'bg-muc-2' : n === deadline.used ? 'bg-cham' : 'bg-mat-noi']"
              ></i>
            </div>
            <div class="mt-2 grid gap-x-2 text-[12px] text-phu" :style="{ gridTemplateColumns: deadline.cols }">
              <span
                v-for="m in deadline.steps"
                :key="m.key"
                :class="['moc', m.state === 'xong' && 'text-chu', m.state === 'dang' && 'moc-dang']"
              >{{ m.label }}</span>
            </div>
            <div class="mt-2.5 flex flex-wrap justify-between gap-2 text-[13px]">
              <span>Ngày làm việc thứ <b class="font-semibold">{{ deadline.used }}</b> trên {{ deadline.total }} theo quy định</span>
              <span>{{ countdownText }}</span>
            </div>
          </div>

          <div v-if="detailError" class="thong-bao-vang mt-3 text-[12.5px]">
            {{ detailError }}
          </div>

          <dl class="mt-4 grid grid-cols-1 gap-x-4 gap-y-3 text-[13.5px] sm:grid-cols-2">
            <div>
              <dt class="nhan-nho">Chủ đầu tư</dt>
              <dd class="m-0 font-semibold text-chu">{{ selectedDossier.ho_ten || "—" }}</dd>
            </div>
            <div>
              <dt class="nhan-nho">CCCD / Điện thoại</dt>
              <dd class="m-0 text-chu">{{ cheCccd(selectedDossier.cccd) || "—" }} / {{ selectedDossier.dien_thoai || "—" }}</dd>
            </div>
            <div class="sm:col-span-2">
              <dt class="nhan-nho">Địa chỉ xây dựng</dt>
              <dd class="m-0 font-semibold text-chu">{{ selectedDossier.dia_chi_cong_trinh || "—" }}</dd>
            </div>
            <div>
              <dt class="nhan-nho">Thửa đất</dt>
              <dd class="m-0 text-chu">{{ selectedDossier.thua_dat || "—" }}</dd>
            </div>
            <div>
              <dt class="nhan-nho">Quy mô</dt>
              <dd class="m-0 text-chu">{{ selectedDossier.so_tang || "—" }} tầng, {{ selectedDossier.dien_tich_san_m2 || "—" }} m²</dd>
            </div>
            <div>
              <dt class="nhan-nho">Địa bàn</dt>
              <dd class="m-0 text-chu">{{ selectedDossier.tenant || "—" }}</dd>
            </div>
            <div>
              <dt class="nhan-nho">Hạn xử lý</dt>
              <dd
                class="m-0 font-semibold"
                :class="
                  selectedTask && hanCuaViec(selectedTask) !== null && hanCuaViec(selectedTask)! < Date.now()
                    ? 'text-son'
                    : 'text-chu'
                "
              >
                {{ selectedTask ? dinhDangHan(selectedTask) : "—" }}
              </dd>
            </div>
          </dl>

          <div class="mt-5 border-t border-vien-nhat pt-4">
            <div class="mb-2 flex items-center justify-between">
              <h3 class="m-0 text-[14px] font-semibold text-chu">Tệp đính kèm hồ sơ</h3>
              <span class="text-[12.5px] text-phu">{{ files.length }} tệp</span>
            </div>
            <p v-if="!files.length" class="m-0 text-[12.5px] italic text-phu">Chưa có tệp đính kèm hoặc chưa tải được danh sách.</p>
            <ul v-else class="m-0 list-none space-y-2 p-0">
              <li v-for="f in files" :key="f.id || f.file_id" class="the-tep text-[12.5px]">
                <div class="flex items-center justify-between gap-2">
                  <span class="min-w-0">
                    <span class="block font-semibold text-chu">{{ f.ten_loai || f.loai || "Tệp" }}</span>
                    <span class="block truncate text-[11.5px] text-phu">{{ f.ten_file || f.file_name || f.loai || "Tệp đính kèm" }}</span>
                  </span>
                  <span :class="f.trang_thai_kiem_tra === 'dat' ? 'tt tt-xanh' : f.trang_thai_kiem_tra === 'khong_dat' ? 'tt tt-do' : 'tt tt-xam'">
                    {{ f.trang_thai_kiem_tra === "dat" ? "Đạt" : f.trang_thai_kiem_tra === "khong_dat" ? "Không đạt" : "Chờ kiểm tra" }}
                  </span>
                </div>
                <p v-if="f.ly_do" class="m-0 mt-1 text-[11.5px] text-son">Lý do: {{ f.ly_do }}</p>
                <div class="mt-2 flex flex-wrap items-center gap-1.5">
                  <button type="button" class="btn btn-sm" :disabled="dangLuuTep === f.id" @click="danhGiaTep(f, 'dat')">Đạt</button>
                  <button type="button" class="btn btn-sm text-vang" :disabled="dangLuuTep === f.id" @click="moDanhGiaTep(f)">Không đạt</button>
                </div>
                <form v-if="dangDanhGia === f.id" class="mt-2 flex flex-wrap gap-1.5" @submit.prevent="danhGiaTep(f, 'khong_dat')">
                  <input v-model="lyDoTep" class="o min-w-[180px] flex-1 !h-8 text-[12px]" required placeholder="Lý do không đạt" />
                  <button type="submit" class="btn btn-sm" :disabled="dangLuuTep === f.id || !lyDoTep.trim()">Lưu</button>
                  <button type="button" class="btn btn-sm" @click="dangDanhGia = ''">Hủy</button>
                </form>
              </li>
            </ul>
          </div>

          <div class="mt-5 border-t border-vien-nhat pt-4">
            <div class="mb-2 flex items-center justify-between">
              <h3 class="m-0 text-[14px] font-semibold text-chu">Lịch sử xử lý gần đây</h3>
              <span class="text-[12.5px] text-phu">{{ audit.length }} ghi nhận</span>
            </div>
            <p v-if="!audit.length" class="m-0 text-[12.5px] italic text-phu">Chưa có ghi nhận nào.</p>
            <ul v-else tabindex="0" aria-label="Lịch sử xử lý gần đây" class="m-0 max-h-48 list-none space-y-1.5 overflow-y-auto p-0">
              <li v-for="(a, idx) in audit.slice(0, 8)" :key="idx" class="rounded-[14px] border border-vien-nhat bg-mat-2 p-2 text-[12px]">
                <div class="flex items-center justify-between gap-2">
                  <span class="font-semibold text-chu">{{ tenHanhDong(a.action || a.hanh_dong || "") }}</span>
                  <span class="text-[10.5px] text-phu">{{ ngayGio(a.at || a.created_at) }}</span>
                </div>
                <p class="m-0 mt-0.5 text-[11.5px] text-phu">{{ a.actor_name || a.actor_sub || "Hệ thống" }}</p>
              </li>
            </ul>
          </div>

          <div class="mt-5 flex flex-wrap gap-2">
            <button
              v-if="selectedTask && actions.laNguoiDuocGiao(selectedTask)"
              class="btn btn-chinh"
              :disabled="dangLam === selectedTask.id"
              @click="hoanThanh(selectedTask)"
            >
              {{ dangLam === selectedTask.id ? "Đang xử lý..." : "Hoàn thành việc" }}
            </button>
            <button
              v-if="laQuanLy && selectedTask && hanCuaViec(selectedTask) !== null && hanCuaViec(selectedTask)! < Date.now()"
              class="btn text-vang"
              :disabled="dangNhac === selectedTask.id"
              @click="nhacViec(selectedTask)"
            >
              {{ dangNhac === selectedTask.id ? "Đang nhắc..." : "Nhắc việc" }}
            </button>
          </div>
        </template>
      </section>

      <!-- Cột 3: thao tác xử lý -->
      <aside class="the max-h-[760px] overflow-y-auto p-4 lg:col-span-12 xl:col-span-3">
        <h2 class="nhan-nho m-0 border-b border-vien-nhat pb-3">Thao tác xử lý</h2>
        <p v-if="!selectedDossier" class="mt-4 text-[12.5px] italic text-phu">Chọn một việc để xem thao tác.</p>
        <template v-else>
          <DossierActionBar
            v-if="accessToken"
            id="workspace-dossier-actions"
            compact
            :dossier="selectedDossier"
            :token="accessToken"
            @done="sauKhiXuLy"
          />
          <p v-else class="mt-4 text-[12.5px] text-vang">Chưa có phiên đăng nhập hợp lệ.</p>
          <div class="mt-4 rounded-[16px] border border-vien-nhat bg-mat-2 p-3 text-[12.5px] text-phu">
            <p class="m-0 font-semibold text-chu">Gợi ý</p>
            <p class="m-0 mt-1">Dùng cột giữa để kiểm tra hồ sơ, tệp đính kèm và lịch sử trước khi ra quyết định.</p>
          </div>
        </template>
      </aside>
    </div>
  </section>
</template>

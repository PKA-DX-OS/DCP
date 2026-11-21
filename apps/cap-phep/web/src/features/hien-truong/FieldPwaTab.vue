<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { getUser, getValidToken, readRoles } from "../../auth";
import { createInspection, fetchCongTrinhNhanh, fetchPhieuKiemTraNhanh } from "../../api/construction";
import { notify } from "../../composables/useToast";
import { useOptionalFeatureContext } from "../context";
import SignaturePad from "./SignaturePad.vue";
import {
  CHECKLIST_HIEN_TRUONG,
  canhBaoNhap,
  loiNhap,
  moTaXungDot,
  taoNhapMoi,
  timXungDot,
  tomTatGhiChu,
  type CongTrinhCache,
  type FieldDraft,
  type FieldPhoto,
} from "../../utils/field-inspection";
import {
  docCacheCongTrinh,
  luuCacheCongTrinh,
  luuNhap as luuNhapKho,
  taiDsNhap as taiDsNhapKho,
  xoaNhap as xoaNhapKho,
} from "../../utils/field-drafts";

const VAI_HIEN_TRUONG = ["app:cap-phep:trat-tu-xd", "app:cap-phep:lanh-dao"];
const ctx = useOptionalFeatureContext();

const quyen = ref(false);
const dangTai = ref(true);
const loiCongTrinh = ref("");
const dsCongTrinh = ref<CongTrinhCache[]>([]);
const dsNhap = ref<FieldDraft[]>([]);
const dangChon = ref<FieldDraft | null>(null);
const chonCongTrinhId = ref("");
const online = ref(typeof navigator === "undefined" ? true : navigator.onLine);
const dangLayGps = ref(false);
const dangGui = ref<string | null>(null);
const dangGuiTatCa = ref(false);
const daThuGui = ref(false);
const thongBaoLuu = ref("");
const xoaCho = ref<string | null>(null);
const caiDat = ref<any>(null);
const nhapAnh = ref<HTMLInputElement | null>(null);
const previewUrls = new Map<string, string>();
let henLuu: ReturnType<typeof setTimeout> | null = null;

const dsChoGui = computed(() => dsNhap.value.filter((d) => d.status !== "da_gui"));
const coTheSua = computed(() => Boolean(dangChon.value && dangChon.value.status !== "da_gui"));
const loiHienThi = computed(() => (daThuGui.value && dangChon.value ? loiNhap(dangChon.value) : []));
const canhBao = computed(() => (dangChon.value ? canhBaoNhap(dangChon.value) : []));

function taoId(): string {
  return globalThis.crypto?.randomUUID?.() || `anh-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function tenTrangThai(status: string): string {
  return { nhap: "Nháp", loi: "Lỗi đồng bộ", da_gui: "Đã gửi" }[status] || status;
}

function lopTrangThai(status: string): string {
  if (status === "da_gui") return "tt tt-xanh";
  if (status === "loi") return "tt tt-do";
  return "tt tt-vang";
}

function ngayGio(value: number | string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("vi-VN");
}

function capNhatDanhSach(d: FieldDraft): void {
  const i = dsNhap.value.findIndex((x) => x.id === d.id);
  if (i >= 0) dsNhap.value[i] = { ...d };
  else dsNhap.value = [d, ...dsNhap.value];
  dsNhap.value.sort((a, b) => b.updatedAt - a.updatedAt);
}

async function luuNhapNgay(): Promise<void> {
  const d = dangChon.value;
  if (!d || d.status === "da_gui") return;
  d.updatedAt = Date.now();
  await luuNhapKho(d);
  capNhatDanhSach(d);
  thongBaoLuu.value = new Date(d.updatedAt).toLocaleTimeString("vi-VN");
}

function xoaPreviewAll(): void {
  for (const url of previewUrls.values()) window.URL.revokeObjectURL(url);
  previewUrls.clear();
}

function urlAnh(p: FieldPhoto): string {
  if (!previewUrls.has(p.id)) {
    previewUrls.set(p.id, typeof URL.createObjectURL === "function" ? URL.createObjectURL(p.blob) : "");
  }
  return previewUrls.get(p.id) || "";
}

function chonNhap(d: FieldDraft): void {
  if (dangChon.value?.id === d.id) return;
  void luuNhapNgay();
  dangChon.value = d;
  daThuGui.value = false;
  thongBaoLuu.value = "";
  xoaPreviewAll();
}

async function taiNhap(): Promise<void> {
  dsNhap.value = await taiDsNhapKho();
  if (!dangChon.value && dsNhap.value.length) dangChon.value = dsNhap.value[0];
}

async function taiCongTrinh(): Promise<void> {
  const cache = await docCacheCongTrinh();
  if (cache.length) dsCongTrinh.value = cache;
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Chưa có phiên đăng nhập");
    const ds = await fetchCongTrinhNhanh(t);
    const sach: CongTrinhCache[] = (ds || [])
      .map((c: any) => ({
        id: String(c.id || ""),
        ma_cong_trinh: String(c.ma_cong_trinh || ""),
        dia_chi: String(c.dia_chi || ""),
      }))
      .filter((c) => c.id && c.ma_cong_trinh);
    if (sach.length) {
      dsCongTrinh.value = sach;
      await luuCacheCongTrinh(sach);
      loiCongTrinh.value = "";
    } else if (!cache.length) {
      loiCongTrinh.value = "Chưa có danh sách công trình trên thiết bị. Kết nối mạng để tải lần đầu.";
    }
  } catch {
    if (!cache.length) loiCongTrinh.value = "Không tải được danh sách công trình; đang dùng dữ liệu lưu trên thiết bị.";
  }
}

async function taoPhieuMoi(): Promise<void> {
  const c = dsCongTrinh.value.find((x) => x.id === chonCongTrinhId.value);
  if (!c) {
    notify("Chọn công trình trước khi tạo phiếu", "canh_bao");
    return;
  }
  await luuNhapNgay();
  const d = taoNhapMoi(c);
  await luuNhapKho(d);
  dsNhap.value = [d, ...dsNhap.value.filter((x) => x.id !== d.id)];
  dangChon.value = d;
  chonCongTrinhId.value = "";
  daThuGui.value = false;
  thongBaoLuu.value = "";
  xoaPreviewAll();
  notify(`Đã tạo phiếu nháp cho ${c.ma_cong_trinh}`, "ok");
}

async function xacNhanXoa(d: FieldDraft): Promise<void> {
  await xoaNhapKho(d.id);
  dsNhap.value = dsNhap.value.filter((x) => x.id !== d.id);
  if (dangChon.value?.id === d.id) {
    dangChon.value = dsNhap.value[0] || null;
    daThuGui.value = false;
    thongBaoLuu.value = "";
    xoaPreviewAll();
  }
  xoaCho.value = null;
  notify("Đã xóa bản nháp trên thiết bị", "ok");
}

function layGps(): void {
  if (!dangChon.value) return;
  if (!navigator.geolocation) {
    notify("Trình duyệt không hỗ trợ lấy vị trí", "canh_bao");
    return;
  }
  dangLayGps.value = true;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      if (dangChon.value) {
        dangChon.value.gps = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: Number.isFinite(pos.coords.accuracy) ? pos.coords.accuracy : null,
        };
        notify("Đã lấy vị trí hiện tại", "ok");
      }
      dangLayGps.value = false;
    },
    (err) => {
      dangLayGps.value = false;
      notify(err.message || "Không lấy được vị trí", "canh_bao");
    },
    { enableHighAccuracy: true, timeout: 10_000, maximumAge: 30_000 },
  );
}

function moChonAnh(): void {
  nhapAnh.value?.click();
}

async function themAnh(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  const d = dangChon.value;
  if (!d) return;
  let them = 0;
  for (const file of files) {
    if (!file.type.startsWith("image/")) {
      notify(`Bỏ qua ${file.name}: không phải ảnh`, "canh_bao");
      continue;
    }
    if (file.size > 8 * 1024 * 1024) {
      notify(`Bỏ qua ${file.name}: vượt 8 MB`, "canh_bao");
      continue;
    }
    if (d.photos.length >= 6) {
      notify("Chỉ lưu tối đa 6 ảnh mỗi phiếu", "canh_bao");
      break;
    }
    d.photos.push({ id: taoId(), name: file.name, type: file.type, size: file.size, blob: file, addedAt: Date.now() });
    them += 1;
  }
  input.value = "";
  if (them) await luuNhapNgay();
}

async function xoaAnh(p: FieldPhoto): Promise<void> {
  const d = dangChon.value;
  if (!d) return;
  const url = previewUrls.get(p.id);
  if (url) window.URL.revokeObjectURL(url);
  previewUrls.delete(p.id);
  d.photos = d.photos.filter((x) => x.id !== p.id);
  await luuNhapNgay();
}

function capNhatMang(): void {
  online.value = navigator.onLine;
  if (online.value) {
    notify("Đã có mạng. Có thể gửi phiếu đang lưu trên thiết bị.", "tin");
    if (!dsCongTrinh.value.length) void taiCongTrinh();
  }
}

function nhanCaiDat(e: Event): void {
  e.preventDefault();
  caiDat.value = e;
}

async function caiUngDung(): Promise<void> {
  const e = caiDat.value;
  if (!e) return;
  caiDat.value = null;
  try {
    await e.prompt();
  } catch {
    notify("Không mở được hộp cài ứng dụng", "canh_bao");
  }
}

async function guiMot(
  d: FieldDraft,
  token: string,
  dsPhieu: any[],
  boQuaXungDot: boolean,
): Promise<"ok" | "conflict" | "loi" | "invalid"> {
  const loi = loiNhap(d);
  if (loi.length) {
    notify(loi[0], "canh_bao");
    return "invalid";
  }
  if (!boQuaXungDot) {
    const xungDot = timXungDot(d, dsPhieu);
    if (xungDot) {
      d.conflict = moTaXungDot(xungDot);
      d.updatedAt = Date.now();
      await luuNhapKho(d);
      capNhatDanhSach(d);
      return "conflict";
    }
  }
  try {
    d.conflict = null;
    const res = await createInspection(token, d.congTrinhId, tomTatGhiChu(d));
    const server = Array.isArray(res) ? res[0] : res;
    d.status = "da_gui";
    d.serverId = server?.id || null;
    d.serverMaPhieu = server?.ma_phieu || server?.ma_phieu_kiem_tra || null;
    d.syncError = null;
    d.updatedAt = Date.now();
    await luuNhapKho(d);
    capNhatDanhSach(d);
    return "ok";
  } catch (e) {
    d.status = "loi";
    d.syncError = e instanceof Error ? e.message : "Không gửi được phiếu";
    d.updatedAt = Date.now();
    await luuNhapKho(d);
    capNhatDanhSach(d);
    return "loi";
  }
}

async function guiNhap(d: FieldDraft, boQuaXungDot = false): Promise<void> {
  daThuGui.value = true;
  if (d.status === "da_gui") return;
  if (!online.value) {
    notify("Đang ngoại tuyến: phiếu vẫn được lưu trên thiết bị để gửi sau.", "canh_bao");
    return;
  }
  const loi = loiNhap(d);
  if (loi.length) {
    notify(loi[0], "canh_bao");
    return;
  }
  dangGui.value = d.id;
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    const dsPhieu = await fetchPhieuKiemTraNhanh(t).catch(() => []);
    const kq = await guiMot(d, t, dsPhieu, boQuaXungDot);
    if (kq === "ok") notify(`Đã gửi phiếu${d.serverMaPhieu ? ` ${d.serverMaPhieu}` : ""}. Ảnh và chữ ký vẫn lưu trên thiết bị.`, "ok");
    else if (kq === "conflict") notify("Có phiếu mới hơn trên máy chủ. Kiểm tra rồi bấm “Vẫn gửi” nếu cần.", "canh_bao");
    else if (kq === "loi") notify(d.syncError || "Không gửi được phiếu", "loi");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không gửi được phiếu", "loi");
  } finally {
    dangGui.value = null;
  }
}

async function guiTatCa(): Promise<void> {
  if (!online.value) {
    notify("Đang ngoại tuyến: chưa thể gửi phiếu.", "canh_bao");
    return;
  }
  const ds = dsChoGui.value.slice();
  if (!ds.length) return;
  dangGuiTatCa.value = true;
  let ok = 0;
  let conflict = 0;
  let loi = 0;
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    const dsPhieu = await fetchPhieuKiemTraNhanh(t).catch(() => []);
    for (const d of ds) {
      const kq = await guiMot(d, t, dsPhieu, false);
      if (kq === "ok") ok += 1;
      else if (kq === "conflict") conflict += 1;
      else if (kq === "loi" || kq === "invalid") {
        loi += 1;
        if (kq === "invalid") daThuGui.value = true;
      }
    }
    notify(
      `Đã gửi ${ok}/${ds.length} phiếu${conflict ? `; ${conflict} phiếu có xung đột cần xác nhận` : ""}${loi ? `; ${loi} phiếu lỗi` : ""}`,
      ok === ds.length ? "ok" : "canh_bao",
    );
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không gửi được phiếu hàng loạt", "loi");
  } finally {
    dangGuiTatCa.value = false;
  }
}

watch(
  dangChon,
  () => {
    if (!dangChon.value || dangChon.value.status === "da_gui") return;
    if (henLuu) clearTimeout(henLuu);
    henLuu = setTimeout(() => void luuNhapNgay(), 600);
  },
  { deep: true },
);

onMounted(async () => {
  if (ctx?.vaiTro.value?.length) {
    quyen.value = ctx.vaiTro.value.some((r) => VAI_HIEN_TRUONG.includes(r));
  } else {
    const user = await getUser();
    const roles = readRoles(user?.access_token);
    quyen.value = roles.some((r) => VAI_HIEN_TRUONG.includes(r));
  }
  window.addEventListener("online", capNhatMang);
  window.addEventListener("offline", capNhatMang);
  window.addEventListener("beforeinstallprompt", nhanCaiDat);
  await Promise.all([taiCongTrinh(), taiNhap()]);
  dangTai.value = false;
});

onBeforeUnmount(() => {
  if (henLuu) clearTimeout(henLuu);
  void luuNhapNgay();
  xoaPreviewAll();
  window.removeEventListener("online", capNhatMang);
  window.removeEventListener("offline", capNhatMang);
  window.removeEventListener("beforeinstallprompt", nhanCaiDat);
});
</script>

<template>
  <section id="pwa-hien-truong" aria-labelledby="tieu-de-hien-truong">
    <div class="mb-4 flex flex-wrap items-end gap-3">
      <div class="min-w-0">
        <h1 id="tieu-de-hien-truong" class="tieu-de-trang">Hiện trường</h1>
        <p class="mt-2 max-w-3xl text-[16px] text-phu">
          Tạo phiếu kiểm tra khi mất mạng, chụp ảnh, lấy GPS, ký tay và đồng bộ khi có mạng.
        </p>
      </div>
      <div class="flex-1"></div>
      <span class="tt" :class="online ? 'tt-xanh' : 'tt-vang'">{{ online ? "Trực tuyến" : "Ngoại tuyến" }}</span>
      <button v-if="caiDat" type="button" class="btn btn-chinh" @click="caiUngDung">Cài ứng dụng</button>
      <button type="button" class="btn" :disabled="dangTai" @click="taiCongTrinh()">Tải lại công trình</button>
    </div>

    <p v-if="!online" class="thong-bao-vang mb-4 text-[13px]">
      Đang ngoại tuyến. Phiếu và ảnh vẫn lưu trên thiết bị; kết nối mạng để gửi.
    </p>

    <div v-if="dangTai" class="the p-6 text-[13px] text-phu" role="status">Đang tải dữ liệu hiện trường…</div>

    <div v-else-if="!quyen" class="thong-bao-loi" role="alert">
      Tài khoản không có quyền dùng phiếu hiện trường.
    </div>

    <div v-else class="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
      <aside class="the p-4">
        <h2 class="m-0 text-[14px] font-semibold">Phiếu trên thiết bị</h2>
        <p class="goi-y mt-1">{{ dsNhap.length }} phiếu · {{ dsChoGui.length }} chờ gửi</p>

        <div class="mt-3 rounded-[14px] border border-vien-nhat bg-mat-2 p-3">
          <label class="block">
            <span class="nhan">Công trình</span>
            <select v-model="chonCongTrinhId" class="o w-full" aria-label="Chọn công trình để tạo phiếu">
              <option value="">Chọn công trình</option>
              <option v-for="c in dsCongTrinh" :key="c.id" :value="c.id">
                {{ c.ma_cong_trinh }} — {{ c.dia_chi }}
              </option>
            </select>
          </label>
          <button type="button" class="btn btn-sm btn-chinh mt-2 w-full" :disabled="!chonCongTrinhId" @click="taoPhieuMoi">
            Tạo phiếu nháp
          </button>
          <p v-if="loiCongTrinh" class="m-0 mt-2 text-[12px] text-vang">{{ loiCongTrinh }}</p>
        </div>

        <button
          v-if="dsChoGui.length"
          type="button"
          class="btn btn-sm mt-3 w-full"
          :disabled="!online || dangGuiTatCa"
          @click="guiTatCa"
        >
          {{ dangGuiTatCa ? "Đang gửi…" : `Gửi tất cả phiếu chờ (${dsChoGui.length})` }}
        </button>

        <p v-if="!dsNhap.length" class="mt-4 text-[13px] text-phu">Chưa có phiếu nháp nào trên thiết bị.</p>
        <ul v-else class="mt-3 list-none space-y-2 p-0">
          <li v-for="d in dsNhap" :key="d.id" class="rounded-[14px] border border-vien-nhat">
            <div class="flex items-start gap-1 p-2">
              <button type="button" class="min-w-0 flex-1 rounded-[10px] p-1 text-left" @click="chonNhap(d)">
                <span class="flex flex-wrap items-center gap-2">
                  <b class="text-[13px]">{{ d.maCongTrinh || "Công trình" }}</b>
                  <span :class="lopTrangThai(d.status)">{{ tenTrangThai(d.status) }}</span>
                </span>
                <span class="mt-1 block text-[11.5px] text-phu">{{ ngayGio(d.updatedAt) }}</span>
                <span class="mt-0.5 block text-[11.5px] text-phu">
                  {{ d.photos.length }} ảnh · {{ d.signature ? "đã ký" : "chưa ký" }}
                </span>
                <span v-if="d.conflict" class="mt-1 block text-[11.5px] text-vang">{{ d.conflict }}</span>
                <span v-if="d.syncError" class="mt-1 block text-[11.5px] text-son">{{ d.syncError }}</span>
              </button>
              <button
                v-if="d.status !== 'da_gui'"
                type="button"
                class="btn-lien-ket shrink-0 p-1 text-[11.5px] text-son"
                @click="xoaCho = d.id"
              >Xóa</button>
            </div>
            <div v-if="xoaCho === d.id" class="flex flex-wrap items-center gap-2 border-t border-vien-nhat px-2 py-2 text-[12px]">
              <span>Xóa bản nháp này?</span>
              <button type="button" class="btn btn-sm text-son" @click="xacNhanXoa(d)">Chắc chắn xóa</button>
              <button type="button" class="btn btn-sm" @click="xoaCho = null">Hủy</button>
            </div>
          </li>
        </ul>
      </aside>

      <div class="the p-4">
        <p v-if="!dangChon" class="py-10 text-center text-[13px] text-phu">
          Chọn một phiếu nháp hoặc tạo phiếu mới từ danh sách công trình.
        </p>

        <template v-else>
          <div class="flex flex-wrap items-start justify-between gap-3 border-b border-vien-nhat pb-3">
            <div class="min-w-0">
              <h2 class="m-0 text-[18px] font-semibold">{{ dangChon.maCongTrinh }}</h2>
              <p class="m-0 mt-1 text-[13px] text-phu">{{ dangChon.diaChi || "—" }}</p>
              <p class="m-0 mt-1 text-[12px] text-phu">
                Tạo lúc {{ ngayGio(dangChon.createdAt) }}
                <span v-if="thongBaoLuu"> · đã lưu nháp lúc {{ thongBaoLuu }}</span>
              </p>
            </div>
            <span :class="lopTrangThai(dangChon.status)">{{ tenTrangThai(dangChon.status) }}</span>
          </div>

          <p v-if="dangChon.status === 'da_gui'" class="thong-bao-vang mt-3 text-[13px]">
            Đã gửi phiếu<template v-if="dangChon.serverMaPhieu"> <b>{{ dangChon.serverMaPhieu }}</b></template>.
            Ảnh và chữ ký vẫn lưu trên thiết bị; API hiện chưa nhận tệp đính kèm của phiếu.
          </p>
          <p v-if="dangChon.syncError && dangChon.status === 'loi'" class="thong-bao-loi mt-3 text-[13px]" role="alert">
            Lỗi đồng bộ: {{ dangChon.syncError }}
          </p>

          <div v-if="daThuGui && loiHienThi.length" class="thong-bao-loi mt-3" role="alert">
            <b>Chưa gửi được ({{ loiHienThi.length }} lỗi)</b>
            <ul class="mt-1 mb-0 pl-5 list-disc">
              <li v-for="(loi, i) in loiHienThi" :key="i">{{ loi }}</li>
            </ul>
          </div>

          <p v-if="canhBao.length" class="thong-bao-vang mt-3 text-[13px]">
            Cảnh báo: {{ canhBao.join(" ") }}
          </p>

          <div v-if="dangChon.conflict" class="thong-bao-vang mt-3 text-[13px]" role="alert">
            <p class="m-0 font-semibold">Có xung đột dữ liệu</p>
            <p class="m-0 mt-1">{{ dangChon.conflict }}</p>
            <button type="button" class="btn btn-sm mt-2" :disabled="dangGui === dangChon.id" @click="guiNhap(dangChon, true)">
              {{ dangGui === dangChon.id ? "Đang gửi…" : "Vẫn gửi" }}
            </button>
          </div>

          <div class="mt-4">
            <h3 class="muc-con">Checklist hiện trường</h3>
            <div class="space-y-2">
              <label v-for="item in CHECKLIST_HIEN_TRUONG" :key="item.key" class="grid gap-1 sm:grid-cols-[minmax(0,1fr)_190px] sm:items-center">
                <span class="text-[13px]">{{ item.label }}</span>
                <select v-model="dangChon.checklist[item.key]" class="o" :disabled="!coTheSua" :aria-label="`Đánh giá: ${item.label}`">
                  <option value="">Chưa đánh giá</option>
                  <option value="dat">Đạt</option>
                  <option value="khong_dat">Không đạt</option>
                  <option value="khong_ap_dung">Không áp dụng</option>
                </select>
              </label>
            </div>
          </div>

          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <section class="rounded-[14px] border border-vien-nhat p-3">
              <h3 class="m-0 text-[13px] font-semibold">Vị trí GPS</h3>
              <p v-if="dangChon.gps" class="m-0 mt-1 text-[12.5px] text-phu">
                {{ dangChon.gps.lat.toFixed(6) }}, {{ dangChon.gps.lng.toFixed(6) }}
                <template v-if="dangChon.gps.accuracy !== null"> (±{{ Math.round(dangChon.gps.accuracy) }} m)</template>
              </p>
              <p v-else class="m-0 mt-1 text-[12.5px] text-phu">Chưa lấy vị trí.</p>
              <button v-if="coTheSua" type="button" class="btn btn-sm mt-2" :disabled="dangLayGps" @click="layGps">
                {{ dangLayGps ? "Đang lấy vị trí…" : "Lấy vị trí hiện tại" }}
              </button>
            </section>

            <section class="rounded-[14px] border border-vien-nhat p-3">
              <h3 class="m-0 text-[13px] font-semibold">Ghi chú</h3>
              <textarea
                v-model="dangChon.ghiChu"
                class="o mt-2 min-h-[92px] w-full resize-y"
                maxlength="2000"
                :disabled="!coTheSua"
                placeholder="Mô tả hiện trạng, vi phạm, hướng xử lý…"
                aria-label="Ghi chú hiện trường"
              ></textarea>
            </section>
          </div>

          <div class="mt-4">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <h3 class="m-0 text-[14px] font-semibold">Ảnh hiện trường ({{ dangChon.photos.length }}/6)</h3>
              <input ref="nhapAnh" type="file" accept="image/*" capture="environment" multiple class="sr-only" @change="themAnh" />
              <button v-if="coTheSua" type="button" class="btn btn-sm" :disabled="dangChon.photos.length >= 6" @click="moChonAnh">
                Chụp / chọn ảnh
              </button>
            </div>
            <p v-if="!dangChon.photos.length" class="mt-2 text-[12.5px] text-phu">Chưa có ảnh. Ảnh chỉ lưu trên thiết bị.</p>
            <div v-else class="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
              <figure v-for="p in dangChon.photos" :key="p.id" class="overflow-hidden rounded-[12px] border border-vien-nhat bg-mat-2">
                <img :src="urlAnh(p)" :alt="p.name" class="h-28 w-full object-cover" />
                <figcaption class="flex items-center justify-between gap-1 p-1.5 text-[11px] text-phu">
                  <span class="min-w-0 truncate">{{ p.name }}</span>
                  <button v-if="coTheSua" type="button" class="btn-lien-ket text-son" @click="xoaAnh(p)">Xóa</button>
                </figcaption>
              </figure>
            </div>
          </div>

          <div class="mt-4">
            <h3 class="m-0 text-[14px] font-semibold">Chữ ký cán bộ</h3>
            <SignaturePad v-if="coTheSua" v-model="dangChon.signature" class="mt-2" />
            <div v-else-if="dangChon.signature" class="mt-2 rounded-[14px] border border-vien-nhat bg-white p-2">
              <img :src="dangChon.signature" alt="Chữ ký cán bộ" class="block w-full" />
            </div>
            <p v-else class="mt-2 text-[12.5px] text-phu">Không có chữ ký.</p>
          </div>

          <div v-if="coTheSua" class="mt-5 flex flex-wrap items-center gap-2 border-t border-vien-nhat pt-4">
            <button type="button" class="btn" @click="luuNhapNgay">Lưu nháp</button>
            <button
              type="button"
              class="btn btn-chinh"
              :disabled="!online || dangGui === dangChon.id"
              @click="guiNhap(dangChon)"
            >
              {{ dangGui === dangChon.id ? "Đang gửi…" : "Gửi phiếu" }}
            </button>
            <p class="goi-y m-0">Gửi phiếu sẽ tạo phiếu kiểm tra trên máy chủ; ảnh/chữ ký chưa tải lên.</p>
          </div>
        </template>
      </div>
    </div>
  </section>
</template>

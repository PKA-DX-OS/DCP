<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { getValidToken } from "../../auth";
import { downloadFile } from "../../api/files";
import {
  confirmOcr,
  fetchOcrDetail,
  fetchOcrQueue,
  mockConfirmOcr,
  mockRejectOcr,
  rejectOcr,
  type LoaiGiayTo,
  type TrangThaiTrichXuat,
  type TrichXuat,
  type TrichXuatTomTat,
  type TruongTrichXuat,
} from "../../api/ocr";
import { notify } from "../../composables/useToast";
import { ngayGio } from "../../utils/labels";
import { useFeatureContext } from "../context";

const { moHoSo } = useFeatureContext();

const TRANG_THAI: { value: "all" | TrangThaiTrichXuat; label: string }[] = [
  { value: "all", label: "Tất cả trạng thái" },
  { value: "needs_review", label: "Cần duyệt" },
  { value: "queued", label: "Đang chờ" },
  { value: "processing", label: "Đang xử lý" },
  { value: "confirmed", label: "Đã xác nhận" },
  { value: "rejected", label: "Đã từ chối" },
  { value: "failed", label: "Lỗi" },
];

const LOAI_GIAY: { value: LoaiGiayTo; label: string }[] = [
  { value: "cccd", label: "Căn cước công dân" },
  { value: "giay_chung_nhan_qsdd", label: "Giấy chứng nhận QSDĐ" },
  { value: "don_de_nghi_cap_phep", label: "Đơn đề nghị cấp phép" },
];

const NHAN_TRUONG: Record<string, string> = {
  ho_ten: "Họ tên",
  so_cccd: "Số CCCD",
  so_thua: "Số thửa",
  to_ban_do: "Tờ bản đồ",
  dien_tich_m2: "Diện tích (m²)",
  dia_chi: "Địa chỉ",
  so_giay_chung_nhan: "Số giấy chứng nhận",
  ngay_cap: "Ngày cấp",
};

const NHAN_TRANG_THAI: Record<TrangThaiTrichXuat, string> = {
  queued: "Đang chờ",
  processing: "Đang xử lý",
  needs_review: "Cần duyệt",
  confirmed: "Đã xác nhận",
  rejected: "Đã từ chối",
  failed: "Lỗi",
};

const token = ref<string | null>(null);
const nguon = ref<"api" | "mock" | null>(null);
const ocrTat = ref(false);
const hangCho = ref<{ items: TrichXuatTomTat[]; page: number; page_size: number; total: number } | null>(null);
const loading = ref(false);
const loi = ref("");
const chiTiet = ref<TrichXuat | null>(null);
const loadingChiTiet = ref(false);
const loiChiTiet = ref("");
const dangLuu = ref(false);
const hienTuChoi = ref(false);
const lyDoTuChoi = ref("");
const loiLyDo = ref("");
const previewUrl = ref("");
const previewType = ref<"image" | "pdf" | "other" | "">("");
const tenTep = ref("");
const dangTaiTep = ref(false);
const dangChonTruong = ref("");
const NGUONG_TIN_CAY_THAP = 0.8;
let lanHang = 0;
let lanChiTiet = 0;

const boLoc = reactive<{
  status: "all" | TrangThaiTrichXuat;
  doc_type: "" | LoaiGiayTo;
  uuTienThap: boolean;
  page: number;
}>({
  status: "needs_review",
  doc_type: "",
  uuTienThap: true,
  page: 1,
});

const soTrang = computed(() => {
  const h = hangCho.value;
  if (!h) return 1;
  return Math.max(1, Math.ceil(h.total / Math.max(1, h.page_size)));
});

const coTheDuyet = computed(() => chiTiet.value?.status === "needs_review");
const apDungNguong = computed(() => boLoc.status !== "confirmed" && boLoc.status !== "rejected");
const fieldsBbox = computed(
  () => (chiTiet.value?.fields || []).filter((f) => f.page === 1 && hopLeBbox(f)),
);

function tenLoai(v: LoaiGiayTo): string {
  return LOAI_GIAY.find((x) => x.value === v)?.label || v;
}

function tenTrangThai(v: TrangThaiTrichXuat): string {
  return NHAN_TRANG_THAI[v] || v;
}

function lopTrangThai(v: TrangThaiTrichXuat): string {
  if (v === "needs_review") return "tt tt-vang";
  if (v === "confirmed") return "tt tt-xanh";
  if (v === "rejected" || v === "failed") return "tt tt-do";
  if (v === "processing") return "tt tt-lam";
  return "tt tt-xam";
}

function tenTruong(name: string): string {
  return NHAN_TRUONG[name] || name;
}

function phanTram(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(Number(v))) return "—";
  return `${Math.round(Number(v) * 100)}%`;
}

function lopTinCay(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-phu";
  if (v >= 0.85) return "text-xanh";
  if (v >= 0.6) return "text-vang";
  return "text-son";
}

function lopNenTinCay(v: number | null | undefined): string {
  if (v === null || v === undefined) return "bg-phu/30";
  if (v >= 0.85) return "bg-xanh";
  if (v >= 0.6) return "bg-vang";
  return "bg-son";
}

function hopLeBbox(f: TruongTrichXuat): boolean {
  return Array.isArray(f.bbox) && f.bbox.length === 4 && f.bbox.every((n) => Number.isFinite(Number(n)));
}

function kieuBbox(f: TruongTrichXuat): Record<string, string> {
  const b = f.bbox || [];
  return {
    left: `${Number(b[0]) * 100}%`,
    top: `${Number(b[1]) * 100}%`,
    width: `${Number(b[2]) * 100}%`,
    height: `${Number(b[3]) * 100}%`,
  };
}

function xoaPreview(): void {
  if (previewUrl.value) window.URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = "";
  previewType.value = "";
  tenTep.value = "";
}

function khopBoLoc(item: TrichXuatTomTat): boolean {
  if (boLoc.status !== "all" && item.status !== boLoc.status) return false;
  if (boLoc.doc_type && item.doc_type !== boLoc.doc_type) return false;
  if (boLoc.uuTienThap && (item.confidence === null || item.confidence > NGUONG_TIN_CAY_THAP)) return false;
  return true;
}

function capNhatHangCho(kq: TrichXuat): void {
  const ds = hangCho.value;
  if (!ds) return;
  const i = ds.items.findIndex((x) => x.id === kq.id);
  if (i < 0) return;
  if (!khopBoLoc(kq)) {
    ds.items.splice(i, 1);
    ds.total = Math.max(0, ds.total - 1);
    if (!ds.items.length && ds.page > 1) {
      boLoc.page -= 1;
      void taiHangCho();
    }
    return;
  }
  ds.items[i] = { ...ds.items[i], status: kq.status, confidence: kq.confidence };
}

async function taiChiTiet(id: string, nguonHang: "api" | "mock"): Promise<void> {
  if (!token.value) return;
  const lan = ++lanChiTiet;
  loadingChiTiet.value = true;
  loiChiTiet.value = "";
  hienTuChoi.value = false;
  lyDoTuChoi.value = "";
  loiLyDo.value = "";
  xoaPreview();
  try {
    const kq = await fetchOcrDetail(token.value, id, nguonHang === "mock");
    if (lan !== lanChiTiet) return;
    chiTiet.value = kq.data;
    nguon.value = kq.source;
  } catch (e) {
    if (lan !== lanChiTiet) return;
    chiTiet.value = null;
    loiChiTiet.value = e instanceof Error ? e.message : "Không tải được chi tiết OCR";
  } finally {
    if (lan === lanChiTiet) loadingChiTiet.value = false;
  }
}

async function taiHangCho(): Promise<void> {
  const lan = ++lanHang;
  loading.value = true;
  loi.value = "";
  try {
    token.value = await getValidToken();
    if (!token.value) {
      loi.value = "Hết phiên đăng nhập. Vui lòng đăng nhập lại.";
      return;
    }
    const kq = await fetchOcrQueue(token.value, {
      status: boLoc.status === "all" ? undefined : boLoc.status,
      doc_type: boLoc.doc_type || undefined,
      max_confidence: boLoc.uuTienThap && apDungNguong.value ? NGUONG_TIN_CAY_THAP : undefined,
      page: boLoc.page,
      page_size: 20,
    });
    if (lan !== lanHang) return;
    hangCho.value = kq.data;
    nguon.value = kq.source;
    ocrTat.value = Boolean(kq.disabled);
    const dau = kq.data.items[0];
    if (dau) {
      const dangChon = chiTiet.value?.id;
      if (!dangChon || !kq.data.items.some((x) => x.id === dangChon)) {
        await taiChiTiet(dau.id, kq.source);
      }
    } else {
      chiTiet.value = null;
      xoaPreview();
    }
  } catch (e) {
    if (lan !== lanHang) return;
    hangCho.value = null;
    chiTiet.value = null;
    loi.value = e instanceof Error ? e.message : "Không tải được hàng chờ OCR";
  } finally {
    if (lan === lanHang) loading.value = false;
  }
}

function chon(item: TrichXuatTomTat): void {
  void taiChiTiet(item.id, nguon.value || "mock");
}

function doiTrang(buoc: number): void {
  const moi = Math.min(soTrang.value, Math.max(1, boLoc.page + buoc));
  if (moi === boLoc.page) return;
  boLoc.page = moi;
  void taiHangCho();
}

async function xemTep(): Promise<void> {
  if (!token.value || !chiTiet.value?.file_id) return;
  dangTaiTep.value = true;
  try {
    const blob = await downloadFile(token.value, `/files/${encodeURIComponent(chiTiet.value.file_id)}/download`);
    xoaPreview();
    previewUrl.value = window.URL.createObjectURL(blob);
    tenTep.value = `ocr-${chiTiet.value.doc_type}-${chiTiet.value.id.slice(0, 8)}`;
    if (String(blob.type || "").startsWith("image/")) previewType.value = "image";
    else if (String(blob.type || "").includes("pdf")) previewType.value = "pdf";
    else previewType.value = "other";
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tải được tệp gốc", "loi");
  } finally {
    dangTaiTep.value = false;
  }
}

async function xacNhan(): Promise<void> {
  if (!chiTiet.value || !token.value) return;
  const fields = chiTiet.value.fields.map((f) => ({
    name: f.name,
    value: f.value?.trim() ? f.value.trim() : null,
  }));
  dangLuu.value = true;
  try {
    const kq =
      nguon.value === "mock"
        ? mockConfirmOcr(chiTiet.value.id, fields)
        : await confirmOcr(token.value, chiTiet.value.id, fields);
    chiTiet.value = kq;
    capNhatHangCho(kq);
    notify(
      nguon.value === "mock"
        ? "Đã xác nhận trên bản mô phỏng; chưa ghi vào hồ sơ thật."
        : "Đã xác nhận trích xuất và ghi nhật ký.",
      "ok",
    );
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không xác nhận được trích xuất", "loi");
  } finally {
    dangLuu.value = false;
  }
}

async function tuChoi(): Promise<void> {
  if (!chiTiet.value || !token.value) return;
  const lyDo = lyDoTuChoi.value.trim();
  if (lyDo.length < 3) {
    loiLyDo.value = "Nhập lý do từ chối, ít nhất 3 ký tự.";
    return;
  }
  loiLyDo.value = "";
  dangLuu.value = true;
  try {
    const kq =
      nguon.value === "mock"
        ? mockRejectOcr(chiTiet.value.id, lyDo)
        : await rejectOcr(token.value, chiTiet.value.id, lyDo);
    chiTiet.value = kq;
    capNhatHangCho(kq);
    hienTuChoi.value = false;
    lyDoTuChoi.value = "";
    notify(
      nguon.value === "mock"
        ? "Đã từ chối trên bản mô phỏng; chưa ghi vào hồ sơ thật."
        : "Đã từ chối trích xuất và ghi nhật ký.",
      "ok",
    );
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không từ chối được trích xuất", "loi");
  } finally {
    dangLuu.value = false;
  }
}

function moHoSoLienKet(): void {
  if (chiTiet.value?.dossier_id) void moHoSo(chiTiet.value.dossier_id);
}

watch(
  () => [boLoc.status, boLoc.doc_type, boLoc.uuTienThap],
  () => {
    boLoc.page = 1;
    void taiHangCho();
  },
);

onMounted(taiHangCho);
onBeforeUnmount(xoaPreview);
</script>

<template>
  <section id="ocr-review" aria-labelledby="tieu-de-ocr">
    <div class="mb-4 flex flex-wrap items-end gap-3">
      <div class="min-w-0">
        <h1 id="tieu-de-ocr" class="tieu-de-trang">Duyệt trích xuất OCR</h1>
        <p class="mt-2 max-w-3xl text-[16px] text-phu">
          So sánh tệp gốc với từng trường được trích xuất, sửa nếu cần rồi xác nhận hoặc từ chối.
          Không có kết quả nào tự ghi vào hồ sơ.
        </p>
      </div>
      <div class="flex-1"></div>
      <span v-if="nguon" class="tt" :class="nguon === 'api' ? 'tt-xanh' : 'tt-vang'">
        {{ nguon === "api" ? "API OCR" : ocrTat ? "OCR đang tắt · dữ liệu mẫu" : "Dữ liệu mẫu" }}
      </span>
      <button type="button" class="btn" :disabled="loading" @click="taiHangCho">
        {{ loading ? "Đang tải…" : "Làm mới" }}
      </button>
    </div>

    <div v-if="nguon === 'mock'" class="thong-bao-vang mb-4 text-[13.5px]" role="note">
      <p class="m-0 font-semibold">{{ ocrTat ? "Dịch vụ OCR đang tắt" : "API OCR chưa sẵn sàng" }}</p>
      <p v-if="ocrTat" class="m-0 mt-1">
        Dịch vụ OCR có trong hệ thống nhưng đang tắt (<code>DH_OCR=false</code>). Đang hiển thị dữ liệu mẫu để xem trước;
        bật <code>DH_OCR=true</code> và khởi động lại <code>dxos-ocr</code> để dùng hàng chờ thật.
      </p>
      <p v-else class="m-0 mt-1">
        Đang dùng dữ liệu mẫu theo <code>contracts/dh/ocr.yaml</code>. Xác nhận/từ chối chỉ thay đổi trên trình duyệt,
        không ghi vào hồ sơ thật và không tạo audit thật.
      </p>
    </div>

    <div class="the mb-4 flex flex-wrap items-end gap-3 p-4">
      <label class="flex flex-col gap-1 text-[13px]">
        <span class="nhan">Trạng thái</span>
        <select v-model="boLoc.status" class="o w-auto min-w-[190px]">
          <option v-for="t in TRANG_THAI" :key="t.value" :value="t.value">{{ t.label }}</option>
        </select>
      </label>
      <label class="flex flex-col gap-1 text-[13px]">
        <span class="nhan">Loại giấy tờ</span>
        <select v-model="boLoc.doc_type" class="o w-auto min-w-[220px]">
          <option value="">Tất cả loại giấy</option>
          <option v-for="l in LOAI_GIAY" :key="l.value" :value="l.value">{{ l.label }}</option>
        </select>
      </label>
      <label class="mb-2 inline-flex items-center gap-2 text-[13px]" :class="!apDungNguong && 'opacity-50'">
        <input
          v-model="boLoc.uuTienThap"
          type="checkbox"
          class="h-4 w-4 accent-[rgb(var(--c-cham))]"
          :disabled="!apDungNguong"
        />
        Ưu tiên độ tin cậy ≤ 80%
      </label>
      <p class="m-0 mb-2 ml-auto text-[12.5px] text-phu">
        Dữ liệu trường là thông tin cá nhân; chỉ xem hồ sơ được phân công.
      </p>
    </div>

    <div v-if="loi" class="thong-bao-loi mb-4" role="alert">
      <p class="m-0">{{ loi }}</p>
      <button type="button" class="btn btn-sm mt-2" @click="taiHangCho">Thử lại</button>
    </div>

    <div v-if="loading" class="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]" role="status" aria-busy="true">
      <span class="sr-only">Đang tải hàng chờ OCR</span>
      <div class="kinh animate-pulse space-y-3 p-4" aria-hidden="true">
        <div v-for="i in 4" :key="i" class="h-16 rounded bg-slate-200 dark:bg-slate-700"></div>
      </div>
      <div class="kinh animate-pulse space-y-3 p-4" aria-hidden="true">
        <div class="h-5 w-1/3 rounded bg-slate-200 dark:bg-slate-700"></div>
        <div v-for="i in 5" :key="i" class="h-10 w-full rounded bg-slate-200 dark:bg-slate-700"></div>
      </div>
    </div>

    <div v-else-if="hangCho" class="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
      <div class="the overflow-hidden">
        <div class="flex items-center justify-between border-b border-vien-nhat px-4 py-3">
          <b class="text-[13.5px]">{{ hangCho.total }} trích xuất</b>
          <span class="mo">Trang {{ hangCho.page }}/{{ soTrang }}</span>
        </div>
        <div v-if="!hangCho.items.length" class="p-4 text-[13px] text-phu">
          Không có trích xuất nào khớp bộ lọc. Thử bỏ lọc độ tin cậy hoặc đổi trạng thái.
        </div>
        <div v-else class="max-h-[68vh] overflow-y-auto p-2">
          <button
            v-for="item in hangCho.items"
            :key="item.id"
            type="button"
            class="mb-1 w-full rounded-[14px] p-3 text-left transition-colors"
            :class="chiTiet?.id === item.id ? 'bg-mat-2' : 'hover:bg-mat-2'"
            @click="chon(item)"
          >
            <span class="flex flex-wrap items-center justify-between gap-2">
              <b class="text-[13px]">{{ tenLoai(item.doc_type) }}</b>
              <span :class="lopTrangThai(item.status)">{{ tenTrangThai(item.status) }}</span>
            </span>
            <span class="mt-1 block text-[12px] text-phu">
              {{ item.dossier_id ? "Có hồ sơ liên kết" : "Chưa gắn hồ sơ" }} · {{ ngayGio(item.created_at) }}
            </span>
            <span class="mt-2 flex items-center gap-2">
              <span class="h-1.5 flex-1 overflow-hidden rounded-full bg-mat-2">
                <span
                  class="block h-full rounded-full"
                  :class="lopNenTinCay(item.confidence)"
                  :style="{ width: `${Math.round((item.confidence ?? 0) * 100)}%` }"
                ></span>
              </span>
              <span class="text-[11.5px]" :class="lopTinCay(item.confidence)">{{ phanTram(item.confidence) }}</span>
            </span>
          </button>
        </div>
        <div v-if="soTrang > 1" class="flex items-center justify-between border-t border-vien-nhat px-3 py-2">
          <button type="button" class="btn btn-sm" :disabled="boLoc.page <= 1" @click="doiTrang(-1)">Trước</button>
          <span class="mo">Trang {{ boLoc.page }}/{{ soTrang }}</span>
          <button type="button" class="btn btn-sm" :disabled="boLoc.page >= soTrang" @click="doiTrang(1)">Sau</button>
        </div>
      </div>

      <div class="the p-4">
        <div v-if="loadingChiTiet" class="py-10 text-center text-[13px] text-phu" role="status">Đang tải chi tiết…</div>
        <div v-else-if="loiChiTiet" class="thong-bao-loi" role="alert">{{ loiChiTiet }}</div>

        <template v-else-if="chiTiet">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <h2 class="m-0 text-[18px] font-semibold">{{ tenLoai(chiTiet.doc_type) }}</h2>
              <p class="m-0 mt-1 text-[13px] text-phu">
                Độ tin cậy tổng: <b :class="lopTinCay(chiTiet.confidence)">{{ phanTram(chiTiet.confidence) }}</b>
                · {{ ngayGio(chiTiet.created_at) }}
              </p>
            </div>
            <span :class="lopTrangThai(chiTiet.status)">{{ tenTrangThai(chiTiet.status) }}</span>
          </div>

          <div class="mt-3 flex flex-wrap gap-2">
            <button type="button" class="btn btn-sm" :disabled="dangTaiTep" @click="xemTep">
              {{ dangTaiTep ? "Đang tải tệp…" : previewUrl ? "Tải lại tệp gốc" : "Xem tệp gốc" }}
            </button>
            <button v-if="chiTiet.dossier_id" type="button" class="btn btn-sm" @click="moHoSoLienKet">Mở hồ sơ</button>
            <button v-if="previewUrl" type="button" class="btn btn-sm" @click="xoaPreview">Đóng tệp</button>
          </div>

          <div v-if="previewUrl" class="mt-3 overflow-hidden rounded-[14px] border border-vien-nhat">
            <div v-if="previewType === 'image'" class="max-h-[460px] overflow-auto bg-black/20">
              <div class="relative">
                <img :src="previewUrl" alt="Tệp gốc của trích xuất OCR" class="block w-full" />
                <span
                  v-for="f in fieldsBbox"
                  :key="f.name"
                  class="pointer-events-none absolute border-2"
                  :class="dangChonTruong === f.name ? 'border-cham bg-cham/15' : 'border-son/70'"
                  :style="kieuBbox(f)"
                  :title="`${tenTruong(f.name)}: ${f.value ?? '—'}`"
                ></span>
              </div>
            </div>
            <iframe
              v-else-if="previewType === 'pdf'"
              :src="previewUrl"
              title="Tệp gốc của trích xuất OCR"
              class="h-[460px] w-full bg-white"
            ></iframe>
            <div v-else class="flex flex-wrap items-center gap-2 p-3 text-[13px]">
              <span class="text-phu">Tệp không phải ảnh/PDF, không xem trước được.</span>
              <a :href="previewUrl" :download="tenTep" class="btn btn-sm">Tải tệp</a>
            </div>
          </div>

          <p v-if="chiTiet.error" class="thong-bao-loi mt-3" role="alert">{{ chiTiet.error }}</p>

          <div v-if="chiTiet.fields.length" class="mt-4 overflow-x-auto">
            <table class="bang w-full text-[13px]">
              <thead>
                <tr>
                  <th>Trường</th>
                  <th>Giá trị trích xuất</th>
                  <th>Tin cậy</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="f in chiTiet.fields"
                  :key="f.name"
                  @mouseenter="dangChonTruong = f.name"
                  @mouseleave="dangChonTruong = ''"
                >
                  <td class="whitespace-nowrap">
                    <b class="font-medium">{{ tenTruong(f.name) }}</b>
                    <span v-if="f.page" class="mo"> · trang {{ f.page }}</span>
                    <span v-if="f.edited" class="tt tt-lam ml-1">Đã sửa</span>
                  </td>
                  <td class="min-w-[220px]">
                    <input
                      v-if="coTheDuyet"
                      v-model="f.value"
                      type="text"
                      class="o"
                      :aria-label="`Giá trị ${tenTruong(f.name)}`"
                    />
                    <span v-else>{{ f.value || "—" }}</span>
                  </td>
                  <td class="whitespace-nowrap"><span :class="lopTinCay(f.confidence)">{{ phanTram(f.confidence) }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="mt-4 text-[13px] text-phu">Chưa có trường nào được trích xuất.</p>

          <p v-if="chiTiet.status === 'confirmed'" class="mt-3 text-[13px] text-xanh">
            Đã xác nhận bởi {{ chiTiet.reviewed_by || "cán bộ" }}<template v-if="chiTiet.reviewed_at"> lúc {{ ngayGio(chiTiet.reviewed_at) }}</template>.
          </p>
          <p v-if="chiTiet.status === 'rejected'" class="mt-3 text-[13px] text-son">
            Đã từ chối<template v-if="chiTiet.reviewed_by"> bởi {{ chiTiet.reviewed_by }}</template><template v-if="chiTiet.reviewed_at"> lúc {{ ngayGio(chiTiet.reviewed_at) }}</template>.
            <template v-if="chiTiet.reject_reason"> Lý do: {{ chiTiet.reject_reason }}</template>
          </p>

          <div v-if="coTheDuyet" class="mt-4 border-t border-vien-nhat pt-4">
            <div class="flex flex-wrap gap-2">
              <button type="button" class="btn btn-chinh" :disabled="dangLuu" @click="xacNhan">
                {{ dangLuu ? "Đang lưu…" : "Xác nhận kết quả" }}
              </button>
              <button type="button" class="btn text-son" :disabled="dangLuu" @click="hienTuChoi = !hienTuChoi">
                {{ hienTuChoi ? "Hủy từ chối" : "Từ chối" }}
              </button>
            </div>
            <form v-if="hienTuChoi" class="mt-3 rounded-[14px] border border-vien-nhat p-3" @submit.prevent="tuChoi">
              <label class="block">
                <span class="nhan">Lý do từ chối (bắt buộc)</span>
                <input
                  v-model="lyDoTuChoi"
                  class="o w-full"
                  maxlength="500"
                  placeholder="Ví dụ: ảnh mờ, không đọc được diện tích"
                  :aria-invalid="Boolean(loiLyDo)"
                  :aria-describedby="loiLyDo ? 'loi-ly-do-ocr' : undefined"
                />
              </label>
              <p v-if="loiLyDo" id="loi-ly-do-ocr" class="m-0 mt-1 text-[12.5px] text-son" role="alert">{{ loiLyDo }}</p>
              <button type="submit" class="btn btn-sm mt-2 text-son" :disabled="dangLuu">Xác nhận từ chối</button>
            </form>
            <p class="goi-y mt-3">
              Sau khi xác nhận, trường chỉ được dùng để điền sẵn; cán bộ vẫn phải kiểm tra và lưu hồ sơ.
              Mọi thao tác đọc/xác nhận/từ chối đều được ghi nhật ký.
            </p>
          </div>
        </template>

        <p v-else class="py-10 text-center text-[13px] text-phu">Chọn một trích xuất ở cột bên trái để xem chi tiết.</p>
      </div>
    </div>
  </section>
</template>

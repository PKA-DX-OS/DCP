<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { readRoles } from "../../auth";
import { downloadFile, uploadFile as taiTepLen } from "../../api/files";
import { notify } from "../../composables/useToast";
import { Badge, Button, FileUpload, Input, Modal, Select, Skeleton, Tabs, Textarea } from "../../design-system";
import type { HoSo } from "../../types";
import { createDesignReviewApi } from "./api";
import CommentsThread from "./CommentsThread.vue";
import DrawingPreview from "./DrawingPreview.vue";
import DrawingsTab from "./DrawingsTab.vue";
import VersionsPanel from "./VersionsPanel.vue";
import type { BanVe, BoMon, DanhSachBanVe, MaBoMon, MucDo, NhanXet, PhienBanDayDu, TrangThaiThamDinh } from "./types";

const props = defineProps<{ dossier: HoSo; userToken?: string }>();

let api = createDesignReviewApi(props.userToken || "");
const token = computed(() => props.userToken || "");
const boMon = ref<BoMon[]>([]);
const versions = ref<PhienBanDayDu[]>([]);
const phienBan = ref<DanhSachBanVe | null>(null);
const comments = ref<NhanXet[]>([]);
const trangThai = ref<TrangThaiThamDinh | null>(null);
const selectedVersionId = ref<string | null>(null);
const activeTab = ref<"banVe" | "phienBan" | "nhanXet">("banVe");
const loading = ref(false);
const loadingVersion = ref(false);
const saving = ref(false);
const error = ref("");
const preview = ref<BanVe | null>(null);
const previewOpen = ref(false);
const selectedDrawingId = ref<string | null>(null);
const newVersionOpen = ref(false);
const moTa = ref("");
const uploadOpen = ref(false);
const uploadSubject = ref<MaBoMon>("kien_truc");
const uploadName = ref("");
const uploadFile = ref<File | null>(null);
const uploading = ref(false);

watch(
  () => props.userToken,
  (value) => {
    api = createDesignReviewApi(value || "");
    void taiTatCa();
  },
);

const vai = computed(() => readRoles(props.userToken));
const sub = computed(() => docSub(props.userToken));
const laChuHoSo = computed(() =>
  props.dossier.chu_dau_tu_sub
    ? props.dossier.chu_dau_tu_sub === sub.value
    : vai.value.includes("app:cap-phep:chu-dau-tu"),
);
const laThamDinh = computed(() => vai.value.includes("app:cap-phep:tham-dinh") || vai.value.includes("dx:platform-admin"));
const laQuanTri = computed(() => vai.value.includes("dx:platform-admin"));
const coTheTao = computed(() => (laChuHoSo.value || laQuanTri.value) && props.dossier.trang_thai !== "TU_CHOI");
const version = computed(() => phienBan.value?.phien_ban || null);
const nhom = computed(() => phienBan.value?.nhom || []);
const drawings = computed(() => nhom.value.flatMap((n) => n.ban_ve));
const boMonBatBuoc = computed(() => boMon.value.filter((b) => b.bat_buoc).map((b) => b.ma));
const thieuBoMon = computed(() => boMonBatBuoc.value.filter((ma) => !drawings.value.some((bv) => bv.bo_mon === ma)));
const nhanXetMo = computed(() => comments.value.filter((x) => x.trang_thai === "mo").length);
const coTheThemBanVe = computed(() => coTheTao.value && version.value?.trang_thai === "dang_soan");
const tabItems = computed(() => [
  { key: "banVe", label: "Bản vẽ", count: drawings.value.length },
  { key: "phienBan", label: "Phiên bản", count: versions.value.length },
  { key: "nhanXet", label: "Nhận xét", count: nhanXetMo.value },
]);
const boMonOptions = computed(() => boMon.value.map((b) => ({ value: b.ma, label: b.ten })));

function docSub(value?: string): string {
  if (!value) return "";
  try {
    const part = value.split(".")[1] || "";
    const json = JSON.parse(decodeURIComponent(escape(atob(part.replace(/-/g, "+").replace(/_/g, "/")))));
    return String(json?.sub || "");
  } catch {
    return "";
  }
}
function uuid(): string {
  return globalThis.crypto?.randomUUID?.() || `tk-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
function ngay(value?: string | null): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "—";
}
function nhanKetLuan(value?: string): string {
  return value === "dat" ? "Đạt" : value === "khong_dat" ? "Không đạt" : value === "dang_tham_dinh" ? "Đang thẩm định" : "Chưa nộp";
}
function toneKetLuan(value?: string): "success" | "danger" | "warning" | "neutral" {
  return value === "dat" ? "success" : value === "khong_dat" ? "danger" : value === "dang_tham_dinh" ? "warning" : "neutral";
}

async function taiTatCa() {
  if (!token.value) return;
  loading.value = true;
  error.value = "";
  try {
    const [dsMon, dsPhienBan] = await Promise.all([api.dsBoMon(), api.dsPhienBan({ p_ho_so_id: props.dossier.id })]);
    boMon.value = dsMon;
    versions.value = dsPhienBan;
    if (!selectedVersionId.value || !dsPhienBan.some((v) => v.id === selectedVersionId.value)) {
      selectedVersionId.value = dsPhienBan[0]?.id || null;
    }
    await taiPhienBan();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được dữ liệu thiết kế";
  } finally {
    loading.value = false;
  }
}

async function taiPhienBan() {
  if (!token.value) return;
  loadingVersion.value = true;
  try {
    const [ds, tt] = await Promise.all([
      api.dsBanVe({ p_ho_so_id: props.dossier.id, p_phien_ban_id: selectedVersionId.value }),
      api.trangThaiThamDinh({ p_ho_so_id: props.dossier.id }),
    ]);
    phienBan.value = ds;
    trangThai.value = tt;
    comments.value = selectedVersionId.value
      ? await api.dsNhanXet({ p_phien_ban_id: selectedVersionId.value })
      : [];
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được phiên bản thiết kế";
  } finally {
    loadingVersion.value = false;
  }
}

function chonPhienBan(id: string) {
  selectedVersionId.value = id;
  void taiPhienBan();
}

function moTaoPhienBan() {
  moTa.value = "";
  newVersionOpen.value = true;
}

async function taoPhienBan() {
  if (!moTa.value.trim()) return;
  saving.value = true;
  try {
    const pb = await api.taoPhienBan({
      p_ho_so_id: props.dossier.id,
      p_mo_ta: moTa.value.trim(),
      p_idempotency_key: uuid(),
    });
    selectedVersionId.value = pb.id;
    newVersionOpen.value = false;
    await taiTatCa();
    notify(`Đã tạo phiên bản thiết kế v${pb.so_phien_ban}`, "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tạo được phiên bản", "loi");
  } finally {
    saving.value = false;
  }
}

function moUpload(ma?: MaBoMon) {
  uploadSubject.value = ma || boMonBatBuoc.value[0] || "kien_truc";
  uploadName.value = "";
  uploadFile.value = null;
  uploadOpen.value = true;
}
function chonTep(files: File[]) {
  uploadFile.value = files[0] || null;
  if (uploadFile.value && !uploadName.value) uploadName.value = uploadFile.value.name.replace(/\.pdf$/i, "");
}

async function themBanVe() {
  if (!version.value || !uploadFile.value) return;
  uploading.value = true;
  try {
    const meta = await taiTepLen(token.value, uploadFile.value, "ho_so", props.dossier.id);
    await api.themBanVe({
      p_phien_ban_id: version.value.id,
      p_bo_mon: uploadSubject.value,
      p_ten: uploadName.value.trim() || uploadFile.value.name,
      p_file_id: meta.file_id,
      p_idempotency_key: uuid(),
    });
    uploadOpen.value = false;
    await taiTatCa();
    notify("Đã thêm bản vẽ vào phiên bản đang soạn", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không thêm được bản vẽ", "loi");
  } finally {
    uploading.value = false;
  }
}

async function danhGia(bv: BanVe, ketQua: "dat" | "khong_dat") {
  saving.value = true;
  try {
    await api.danhGiaBanVe({ p_ban_ve_id: bv.id, p_ket_qua: ketQua });
    await taiPhienBan();
    notify(`Đã đánh giá ${bv.ten}: ${ketQua === "dat" ? "đạt" : "không đạt"}`, "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không đánh giá được bản vẽ", "loi");
  } finally {
    saving.value = false;
  }
}

async function themNhanXet(payload: { ban_ve_id: string; noi_dung: string; muc_do: MucDo }) {
  saving.value = true;
  try {
    await api.themNhanXet({
      p_ban_ve_id: payload.ban_ve_id,
      p_noi_dung: payload.noi_dung,
      p_muc_do: payload.muc_do,
      p_idempotency_key: uuid(),
    });
    await taiPhienBan();
    notify("Đã gửi nhận xét thẩm định", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không gửi được nhận xét", "loi");
  } finally {
    saving.value = false;
  }
}

async function xuLyNhanXet(payload: { id: string; ghi_chu: string }) {
  saving.value = true;
  try {
    await api.xuLyNhanXet({ p_nhan_xet_id: payload.id, p_ghi_chu: payload.ghi_chu || null });
    await taiPhienBan();
    notify("Đã đánh dấu nhận xét xử lý xong", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không xử lý được nhận xét", "loi");
  } finally {
    saving.value = false;
  }
}

async function taiVe(bv: BanVe) {
  try {
    const blob = await downloadFile(token.value, `/files/${encodeURIComponent(bv.file_id)}/download`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${bv.ten || "ban-ve"}.pdf`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tải được bản vẽ", "loi");
  }
}

function xem(bv: BanVe) {
  preview.value = bv;
  previewOpen.value = true;
}
function moNhanXet(bv: BanVe) {
  selectedDrawingId.value = bv.id;
  activeTab.value = "nhanXet";
}

onMounted(taiTatCa);
</script>

<template>
  <div id="block-design-review" class="mt-5">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h4 class="m-0 text-[14px] font-semibold">Thẩm định thiết kế đa bộ môn</h4>
        <p class="goi-y m-0 mt-1">Bản vẽ theo bộ môn, phiên bản và nhận xét của thẩm định viên.</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button v-if="coTheTao" size="sm" variant="secondary" @click="moTaoPhienBan">Tạo phiên bản mới</Button>
        <Button v-if="coTheThemBanVe" size="sm" @click="moUpload()">Thêm bản vẽ</Button>
      </div>
    </div>

    <div id="design-review-summary" class="mt-3 flex flex-wrap items-center gap-2">
      <Badge :tone="toneKetLuan(trangThai?.ket_luan)" size="sm">{{ nhanKetLuan(trangThai?.ket_luan) }}</Badge>
      <span class="text-ds-sm text-ds-muted">Phiên bản mới nhất: v{{ trangThai?.so_phien_ban || 0 }}</span>
      <span v-if="version" class="text-ds-sm text-ds-muted">Đang xem: v{{ version.so_phien_ban }} ({{ ngay(version.created_at) }})</span>
      <Badge v-if="thieuBoMon.length" tone="danger" size="sm">Thiếu: {{ thieuBoMon.join(", ") }}</Badge>
      <Badge v-else-if="drawings.length" tone="success" size="sm">Đủ bộ môn bắt buộc</Badge>
      <Badge v-if="nhanXetMo" tone="warning" size="sm">{{ nhanXetMo }} nhận xét mở</Badge>
    </div>

    <p v-if="loading" class="mt-3"><Skeleton :lines="5" /></p>
    <p v-else-if="error" class="mt-3 rounded-ds-sm border border-ds-danger/40 bg-ds-danger/10 p-3 text-ds-sm text-ds-text">{{ error }}</p>

    <template v-else>
      <Tabs v-model="activeTab" :tabs="tabItems" label="Thẩm định thiết kế" class="mt-4">
        <template #banVe>
          <div v-if="!version" class="mb-3 rounded-ds-sm border border-ds-border bg-ds-surface-2/50 p-3 text-ds-sm text-ds-text">
            Chưa có phiên bản thiết kế.
            <Button v-if="coTheTao" size="sm" class="ml-2" @click="moTaoPhienBan">Tạo phiên bản đầu tiên</Button>
          </div>
          <DrawingsTab
            :nhom="nhom"
            :version="version"
            :la-chu-ho-so="coTheTao"
            :la-tham-dinh="laThamDinh"
            :loading="loadingVersion"
            @preview="xem"
            @download="taiVe"
            @comment="moNhanXet"
            @evaluate="danhGia"
          />
        </template>
        <template #phienBan>
          <VersionsPanel :versions="versions" :current-id="selectedVersionId" :bo-mon-bat-buoc="boMonBatBuoc" @select="chonPhienBan" />
        </template>
        <template #nhanXet>
          <CommentsThread
            :comments="comments"
            :drawings="drawings"
            :can-comment="laThamDinh"
            :can-resolve="laThamDinh || coTheTao"
            :loading="loadingVersion"
            :saving="saving"
            :selected-drawing-id="selectedDrawingId"
            @add="themNhanXet"
            @resolve="xuLyNhanXet"
          />
        </template>
      </Tabs>
    </template>

    <DrawingPreview v-model:open="previewOpen" :drawing="preview" :token="token" />

    <Modal v-model:open="newVersionOpen" title="Tạo phiên bản thiết kế" size="md">
      <Textarea v-model="moTa" label="Mô tả thay đổi so với phiên bản trước" :rows="4" :maxlength="2000" required placeholder="Ví dụ: bổ sung kết cấu và sửa sơ đồ cấp điện" />
      <template #footer>
        <Button variant="secondary" @click="newVersionOpen = false">Hủy</Button>
        <Button :disabled="saving || !moTa.trim()" @click="taoPhienBan">{{ saving ? "Đang tạo…" : "Tạo phiên bản" }}</Button>
      </template>
    </Modal>

    <Modal v-model:open="uploadOpen" title="Thêm bản vẽ vào phiên bản đang soạn" size="md">
      <div class="grid gap-3">
        <Select v-model="uploadSubject" label="Bộ môn" :options="boMonOptions" required />
        <Input v-model="uploadName" label="Tên bản vẽ" placeholder="Ví dụ: KT-01 Mặt bằng tầng 1" />
        <FileUpload label="Chọn tệp PDF" hint="Tệp được quét virus và tính SHA-256 trước khi lưu." :accept="['application/pdf']" :max-bytes="50 * 1024 * 1024" @select="chonTep" />
        <p v-if="uploadFile" class="m-0 text-ds-sm text-ds-muted">Đã chọn: {{ uploadFile.name }}</p>
      </div>
      <template #footer>
        <Button variant="secondary" @click="uploadOpen = false">Hủy</Button>
        <Button :disabled="uploading || !uploadFile" @click="themBanVe">{{ uploading ? "Đang tải…" : "Thêm bản vẽ" }}</Button>
      </template>
    </Modal>
  </div>
</template>

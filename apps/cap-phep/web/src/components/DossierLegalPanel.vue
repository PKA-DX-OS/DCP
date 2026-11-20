<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import {
  attachDossierLocation,
  checkAuthority,
  createArchive,
  createFee,
  createReceipt,
  fetchArchive,
  fetchDossierAuthority,
  fetchFees,
  fetchReceipts,
  fetchShareLogs,
  fetchSharePayload,
  lookupLocation,
  shareDossierData,
  updateArchiveStatus,
  updateReceiptStatus,
} from "../api/legal";
import { notify } from "../composables/useToast";

const props = defineProps<{
  dossier: any;
  token: string;
  coTheKiemTra?: boolean;
}>();

const authority = ref<any | null>(null);
const authorityTheoThongTin = ref<any | null>(null);
const authorityForm = reactive({
  loai_cong_trinh: "nha_o_rieng_le",
  cap_cong_trinh: "",
  doi_tuong: "ho_gia_dinh_ca_nhan",
  trong_kcn: false,
  cap_hanh_chinh: "xa",
});
const location = ref<any | null>(null);
const fees = ref<any[]>([]);
const receipts = ref<any[]>([]);
const archive = ref<any[]>([]);
const shareLogs = ref<any[]>([]);
const payload = ref<any | null>(null);
const maDiaDiem = ref(String(props.dossier?.ma_dinh_danh_dia_diem || ""));
const loading = ref(false);
const saving = ref("");
const error = ref("");

const feeForm = reactive({
  ten_thu_tuc: "",
  muc_phi: 50000,
  can_cu: "",
});
const receiptForm = reactive({
  so_bien_lai: "",
  so_tien: 50000,
  ma_tham_chieu: "",
  ghi_chu: "",
});
const archiveForm = reactive({
  nhom_ho_so: "cap_phep_xay_dung",
  ghi_chu: "",
});
const shareForm = reactive({
  ben_nhan: "CSDL quốc gia về hoạt động xây dựng",
  loai_du_lieu: "ho_so",
});
const receiptStatus = reactive<Record<string, string>>({});
const archiveStatus = reactive<Record<string, string>>({});

const laHoSo = computed(() => Boolean(props.dossier?.id));
const coTheGhi = computed(() => Boolean(props.coTheKiemTra));

function ngay(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString("vi-VN") : "—";
}
function tenDoiTuong(value: string): string {
  return {
    ho_gia_dinh_ca_nhan: "Hộ gia đình, cá nhân",
    to_chuc: "Tổ chức",
    doanh_nghiep: "Doanh nghiệp",
  }[value] || value || "—";
}
function tenTrangThaiChiaSe(value: string): string {
  return { cho_ket_noi: "Chờ kết nối", da_gui: "Đã gửi", loi: "Lỗi" }[value] || value || "—";
}
function tien(value: any): string {
  const so = Number(value);
  return Number.isFinite(so) ? `${so.toLocaleString("vi-VN")} đ` : "—";
}
function tenTrangThaiBienLai(value: string): string {
  return { da_doi_soat: "Đã đối soát", hoan_phi: "Hoàn phí", huy: "Hủy" }[value] || value || "—";
}
function tenTrangThaiLuuTru(value: string): string {
  return {
    dang_luu_tru: "Đang lưu trữ",
    chuyen_giao: "Chuyển giao",
    tieu_huy: "Tiêu hủy",
    het_han: "Hết hạn",
  }[value] || value || "—";
}
function tenNhom(value: string): string {
  return { cap_phep_xay_dung: "Cấp phép xây dựng", ho_so_khac: "Hồ sơ khác" }[value] || value || "—";
}
function coQuan(value: any): string {
  return String(value?.co_quan_cap || value?.cap_hanh_chinh || "—");
}

async function tai(): Promise<void> {
  if (!props.token || !laHoSo.value) return;
  loading.value = true;
  error.value = "";
  try {
    const [a, f, r, ar, s] = await Promise.all([
      fetchDossierAuthority(props.token, props.dossier.id).catch(() => null),
      fetchFees(props.token).catch(() => []),
      fetchReceipts(props.token).catch(() => []),
      fetchArchive(props.token).catch(() => []),
      fetchShareLogs(props.token).catch(() => []),
    ]);
    authority.value = a;
    fees.value = f;
    receipts.value = (r || []).filter((x) => x.ho_so_id === props.dossier.id);
    archive.value = (ar || []).filter((x) => x.ho_so_id === props.dossier.id);
    shareLogs.value = (s || []).filter((x) => x.ho_so_id === props.dossier.id);
    for (const x of receipts.value) receiptStatus[x.id] = x.trang_thai;
    for (const x of archive.value) archiveStatus[x.id] = x.trang_thai;
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được dữ liệu pháp lý";
  } finally {
    loading.value = false;
  }
}

async function kiemTraThamQuyen(): Promise<void> {
  saving.value = "authority";
  try {
    authority.value = await fetchDossierAuthority(props.token, props.dossier.id);
    notify("Đã kiểm tra thẩm quyền hồ sơ", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không kiểm tra được thẩm quyền", "loi");
  } finally {
    saving.value = "";
  }
}

async function kiemTraThamQuyenTheoThongTin(): Promise<void> {
  saving.value = "authority-form";
  try {
    authorityTheoThongTin.value = await checkAuthority(props.token, {
      loai_cong_trinh: authorityForm.loai_cong_trinh,
      cap_cong_trinh: authorityForm.cap_cong_trinh || null,
      doi_tuong: authorityForm.doi_tuong,
      trong_kcn: authorityForm.trong_kcn,
      cap_hanh_chinh: authorityForm.cap_hanh_chinh || null,
    });
    notify("Đã kiểm tra thẩm quyền theo thông tin nhập", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không kiểm tra được thẩm quyền", "loi");
  } finally {
    saving.value = "";
  }
}

async function traCuuDiaDiem(baoLoi = true): Promise<void> {
  const ma = maDiaDiem.value.trim();
  if (!/^\d{12}$/.test(ma)) {
    if (baoLoi) notify("Mã định danh địa điểm phải gồm đúng 12 chữ số", "canh_bao");
    return;
  }
  saving.value = "location";
  try {
    location.value = await lookupLocation(props.token, ma);
  } catch (e) {
    location.value = null;
    if (baoLoi) notify(e instanceof Error ? e.message : "Không tra cứu được địa điểm", "loi");
  } finally {
    saving.value = "";
  }
}

async function ganDiaDiem(): Promise<void> {
  const ma = maDiaDiem.value.trim();
  if (!/^\d{12}$/.test(ma)) {
    notify("Mã định danh địa điểm phải gồm đúng 12 chữ số", "canh_bao");
    return;
  }
  saving.value = "attach-location";
  try {
    await attachDossierLocation(props.token, props.dossier.id, ma);
    notify("Đã gắn mã định danh địa điểm cho hồ sơ", "ok");
    await traCuuDiaDiem(false);
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không gắn được mã định danh địa điểm", "loi");
  } finally {
    saving.value = "";
  }
}

async function taoBieuPhi(): Promise<void> {
  if (!feeForm.ten_thu_tuc.trim()) {
    notify("Nhập tên thủ tục", "canh_bao");
    return;
  }
  saving.value = "fee";
  try {
    const moi = await createFee(props.token, {
      ten_thu_tuc: feeForm.ten_thu_tuc.trim(),
      don_vi_tinh: "hồ sơ",
      muc_phi: Number(feeForm.muc_phi) || 0,
      can_cu: feeForm.can_cu.trim() || null,
    });
    fees.value = [moi, ...fees.value];
    feeForm.ten_thu_tuc = "";
    feeForm.can_cu = "";
    notify("Đã thêm biểu phí địa phương", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tạo được biểu phí", "loi");
  } finally {
    saving.value = "";
  }
}

async function taoBienLai(): Promise<void> {
  if (!receiptForm.so_bien_lai.trim()) {
    notify("Nhập số biên lai", "canh_bao");
    return;
  }
  saving.value = "receipt";
  try {
    const moi = await createReceipt(props.token, {
      ho_so_id: props.dossier.id,
      so_bien_lai: receiptForm.so_bien_lai.trim(),
      so_tien: Number(receiptForm.so_tien) || 0,
      ma_tham_chieu: receiptForm.ma_tham_chieu.trim() || null,
      ghi_chu: receiptForm.ghi_chu.trim() || null,
    });
    receipts.value = [moi, ...receipts.value];
    receiptStatus[moi.id] = moi.trang_thai;
    receiptForm.so_bien_lai = "";
    receiptForm.ma_tham_chieu = "";
    receiptForm.ghi_chu = "";
    notify("Đã tạo biên lai phí", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tạo được biên lai", "loi");
  } finally {
    saving.value = "";
  }
}

async function doiTrangThaiBienLai(item: any): Promise<void> {
  const status = receiptStatus[item.id];
  if (!status || status === item.trang_thai) return;
  saving.value = `receipt-${item.id}`;
  try {
    const moi = await updateReceiptStatus(props.token, item.id, status as any);
    item.trang_thai = moi.trang_thai;
    notify("Đã cập nhật trạng thái biên lai", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không cập nhật được biên lai", "loi");
  } finally {
    saving.value = "";
  }
}

async function taoLuuTru(): Promise<void> {
  saving.value = "archive";
  try {
    const moi = await createArchive(props.token, props.dossier.id, {
      nhom_ho_so: archiveForm.nhom_ho_so,
      ghi_chu: archiveForm.ghi_chu.trim() || null,
    });
    archive.value = [moi, ...archive.value.filter((x) => x.id !== moi.id)];
    archiveStatus[moi.id] = moi.trang_thai;
    archiveForm.ghi_chu = "";
    notify("Đã tạo bản ghi lưu trữ", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tạo được bản ghi lưu trữ", "loi");
  } finally {
    saving.value = "";
  }
}

async function doiTrangThaiLuuTru(item: any): Promise<void> {
  const status = archiveStatus[item.id];
  if (!status || status === item.trang_thai) return;
  saving.value = `archive-${item.id}`;
  try {
    const moi = await updateArchiveStatus(props.token, item.id, status as any);
    item.trang_thai = moi.trang_thai;
    notify("Đã cập nhật trạng thái lưu trữ", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không cập nhật được lưu trữ", "loi");
  } finally {
    saving.value = "";
  }
}

async function chiaSe(): Promise<void> {
  if (!shareForm.ben_nhan.trim()) {
    notify("Nhập bên nhận dữ liệu", "canh_bao");
    return;
  }
  saving.value = "share";
  try {
    const moi = await shareDossierData(props.token, {
      loai_du_lieu: shareForm.loai_du_lieu,
      ho_so_id: props.dossier.id,
      ben_nhan: shareForm.ben_nhan.trim(),
    });
    shareLogs.value = [moi, ...shareLogs.value];
    notify("Đã tạo bản ghi chia sẻ dữ liệu NĐ 278", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tạo được bản ghi chia sẻ", "loi");
  } finally {
    saving.value = "";
  }
}

async function taiPayload(): Promise<void> {
  saving.value = "payload";
  try {
    payload.value = await fetchSharePayload(props.token, props.dossier.id);
    notify("Đã tạo payload tối thiểu để chia sẻ", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tạo được payload", "loi");
  } finally {
    saving.value = "";
  }
}

onMounted(tai);
</script>

<template>
  <section id="block-dossier-legal" class="mt-5" aria-labelledby="tieu-de-phap-ly">
    <div class="flex flex-wrap items-baseline justify-between gap-3 mb-2">
      <h4 id="tieu-de-phap-ly" class="text-[14px] font-semibold m-0">Pháp lý, phí và lưu trữ</h4>
      <span class="goi-y">Thẩm quyền, định danh địa điểm, biên lai, lưu trữ và chia sẻ NĐ 278</span>
    </div>

    <p v-if="loading" class="text-phu m-0" role="status">Đang tải dữ liệu pháp lý…</p>
    <p v-else-if="error" class="canh-bao m-0">{{ error }}</p>

    <template v-else>
      <div class="grid gap-3 lg:grid-cols-2">
        <section class="the p-3" aria-labelledby="tieu-de-tham-quyen">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h5 id="tieu-de-tham-quyen" class="text-[13px] font-semibold m-0">Thẩm quyền cấp phép</h5>
            <button type="button" class="btn btn-sm" :disabled="saving === 'authority'" @click="kiemTraThamQuyen">
              {{ saving === "authority" ? "Đang kiểm tra…" : "Kiểm tra lại" }}
            </button>
          </div>
          <div v-if="authority" class="mt-2 space-y-1 text-[13px]">
            <p class="m-0">
              <span class="tt" :class="authority.xac_dinh_duoc ? 'tt-xanh' : 'tt-vang'">
                {{ authority.xac_dinh_duoc ? "Xác định được thẩm quyền" : "Chưa xác định được" }}
              </span>
            </p>
            <p class="m-0"><span class="text-phu">Cơ quan cấp:</span> {{ coQuan(authority) }}</p>
            <p class="m-0"><span class="text-phu">Người ký:</span> {{ authority.nguoi_ky || "—" }}</p>
            <p class="m-0"><span class="text-phu">Đối tượng:</span> {{ tenDoiTuong(authority.doi_tuong) }}</p>
            <p class="m-0"><span class="text-phu">Trong KCN:</span> {{ authority.trong_kcn ? "Có" : "Không" }}</p>
            <p v-if="authority.legal_citation_key" class="m-0 text-phu">Căn cứ: {{ authority.legal_citation_key }}</p>
          </div>
          <p v-else class="mt-2 mb-0 text-phu text-[13px]">Chưa có kết quả kiểm tra thẩm quyền.</p>

          <details class="mt-3 border-t border-vien-nhat pt-2">
            <summary class="cursor-pointer text-[12.5px] font-medium">Kiểm tra thẩm quyền theo thông tin công trình</summary>
            <div class="mt-2 grid gap-2 sm:grid-cols-2">
              <label><span class="nhan">Loại công trình</span>
                <select v-model="authorityForm.loai_cong_trinh" class="o w-full">
                  <option value="nha_o_rieng_le">Nhà ở riêng lẻ</option>
                  <option value="nha_o">Nhà ở</option>
                  <option value="cong_trinh_cong_cong">Công trình công cộng</option>
                  <option value="cong_trinh_khac">Công trình khác</option>
                </select>
              </label>
              <label><span class="nhan">Cấp công trình</span>
                <select v-model="authorityForm.cap_cong_trinh" class="o w-full">
                  <option value="">Không xác định</option>
                  <option value="cap_1">Cấp I</option>
                  <option value="cap_2">Cấp II</option>
                  <option value="cap_3">Cấp III</option>
                  <option value="cap_4">Cấp IV</option>
                </select>
              </label>
              <label><span class="nhan">Đối tượng</span>
                <select v-model="authorityForm.doi_tuong" class="o w-full">
                  <option value="ho_gia_dinh_ca_nhan">Hộ gia đình, cá nhân</option>
                  <option value="to_chuc">Tổ chức</option>
                  <option value="doanh_nghiep">Doanh nghiệp</option>
                </select>
              </label>
              <label><span class="nhan">Cấp hành chính</span>
                <select v-model="authorityForm.cap_hanh_chinh" class="o w-full">
                  <option value="xa">Cấp xã</option>
                  <option value="huyen">Cấp huyện</option>
                  <option value="tinh">Cấp tỉnh</option>
                </select>
              </label>
              <label class="flex items-center gap-2 sm:col-span-2">
                <input v-model="authorityForm.trong_kcn" type="checkbox" class="h-4 w-4" />
                <span class="text-[12.5px]">Công trình nằm trong khu công nghiệp</span>
              </label>
            </div>
            <button type="button" class="btn btn-sm mt-2" :disabled="saving === 'authority-form'" @click="kiemTraThamQuyenTheoThongTin">
              {{ saving === "authority-form" ? "Đang kiểm tra…" : "Kiểm tra thẩm quyền" }}
            </button>
            <div v-if="authorityTheoThongTin" class="mt-2 rounded-[12px] border border-vien-nhat p-2 text-[12.5px]">
              <span class="tt" :class="authorityTheoThongTin.xac_dinh_duoc ? 'tt-xanh' : 'tt-vang'">
                {{ authorityTheoThongTin.xac_dinh_duoc ? "Xác định được thẩm quyền" : "Chưa xác định được" }}
              </span>
              <p class="m-0 mt-1"><span class="text-phu">Cơ quan cấp:</span> {{ coQuan(authorityTheoThongTin) }}</p>
              <p class="m-0"><span class="text-phu">Người ký:</span> {{ authorityTheoThongTin.nguoi_ky || "—" }}</p>
              <p v-if="authorityTheoThongTin.legal_citation_key" class="m-0 text-phu">Căn cứ: {{ authorityTheoThongTin.legal_citation_key }}</p>
            </div>
          </details>
        </section>

        <section class="the p-3" aria-labelledby="tieu-de-dinh-danh">
          <h5 id="tieu-de-dinh-danh" class="text-[13px] font-semibold m-0">Định danh địa điểm</h5>
          <div class="mt-2 flex flex-wrap items-end gap-2">
            <label class="min-w-[210px] flex-1">
              <span class="nhan">Mã định danh 12 chữ số</span>
              <input v-model="maDiaDiem" class="o w-full" inputmode="numeric" maxlength="12" placeholder="790101000001" />
            </label>
            <button type="button" class="btn btn-sm" :disabled="saving === 'location'" @click="traCuuDiaDiem()">
              {{ saving === "location" ? "Đang tra…" : "Tra cứu" }}
            </button>
            <button v-if="coTheGhi" type="button" class="btn btn-sm btn-chinh" :disabled="saving === 'attach-location'" @click="ganDiaDiem">
              {{ saving === "attach-location" ? "Đang gắn…" : "Gắn vào hồ sơ" }}
            </button>
          </div>
          <div v-if="location" class="mt-2 text-[13px]">
            <p class="m-0 text-phu">{{ location.message }}</p>
            <dl v-if="location.found && location.data" class="ds-thong-tin ds-thong-tin-doc mt-2">
              <dt>Địa chỉ</dt><dd>{{ location.data.dia_chi || "—" }}</dd>
              <dt>Thửa đất</dt><dd>{{ location.data.so_thua || "—" }}, tờ {{ location.data.to_ban_do || "—" }}</dd>
              <dt>Diện tích</dt><dd>{{ location.data.dien_tich_m2 || "—" }} m²</dd>
              <dt>Nguồn</dt><dd>{{ location.source || location.data.nguon || "—" }}</dd>
            </dl>
          </div>
        </section>
      </div>

      <div class="mt-3 grid gap-3 lg:grid-cols-2">
        <section class="the p-3" aria-labelledby="tieu-de-phi">
          <div class="flex flex-wrap items-baseline justify-between gap-2">
            <h5 id="tieu-de-phi" class="text-[13px] font-semibold m-0">Phí và biên lai</h5>
            <span class="mo">{{ receipts.length }} biên lai của hồ sơ</span>
          </div>
          <div tabindex="0" role="region" aria-label="Biểu phí địa phương" class="mt-2 max-h-40 overflow-auto">
            <table class="bang w-full text-[12.5px]">
              <thead><tr><th>Thủ tục</th><th>Mức phí</th><th>Căn cứ</th></tr></thead>
              <tbody>
                <tr v-for="f in fees.slice(0, 8)" :key="f.id">
                  <td>{{ f.ten_thu_tuc }}</td>
                  <td class="whitespace-nowrap">{{ tien(f.muc_phi) }} / {{ f.don_vi_tinh }}</td>
                  <td class="text-phu">{{ f.can_cu || "—" }}</td>
                </tr>
                <tr v-if="!fees.length"><td colspan="3" class="text-phu">Chưa có biểu phí.</td></tr>
              </tbody>
            </table>
          </div>

          <div v-if="receipts.length" class="mt-3 overflow-x-auto">
            <table class="bang w-full text-[12.5px]">
              <thead><tr><th>Số biên lai</th><th>Số tiền</th><th>Trạng thái</th><th v-if="coTheGhi"><span class="sr-only">Cập nhật</span></th></tr></thead>
              <tbody>
                <tr v-for="r in receipts" :key="r.id">
                  <td class="whitespace-nowrap">{{ r.so_bien_lai }}</td>
                  <td class="whitespace-nowrap">{{ tien(r.so_tien) }}</td>
                  <td><span class="tt tt-lam">{{ tenTrangThaiBienLai(r.trang_thai) }}</span></td>
                  <td v-if="coTheGhi" class="whitespace-nowrap">
                    <select v-model="receiptStatus[r.id]" :aria-label="`Trạng thái biên lai ${r.so_bien_lai}`" class="o !h-8 text-[12px]">
                      <option value="da_doi_soat">Đã đối soát</option>
                      <option value="hoan_phi">Hoàn phí</option>
                      <option value="huy">Hủy</option>
                    </select>
                    <button type="button" class="btn btn-sm ml-1" :disabled="saving === `receipt-${r.id}`" @click="doiTrangThaiBienLai(r)">Lưu</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="mt-2 mb-0 text-phu text-[12.5px]">Hồ sơ chưa có biên lai.</p>

          <form v-if="coTheGhi" class="mt-3 border-t border-vien-nhat pt-3" @submit.prevent="taoBieuPhi">
            <p class="nhan m-0 mb-1">Thêm biểu phí địa phương</p>
            <div class="grid gap-2 sm:grid-cols-3">
              <label><span class="nhan">Tên thủ tục</span><input v-model="feeForm.ten_thu_tuc" class="o w-full" /></label>
              <label><span class="nhan">Mức phí</span><input v-model.number="feeForm.muc_phi" type="number" min="0" class="o w-full" /></label>
              <label><span class="nhan">Căn cứ</span><input v-model="feeForm.can_cu" class="o w-full" /></label>
            </div>
            <button type="submit" class="btn btn-sm mt-2" :disabled="saving === 'fee'">
              {{ saving === "fee" ? "Đang thêm…" : "Thêm biểu phí" }}
            </button>
          </form>

          <form v-if="coTheGhi" class="mt-3 border-t border-vien-nhat pt-3" @submit.prevent="taoBienLai">
            <div class="grid gap-2 sm:grid-cols-2">
              <label><span class="nhan">Số biên lai</span><input v-model="receiptForm.so_bien_lai" class="o w-full" placeholder="BL-2026-001" /></label>
              <label><span class="nhan">Số tiền (VND)</span><input v-model.number="receiptForm.so_tien" type="number" min="0" class="o w-full" /></label>
              <label><span class="nhan">Mã tham chiếu</span><input v-model="receiptForm.ma_tham_chieu" class="o w-full" /></label>
              <label><span class="nhan">Ghi chú</span><input v-model="receiptForm.ghi_chu" class="o w-full" /></label>
            </div>
            <button type="submit" class="btn btn-sm btn-chinh mt-2" :disabled="saving === 'receipt'">
              {{ saving === "receipt" ? "Đang tạo…" : "Tạo biên lai" }}
            </button>
          </form>
        </section>

        <section class="the p-3" aria-labelledby="tieu-de-luu-tru">
          <div class="flex flex-wrap items-baseline justify-between gap-2">
            <h5 id="tieu-de-luu-tru" class="text-[13px] font-semibold m-0">Lưu trữ hồ sơ</h5>
            <span class="mo">{{ archive.length }} bản ghi</span>
          </div>
          <ul v-if="archive.length" class="m-0 mt-2 list-none space-y-2 p-0 text-[12.5px]">
            <li v-for="a in archive" :key="a.id" class="rounded-[14px] border border-vien-nhat p-2">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <b>{{ tenNhom(a.nhom_ho_so) }}</b>
                <span class="tt tt-lam">{{ tenTrangThaiLuuTru(a.trang_thai) }}</span>
              </div>
              <p class="m-0 mt-1 text-phu">Hạn lưu: {{ ngay(a.thoi_han_den) }}<template v-if="a.ghi_chu"> · {{ a.ghi_chu }}</template></p>
              <div v-if="coTheGhi" class="mt-2 flex flex-wrap items-center gap-1">
                <select v-model="archiveStatus[a.id]" :aria-label="`Trạng thái lưu trữ ${a.nhom_ho_so}`" class="o !h-8 text-[12px]">
                  <option value="dang_luu_tru">Đang lưu trữ</option>
                  <option value="chuyen_giao">Chuyển giao</option>
                  <option value="tieu_huy">Tiêu hủy</option>
                  <option value="het_han">Hết hạn</option>
                </select>
                <button type="button" class="btn btn-sm" :disabled="saving === `archive-${a.id}`" @click="doiTrangThaiLuuTru(a)">Lưu</button>
              </div>
            </li>
          </ul>
          <p v-else class="mt-2 mb-0 text-phu text-[12.5px]">Hồ sơ chưa có bản ghi lưu trữ.</p>

          <form v-if="coTheGhi" class="mt-3 border-t border-vien-nhat pt-3" @submit.prevent="taoLuuTru">
            <label class="block"><span class="nhan">Nhóm hồ sơ</span>
              <select v-model="archiveForm.nhom_ho_so" class="o w-full">
                <option value="cap_phep_xay_dung">Cấp phép xây dựng</option>
                <option value="ho_so_khac">Hồ sơ khác</option>
              </select>
            </label>
            <label class="mt-2 block"><span class="nhan">Ghi chú</span><input v-model="archiveForm.ghi_chu" class="o w-full" /></label>
            <button type="submit" class="btn btn-sm btn-chinh mt-2" :disabled="saving === 'archive'">
              {{ saving === "archive" ? "Đang tạo…" : "Tạo lưu trữ" }}
            </button>
          </form>
        </section>
      </div>

      <section class="the mt-3 p-3" aria-labelledby="tieu-de-chia-se">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <h5 id="tieu-de-chia-se" class="text-[13px] font-semibold m-0">Chia sẻ dữ liệu NĐ 278</h5>
          <span class="mo">{{ shareLogs.length }} lần chia sẻ của hồ sơ</span>
        </div>
        <div v-if="shareLogs.length" tabindex="0" role="region" aria-label="Nhật ký chia sẻ dữ liệu" class="mt-2 max-h-48 overflow-auto">
          <table class="bang w-full text-[12.5px]">
            <thead><tr><th>Bên nhận</th><th>Loại dữ liệu</th><th>Căn cứ</th><th>Trạng thái</th><th>Thời điểm</th></tr></thead>
            <tbody>
              <tr v-for="s in shareLogs" :key="s.id">
                <td>{{ s.ben_nhan }}</td>
                <td>{{ s.loai_du_lieu }}</td>
                <td class="text-phu">{{ s.can_cu_phap_ly }}</td>
                <td><span class="tt tt-vang">{{ tenTrangThaiChiaSe(s.trang_thai) }}</span></td>
                <td class="whitespace-nowrap text-phu">{{ ngay(s.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="mt-2 mb-0 text-phu text-[12.5px]">Hồ sơ chưa được chia sẻ.</p>

        <div v-if="coTheGhi" class="mt-3 flex flex-wrap items-end gap-2 border-t border-vien-nhat pt-3">
          <label class="min-w-[260px] flex-1"><span class="nhan">Bên nhận</span><input v-model="shareForm.ben_nhan" class="o w-full" /></label>
          <button type="button" class="btn btn-sm btn-chinh" :disabled="saving === 'share'" @click="chiaSe">
            {{ saving === "share" ? "Đang tạo…" : "Tạo bản ghi chia sẻ" }}
          </button>
          <button type="button" class="btn btn-sm" :disabled="saving === 'payload'" @click="taiPayload">
            {{ saving === "payload" ? "Đang tạo…" : "Xem payload tối thiểu" }}
          </button>
        </div>
        <pre v-if="payload" tabindex="0" class="mt-2 max-h-64 overflow-auto rounded-[14px] border border-vien-nhat bg-mat-2 p-3 text-[11.5px]">{{ JSON.stringify(payload, null, 2) }}</pre>
      </section>
    </template>
  </section>
</template>

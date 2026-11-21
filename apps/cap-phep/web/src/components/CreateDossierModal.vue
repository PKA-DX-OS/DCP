<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div class="nen-hop" @click.self="$emit('close')">
    <div ref="hop" tabindex="-1" class="hop max-w-[760px]" role="dialog" aria-modal="true" aria-labelledby="tieu-de-nop">
      <div class="hop-dau">
        <div>
          <h2 id="tieu-de-nop">Nộp hồ sơ cấp phép xây dựng</h2>
          <p class="goi-y m-0 mt-1">Chuẩn bị đủ giấy tờ theo danh mục bên dưới. Hệ thống kiểm tra lại toàn bộ trước khi nhận; thời hạn giải quyết 7 ngày làm việc kể từ khi hồ sơ hợp lệ.</p>
        </div>
        <button type="button" class="nut-dong" aria-label="Đóng" @click="$emit('close')"><IconX /></button>
      </div>

      <form id="form-nop-ho-so" class="hop-than" novalidate @submit.prevent="handleSubmit">
        <div v-if="khoiPhuc" id="khoi-phuc-ban-nhap" class="thong-bao-vang mb-3 text-[13px]" role="status">
          <div class="flex flex-wrap items-center gap-2">
            <span class="min-w-0 flex-1">
              Đã khôi phục bản nháp lưu lúc {{ ngayGio(khoiPhuc) }} trên trình duyệt này. Tệp đã chọn không được lưu.
            </span>
            <button type="button" class="btn btn-sm" @click="xoaBanNhapNay">Xóa bản nháp</button>
          </div>
        </div>

        <div v-if="trungHoSo.length" id="canh-bao-trung-ho-so" class="thong-bao-vang mb-3 text-[13px]" role="alert">
          <b class="block">Có hồ sơ trùng CCCD và thửa đất</b>
          <p class="m-0 mt-1">
            Đã có {{ trungHoSo.length }} hồ sơ cùng CCCD và thửa đất. Kiểm tra trước khi nộp để tránh trùng.
          </p>
          <ul class="m-0 mt-2 list-none space-y-1.5 p-0">
            <li v-for="d in trungHoSo.slice(0, 3)" :key="d.id" class="flex flex-wrap items-center gap-2">
              <span class="ma">{{ d.ma_ho_so }}</span>
              <span :class="getStatusBadgeClass(d.trang_thai)">{{ formatStatus(d.trang_thai) }}</span>
              <span class="text-phu">{{ ngayGio(d.created_at) }}</span>
              <button type="button" class="btn-lien-ket ml-auto" @click="moHoSoTrung(d)">Mở hồ sơ</button>
            </li>
          </ul>
        </div>

        <div v-if="daThuGui && loiFormTatCa.length" id="loi-form-nop" class="thong-bao-loi mb-3" role="alert">
          <b>Kiểm tra lại thông tin ({{ loiFormTatCa.length }} lỗi)</b>
          <ul class="mt-1 mb-0 pl-5 list-disc">
            <li v-for="(loi, i) in loiFormTatCa" :key="i">{{ loi }}</li>
          </ul>
        </div>

        <div class="mb-3 flex items-center justify-between gap-2 md:hidden" role="status" aria-live="polite">
          <span class="text-[13px] font-semibold">Bước {{ step + 1 }}/3</span>
          <span class="text-[12px] text-phu">{{ ["Chủ đầu tư", "Công trình", "Giấy tờ kèm theo"][step] }}</span>
        </div>
        <div :class="step !== 0 ? 'hidden md:block' : ''">
        <h3 class="muc-con">Chủ đầu tư</h3>

        <div v-if="hoSoGoiY || tenNguoiDung" id="goi-y-dien-lai" class="mb-3 rounded-[16px] border border-vien-nhat bg-mat-2 p-3">
          <div class="flex flex-wrap items-start justify-between gap-2">
            <div class="min-w-0">
              <p class="m-0 text-[13px] font-semibold">Điền nhanh từ dữ liệu đã có</p>
              <p class="m-0 mt-0.5 text-[12.5px] text-phu">
                <template v-if="hoSoGoiY">
                  Hồ sơ gần nhất {{ hoSoGoiY.ma_ho_so }} · {{ hoSoGoiY.ho_ten }} · {{ hoSoGoiY.dia_chi_cong_trinh }}
                </template>
                <template v-else>Tài khoản {{ tenNguoiDung }}</template>
              </p>
            </div>
            <div class="flex flex-wrap gap-2">
              <button v-if="hoSoGoiY" type="button" class="btn btn-sm" @click="dienTuHoSoGoiY">Điền ô đang trống</button>
              <button v-if="tenNguoiDung" type="button" class="btn btn-sm" @click="dienHoTenTuTaiKhoan">Điền họ tên</button>
            </div>
          </div>
          <p class="m-0 mt-2 text-[12px] text-phu">
            Chỉ điền vào ô đang trống, không ghi đè dữ liệu bạn đã nhập. Kiểm tra lại trước khi nộp.
          </p>
          <p v-if="thongBaoDien" class="m-0 mt-1 text-[12.5px] text-xanh" role="status">{{ thongBaoDien }}</p>
        </div>

        <div class="grid sm:grid-cols-3 gap-3">
          <div>
            <label for="input-doi-tuong" class="nhan">Loại chủ thể</label>
            <select id="input-doi-tuong" v-model="form.doi_tuong" class="o">
              <option value="ho_gia_dinh_ca_nhan">Hộ gia đình, cá nhân</option>
              <option value="to_chuc">Tổ chức</option>
            </select>
          </div>
          <div>
            <label for="input-cap-hanh-chinh" class="nhan">Cấp hành chính</label>
            <select id="input-cap-hanh-chinh" v-model="form.cap_hanh_chinh" class="o">
              <option value="xa">Cấp xã</option>
              <option value="tinh">Cấp tỉnh</option>
            </select>
          </div>
          <label class="inline-flex items-center gap-2 mt-6 cursor-pointer">
            <input type="checkbox" v-model="form.trong_kcn" class="w-4 h-4 accent-[rgb(var(--c-cham))]" />
            Trong KCN/KKT
          </label>
        </div>
        <label for="input-ho-ten" class="nhan mt-3">Họ và tên</label>
        <input
          id="input-ho-ten"
          v-model="form.ho_ten"
          required
          maxlength="120"
          autocomplete="name"
          class="o"
          :class="loiHien('ho_ten') ? 'o-loi' : ''"
          :aria-invalid="loiHien('ho_ten') ? 'true' : undefined"
          :aria-describedby="loiHien('ho_ten') ? 'loi-ho-ten' : undefined"
          placeholder="Nguyễn Văn A"
        />
        <p v-if="loiHien('ho_ten')" id="loi-ho-ten" class="m-0 mt-1 text-[12.5px] text-son" role="alert">{{ loiHien("ho_ten") }}</p>
        <div class="grid sm:grid-cols-2 gap-3 mt-3">
          <div>
            <label for="input-cccd" class="nhan">Số CCCD</label>
            <input
              id="input-cccd"
              v-model="form.cccd"
              required
              inputmode="numeric"
              maxlength="20"
              class="o"
              :class="loiHien('cccd') ? 'o-loi' : ''"
              :aria-invalid="loiHien('cccd') ? 'true' : undefined"
              :aria-describedby="loiHien('cccd') ? 'loi-cccd' : undefined"
              placeholder="001090123456"
              @blur="chuanHoaCccdTruong"
            />
            <p v-if="loiHien('cccd')" id="loi-cccd" class="m-0 mt-1 text-[12.5px] text-son" role="alert">{{ loiHien("cccd") }}</p>
          </div>
          <div>
            <label for="input-dien-thoai" class="nhan">Số điện thoại</label>
            <input
              id="input-dien-thoai"
              v-model="form.dien_thoai"
              required
              inputmode="tel"
              maxlength="20"
              autocomplete="tel"
              class="o"
              :class="loiHien('dien_thoai') ? 'o-loi' : ''"
              :aria-invalid="loiHien('dien_thoai') ? 'true' : undefined"
              :aria-describedby="loiHien('dien_thoai') ? 'loi-dien-thoai' : undefined"
              placeholder="0901234567"
              @blur="chuanHoaDienThoaiTruong"
            />
            <p v-if="loiHien('dien_thoai')" id="loi-dien-thoai" class="m-0 mt-1 text-[12.5px] text-son" role="alert">{{ loiHien("dien_thoai") }}</p>
          </div>
        </div>
        </div>

        <div :class="step !== 1 ? 'hidden md:block' : ''">
        <h3 class="muc-con">Công trình</h3>
        <label for="input-dia-chi" class="nhan">Địa chỉ công trình</label>
        <input
          id="input-dia-chi"
          v-model="form.dia_chi_cong_trinh"
          required
          maxlength="255"
          class="o"
          :class="loiHien('dia_chi_cong_trinh') ? 'o-loi' : ''"
          :aria-invalid="loiHien('dia_chi_cong_trinh') ? 'true' : undefined"
          :aria-describedby="loiHien('dia_chi_cong_trinh') ? 'loi-dia-chi' : undefined"
          placeholder="Số 123 Đường Mẫu, Phường A"
        />
        <p v-if="loiHien('dia_chi_cong_trinh')" id="loi-dia-chi" class="m-0 mt-1 text-[12.5px] text-son" role="alert">{{ loiHien("dia_chi_cong_trinh") }}</p>
        <div class="grid sm:grid-cols-3 gap-3 mt-3">
          <div>
            <label for="input-thua-dat" class="nhan">Thửa đất, tờ bản đồ</label>
            <input
              id="input-thua-dat"
              v-model="form.thua_dat"
              required
              maxlength="100"
              class="o"
              :class="loiHien('thua_dat') ? 'o-loi' : ''"
              :aria-invalid="loiHien('thua_dat') ? 'true' : undefined"
              :aria-describedby="loiHien('thua_dat') ? 'loi-thua-dat' : undefined"
              placeholder="Thửa 12, Tờ 34"
            />
            <p v-if="loiHien('thua_dat')" id="loi-thua-dat" class="m-0 mt-1 text-[12.5px] text-son" role="alert">{{ loiHien("thua_dat") }}</p>
          </div>
          <div>
            <label for="input-so-tang" class="nhan">Số tầng</label>
            <input
              id="input-so-tang"
              type="number"
              v-model.number="form.so_tang"
              required
              class="o"
              :class="loiHien('so_tang') ? 'o-loi' : ''"
              :aria-invalid="loiHien('so_tang') ? 'true' : undefined"
              :aria-describedby="loiHien('so_tang') ? 'loi-so-tang' : undefined"
              min="1"
              max="5"
              step="1"
            />
            <p v-if="loiHien('so_tang')" id="loi-so-tang" class="m-0 mt-1 text-[12.5px] text-son" role="alert">{{ loiHien("so_tang") }}</p>
          </div>
          <div>
            <label for="input-dien-tich" class="nhan">Diện tích sàn (m²)</label>
            <input
              id="input-dien-tich"
              type="number"
              step="0.1"
              min="0.1"
              max="100000"
              v-model.number="form.dien_tich_san_m2"
              required
              class="o"
              :class="loiHien('dien_tich_san_m2') ? 'o-loi' : ''"
              :aria-invalid="loiHien('dien_tich_san_m2') ? 'true' : undefined"
              :aria-describedby="loiHien('dien_tich_san_m2') ? 'loi-dien-tich' : undefined"
            />
            <p v-if="loiHien('dien_tich_san_m2')" id="loi-dien-tich" class="m-0 mt-1 text-[12.5px] text-son" role="alert">{{ loiHien("dien_tich_san_m2") }}</p>
          </div>
        </div>
        <label class="inline-flex items-center gap-2 mt-3 cursor-pointer">
          <input type="checkbox" v-model="form.khu_quan_ly_kien_truc" class="w-4 h-4 accent-[rgb(var(--c-cham))]" />
          Công trình nằm trong khu vực có quy chế quản lý kiến trúc
        </label>
        </div>

        <div :class="step !== 2 ? 'hidden md:block' : ''">
        <h3 class="muc-con">Giấy tờ kèm theo</h3>
        <p v-if="loadingRequirements" class="goi-y m-0" role="status">Đang tải danh mục giấy tờ…</p>
        <DocumentChecklist v-else :key="phienBanNhap" v-model="docs" :requirements="requirements" :errors="tatCaLoi" :form-values="form" />
        <p class="goi-y mt-2 mb-0">PDF hoặc DWG, tối đa 20 MB mỗi tệp. Tệp được quét virus trước khi lưu.</p>

        <div v-if="tatCaLoi.length" id="submit-errors" class="thong-bao-loi mt-4" role="alert">
          <b>Hồ sơ chưa đủ điều kiện nộp ({{ tatCaLoi.length }} lỗi)</b>
          <ul class="mt-1 mb-0 pl-5 list-disc">
            <li v-for="(err, idx) in tatCaLoi" :key="idx">{{ err.reason }}</li>
          </ul>
        </div>

        <div class="flex justify-end gap-2 mt-6">
          <button type="button" class="btn min-h-[44px]" @click="$emit('close')">Hủy</button>
          <button type="submit" id="btn-submit-nop-ho-so" class="btn btn-chinh min-h-[44px]" :disabled="submitting || loadingRequirements">
            {{ submitting ? "Đang kiểm tra và nộp…" : "Kiểm tra và nộp hồ sơ" }}
          </button>
        </div>
        </div>
        <p class="goi-y mt-4 mb-0">
          Bản nháp biểu mẫu được tự lưu trên trình duyệt này<template v-if="luuLuc"> lúc {{ ngayGio(luuLuc) }}</template>.
          Tệp đã chọn không được lưu; nộp thành công thì bản nháp bị xóa. Không dùng máy tính dùng chung.
          <button v-if="coBanNhap && !khoiPhuc" type="button" class="btn-lien-ket ml-1" @click="xoaBanNhapNay">Xóa bản nháp</button>
        </p>
        <div class="mt-4 flex justify-between gap-2 md:hidden">
          <button type="button" class="btn min-h-[44px]" :disabled="step === 0" @click="step--">Quay lại</button>
          <button type="button" class="btn min-h-[44px]" :disabled="step === 2" @click="step++">Tiếp tục</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script lang="ts">
import type { DocEntry as DocEntryM } from "../types";
import { formNopTrong as formTrong } from "../utils/nop-ho-so";

/**
 * Bản nháp giữ trong bộ nhớ của trang để đóng/mở hộp không mất dữ liệu và tệp đã chọn.
 * Bản nháp biểu mẫu (không gồm tệp) được tự lưu thêm trong sessionStorage ở phần setup.
 */
const nhap = { form: formTrong(), docs: {} as Record<string, DocEntryM> };
</script>

<script setup lang="ts">
import IconX from "./IconX.vue";
import DocumentChecklist from "./DocumentChecklist.vue";
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import type { DocEntry, DocError, DocRequirement, HoSo, NopHoSoPayload } from "../types";
import { useModal } from "../composables/useModal";
import { formatStatus, getStatusBadgeClass } from "../utils/formatters";
import { ngayGio } from "../utils/labels";
import {
  chuanHoaCccd,
  chuanHoaDienThoai,
  loiCccd,
  loiDiaChi,
  loiDienThoai,
  loiDienTich,
  loiHoTen,
  loiSoTang,
  loiThuaDat,
} from "../utils/validation";
import {
  dienTuHoSo,
  docBanNhap,
  formNopCoDuLieu,
  hopNhatFormNop,
  khoaBanNhap,
  luuBanNhap,
  xoaBanNhap as xoaBanNhapLuu,
} from "../utils/nop-ho-so";

const props = defineProps<{
  submitting: boolean;
  requirements: DocRequirement[];
  errors: DocError[];
  loadingRequirements?: boolean;
  dossiers?: HoSo[];
  tenNguoiDung?: string;
  nguoiDungId?: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", form: NopHoSoPayload, docs: DocEntry[]): void;
  (e: "mo-ho-so", id: string, ma: string): void;
}>();

const luuTru: Storage | null = (() => {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
})();
const khoaNhap = khoaBanNhap(props.nguoiDungId);
const khoiPhuc = ref<number | null>(null);
const luuLuc = ref<number | null>(null);
const form = ref<NopHoSoPayload>(nhap.form);

// Bản nháp trong bộ nhớ trang được ưu tiên; nếu trang vừa tải lại thì khôi phục từ sessionStorage.
if (!formNopCoDuLieu(nhap.form) && luuTru) {
  const ban = docBanNhap(luuTru, khoaNhap);
  if (ban) {
    nhap.form = hopNhatFormNop(ban.form);
    form.value = nhap.form;
    khoiPhuc.value = ban.at;
  }
}

const step = ref(0);
const daThuGui = ref(false);
const thongBaoDien = ref("");
const phienBanNhap = ref(0);

// Mỗi loại giấy trong danh mục có một mục riêng: tệp, ngày cấp/hết hạn, thông tin đối chiếu
const docs = ref<Record<string, DocEntry>>(nhap.docs);

const TRUONG_FORM = [
  "ho_ten",
  "cccd",
  "dien_thoai",
  "dia_chi_cong_trinh",
  "thua_dat",
  "so_tang",
  "dien_tich_san_m2",
] as const;
type TruongForm = (typeof TRUONG_FORM)[number];

const ID_TRUONG: Record<TruongForm, string> = {
  ho_ten: "input-ho-ten",
  cccd: "input-cccd",
  dien_thoai: "input-dien-thoai",
  dia_chi_cong_trinh: "input-dia-chi",
  thua_dat: "input-thua-dat",
  so_tang: "input-so-tang",
  dien_tich_san_m2: "input-dien-tich",
};
const BUOC_TRUONG: Record<TruongForm, number> = {
  ho_ten: 0,
  cccd: 0,
  dien_thoai: 0,
  dia_chi_cong_trinh: 1,
  thua_dat: 1,
  so_tang: 1,
  dien_tich_san_m2: 1,
};

const loiForm = computed<Record<TruongForm, string>>(() => ({
  ho_ten: loiHoTen(form.value.ho_ten),
  cccd: loiCccd(form.value.cccd),
  dien_thoai: loiDienThoai(form.value.dien_thoai),
  dia_chi_cong_trinh: loiDiaChi(form.value.dia_chi_cong_trinh),
  thua_dat: loiThuaDat(form.value.thua_dat),
  so_tang: loiSoTang(form.value.so_tang),
  dien_tich_san_m2: loiDienTich(form.value.dien_tich_san_m2),
}));
const loiFormTatCa = computed(() => TRUONG_FORM.map((t) => loiForm.value[t]).filter(Boolean));
const coBanNhap = computed(() => formNopCoDuLieu(form.value));

function loiHien(truong: TruongForm): string {
  return daThuGui.value ? loiForm.value[truong] : "";
}

function chuanHoaTruong(): void {
  form.value.ho_ten = form.value.ho_ten.trim();
  form.value.cccd = chuanHoaCccd(form.value.cccd);
  form.value.dien_thoai = chuanHoaDienThoai(form.value.dien_thoai);
  form.value.dia_chi_cong_trinh = form.value.dia_chi_cong_trinh.trim();
  form.value.thua_dat = form.value.thua_dat.trim();
}

function chuanHoaCccdTruong(): void {
  form.value.cccd = chuanHoaCccd(form.value.cccd);
}

function chuanHoaDienThoaiTruong(): void {
  form.value.dien_thoai = chuanHoaDienThoai(form.value.dien_thoai);
}

let henLuu: ReturnType<typeof setTimeout> | null = null;

function luuNhapNgay(): void {
  if (!luuTru) return;
  if (luuBanNhap(luuTru, khoaNhap, form.value)) luuLuc.value = Date.now();
}

watch(
  form,
  (v) => {
    nhap.form = v;
    if (henLuu) clearTimeout(henLuu);
    henLuu = setTimeout(luuNhapNgay, 500);
  },
  { deep: true },
);
watch(docs, (v) => (nhap.docs = v), { deep: true });

const hop = ref<HTMLElement | null>(null);
useModal(hop, () => emit("close"));

// Kiểm tra trước trên giao diện: thiếu giấy bắt buộc thì không gửi, chỉ rõ giấy nào
const loiThieu = ref<DocError[]>([]);
const tatCaLoi = computed<DocError[]>(() => [...loiThieu.value, ...props.errors]);

watch(
  () => props.requirements,
  (reqs) => {
    const next: Record<string, DocEntry> = {};
    for (const req of reqs) {
      next[req.loai] = docs.value[req.loai] || { loai: req.loai, file: null, ngay_cap: "", ngay_het_han: "", thong_tin: {} };
    }
    docs.value = next;
  },
  { immediate: true },
);

// Gợi ý hồ sơ cũ của chính chủ đầu tư; ưu tiên hồ sơ cùng CCCD nếu đã nhập.
const hoSoGoiY = computed<HoSo | null>(() => {
  const ds = props.dossiers || [];
  if (!ds.length) return null;
  const cccd = chuanHoaCccd(form.value.cccd);
  if (cccd) {
    const khop = ds.find((d) => chuanHoaCccd(String(d.cccd || "")) === cccd);
    if (khop) return khop;
  }
  return ds[0] || null;
});

const trungHoSo = computed<HoSo[]>(() => {
  const cccd = chuanHoaCccd(form.value.cccd);
  const thua = form.value.thua_dat.trim().toLocaleLowerCase("vi");
  if (!cccd || !thua) return [];
  return (props.dossiers || []).filter(
    (d) =>
      chuanHoaCccd(String(d.cccd || "")) === cccd &&
      String(d.thua_dat || "").trim().toLocaleLowerCase("vi") === thua,
  );
});

function dienTuHoSoGoiY(): void {
  const d = hoSoGoiY.value;
  if (!d) return;
  const kq = dienTuHoSo(form.value, d);
  form.value = kq.form;
  thongBaoDien.value = kq.soO
    ? `Đã điền ${kq.soO} ô từ hồ sơ ${d.ma_ho_so}; kiểm tra lại trước khi nộp.`
    : "Các ô đã có dữ liệu; không ghi đè. Xóa ô cần thay rồi bấm lại nếu muốn điền.";
}

function dienHoTenTuTaiKhoan(): void {
  if (form.value.ho_ten.trim()) {
    thongBaoDien.value = "Ô họ tên đã có dữ liệu; không ghi đè.";
    return;
  }
  form.value.ho_ten = props.tenNguoiDung || "";
  thongBaoDien.value = form.value.ho_ten
    ? "Đã điền họ tên từ tài khoản; kiểm tra lại trước khi nộp."
    : "Tài khoản chưa có họ tên để điền.";
}

function moHoSoTrung(d: HoSo): void {
  emit("mo-ho-so", d.id, d.ma_ho_so);
}

function xoaBanNhapNay(): void {
  if (henLuu) clearTimeout(henLuu);
  if (luuTru) xoaBanNhapLuu(luuTru, khoaNhap);
  nhap.form = formTrong();
  form.value = nhap.form;
  nhap.docs = {};
  const moi: Record<string, DocEntry> = {};
  for (const [loai, entry] of Object.entries(docs.value)) {
    moi[loai] = { ...entry, file: null, ngay_cap: "", ngay_het_han: "", thong_tin: {} };
  }
  docs.value = moi;
  phienBanNhap.value += 1;
  khoiPhuc.value = null;
  luuLuc.value = null;
  daThuGui.value = false;
  thongBaoDien.value = "";
}

function handleSubmit() {
  daThuGui.value = true;
  chuanHoaTruong();
  const truongLoi = TRUONG_FORM.find((t) => loiForm.value[t]);
  if (truongLoi) {
    step.value = BUOC_TRUONG[truongLoi];
    nextTick(() => {
      const el = document.getElementById(ID_TRUONG[truongLoi]);
      el?.focus();
      el?.scrollIntoView?.({ block: "center", behavior: "smooth" });
    });
    return;
  }
  loiThieu.value = props.requirements
    .filter((r) => r.bat_buoc && !docs.value[r.loai]?.file)
    .map((r) => ({ field: "tep", loai_giay: r.loai, reason: `Thiếu ${r.ten}.` }));
  if (loiThieu.value.length) {
    step.value = 2;
    nextTick(() => document.getElementById("document-checklist")?.scrollIntoView?.({ block: "start", behavior: "smooth" }));
    return;
  }
  dangGui = true;
  emit("submit", { ...form.value }, Object.values(docs.value).filter((d) => d.file));
}

// Nộp thành công thì khung app đóng hộp ngay khi còn đang gửi; nộp lỗi thì hộp còn mở khi gửi xong.
let dangGui = false;
watch(
  () => props.submitting,
  (v, cu) => {
    if (cu && !v) dangGui = false;
  },
);
onBeforeUnmount(() => {
  if (henLuu) clearTimeout(henLuu);
  if (dangGui) {
    nhap.form = formTrong();
    nhap.docs = {};
    if (luuTru) xoaBanNhapLuu(luuTru, khoaNhap);
  } else if (luuTru && formNopCoDuLieu(form.value)) {
    luuBanNhap(luuTru, khoaNhap, form.value);
  }
});
</script>

<style scoped>
.o-loi {
  border-color: rgb(var(--c-son) / 0.65) !important;
  background: var(--do-nen);
}
</style>

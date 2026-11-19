<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div class="nen-hop" @click.self="$emit('close')">
    <div ref="hop" tabindex="-1" class="hop max-w-[760px]" role="dialog" aria-modal="true" aria-labelledby="tieu-de-nop">
      <div class="hop-dau">
        <div>
          <h3 id="tieu-de-nop">Nộp hồ sơ cấp phép xây dựng</h3>
          <p class="goi-y m-0 mt-1">Chuẩn bị đủ giấy tờ theo danh mục bên dưới. Hệ thống kiểm tra lại toàn bộ trước khi nhận; thời hạn giải quyết 15 ngày làm việc kể từ khi hồ sơ hợp lệ.</p>
        </div>
        <button type="button" class="nut-dong" aria-label="Đóng" @click="$emit('close')"><IconX /></button>
      </div>

      <form id="form-nop-ho-so" class="hop-than" @submit.prevent="handleSubmit">
        <h4 class="muc-con">Chủ đầu tư</h4>
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
        <input id="input-ho-ten" v-model="form.ho_ten" required autocomplete="name" class="o" placeholder="Nguyễn Văn A" />
        <div class="grid sm:grid-cols-2 gap-3 mt-3">
          <div>
            <label for="input-cccd" class="nhan">Số CCCD</label>
            <input id="input-cccd" v-model="form.cccd" required inputmode="numeric" pattern="[0-9]{12}" title="12 chữ số" class="o" placeholder="001090123456" />
          </div>
          <div>
            <label for="input-dien-thoai" class="nhan">Số điện thoại</label>
            <input id="input-dien-thoai" v-model="form.dien_thoai" required inputmode="tel" autocomplete="tel" class="o" placeholder="0901234567" />
          </div>
        </div>

        <h4 class="muc-con">Công trình</h4>
        <label for="input-dia-chi" class="nhan">Địa chỉ công trình</label>
        <input id="input-dia-chi" v-model="form.dia_chi_cong_trinh" required class="o" placeholder="Số 123 Đường Mẫu, Phường A" />
        <div class="grid sm:grid-cols-3 gap-3 mt-3">
          <div>
            <label for="input-thua-dat" class="nhan">Thửa đất, tờ bản đồ</label>
            <input id="input-thua-dat" v-model="form.thua_dat" required class="o" placeholder="Thửa 12, Tờ 34" />
          </div>
          <div>
            <label for="input-so-tang" class="nhan">Số tầng</label>
            <input id="input-so-tang" type="number" v-model.number="form.so_tang" required class="o" min="1" max="5" />
          </div>
          <div>
            <label for="input-dien-tich" class="nhan">Diện tích sàn (m²)</label>
            <input id="input-dien-tich" type="number" step="0.1" min="0.1" v-model.number="form.dien_tich_san_m2" required class="o" />
          </div>
        </div>
        <label class="inline-flex items-center gap-2 mt-3 cursor-pointer">
          <input type="checkbox" v-model="form.khu_quan_ly_kien_truc" class="w-4 h-4 accent-[rgb(var(--c-cham))]" />
          Công trình nằm trong khu vực có quy chế quản lý kiến trúc
        </label>

        <h4 class="muc-con">Giấy tờ kèm theo</h4>
        <p v-if="loadingRequirements" class="goi-y m-0" role="status">Đang tải danh mục giấy tờ…</p>
        <DocumentChecklist v-else v-model="docs" :requirements="requirements" :errors="tatCaLoi" :form-values="form" />
        <p class="goi-y mt-2 mb-0">PDF hoặc DWG, tối đa 20 MB mỗi tệp. Tệp được quét virus trước khi lưu.</p>

        <div v-if="tatCaLoi.length" id="submit-errors" class="thong-bao-loi mt-4" role="alert">
          <b>Hồ sơ chưa đủ điều kiện nộp ({{ tatCaLoi.length }} lỗi)</b>
          <ul class="mt-1 mb-0 pl-5 list-disc">
            <li v-for="(err, idx) in tatCaLoi" :key="idx">{{ err.reason }}</li>
          </ul>
        </div>

        <div class="flex justify-end gap-2 mt-6">
          <button type="button" class="btn" @click="$emit('close')">Hủy</button>
          <button type="submit" id="btn-submit-nop-ho-so" class="btn btn-chinh" :disabled="submitting || loadingRequirements">
            {{ submitting ? "Đang kiểm tra và nộp…" : "Kiểm tra và nộp hồ sơ" }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script lang="ts">
import type { DocEntry as DocEntryM, NopHoSoPayload as NopHoSoPayloadM } from "../types";

// Khối script thường: chạy một lần cho cả trang, nên bản nháp sống qua các lần mở/đóng hộp.
function formTrong(): NopHoSoPayloadM {
  return {
    ho_ten: "",
    cccd: "",
    dien_thoai: "",
    dia_chi_cong_trinh: "",
    thua_dat: "",
    so_tang: 1,
    dien_tich_san_m2: 100.0,
    khu_quan_ly_kien_truc: true,
    doi_tuong: "ho_gia_dinh_ca_nhan",
    trong_kcn: false,
    cap_hanh_chinh: "xa",
  };
}

/**
 * Bản nháp giữ trong bộ nhớ của trang (không ghi vào trình duyệt vì có CCCD, số điện thoại):
 * đóng hộp giữa chừng rồi mở lại vẫn còn dữ liệu đã nhập và tệp đã chọn; nộp thành công thì xóa.
 */
const nhap = { form: formTrong(), docs: {} as Record<string, DocEntryM> };
</script>

<script setup lang="ts">
import IconX from "./IconX.vue";
import DocumentChecklist from "./DocumentChecklist.vue";
import { computed, onBeforeUnmount, ref, watch } from "vue";
import type { DocEntry, DocError, DocRequirement, NopHoSoPayload } from "../types";
import { useModal } from "../composables/useModal";


const props = defineProps<{
  submitting: boolean;
  requirements: DocRequirement[];
  errors: DocError[];
  loadingRequirements?: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", form: NopHoSoPayload, docs: DocEntry[]): void;
}>();

const form = ref<NopHoSoPayload>(nhap.form);

// Mỗi loại giấy trong danh mục có một mục riêng: tệp, ngày cấp/hết hạn, thông tin đối chiếu
const docs = ref<Record<string, DocEntry>>(nhap.docs);
watch(form, (v) => (nhap.form = v), { deep: true });
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

function handleSubmit() {
  loiThieu.value = props.requirements
    .filter((r) => r.bat_buoc && !docs.value[r.loai]?.file)
    .map((r) => ({ field: "tep", loai_giay: r.loai, reason: `Thiếu ${r.ten}.` }));
  if (loiThieu.value.length) return;
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
  if (dangGui) {
    nhap.form = formTrong();
    nhap.docs = {};
  }
});
</script>

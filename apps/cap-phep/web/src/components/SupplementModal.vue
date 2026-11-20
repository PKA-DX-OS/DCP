<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div class="nen-hop" @click.self="$emit('close')">
    <div ref="hop" tabindex="-1" class="hop max-w-[600px]" role="dialog" aria-modal="true" aria-labelledby="tieu-de-bo-sung">
      <div class="hop-dau">
        <div>
          <h2 id="tieu-de-bo-sung">Bổ sung hồ sơ cấp phép</h2>
          <p class="ma m-0 mt-1 text-[13px]">{{ dossier.ma_ho_so }}</p>
        </div>
        <button type="button" class="nut-dong" aria-label="Đóng" @click="$emit('close')"><IconX /></button>
      </div>

      <div class="hop-than">
        <div v-if="dossier.ly_do_bo_sung" id="box-ly-do-bo-sung" class="thong-bao-vang">
          <b class="font-semibold block mb-0.5">Phường yêu cầu bổ sung</b>
          <span class="whitespace-pre-wrap">{{ dossier.ly_do_bo_sung }}</span>
        </div>
        <p v-if="dossier.han_buoc_at" id="han-bo-sung" :class="['mt-3 mb-0', quaHan && 'text-son font-semibold']">
          Hạn bổ sung: {{ ngayNgan(dossier.han_buoc_at) }}<template v-if="quaHan"> (đã quá hạn)</template>
        </p>

        <form id="form-bo-sung-ho-so" @submit.prevent="handleSubmit">
          <label for="input-bo-sung-dia-chi" class="nhan mt-4">Địa chỉ công trình</label>
          <input v-model="form.dia_chi_cong_trinh" required class="o" id="input-bo-sung-dia-chi" />
          <div class="grid sm:grid-cols-3 gap-3 mt-3">
            <div>
              <label for="input-bo-sung-thua-dat" class="nhan">Thửa đất</label>
              <input v-model="form.thua_dat" required class="o" id="input-bo-sung-thua-dat" />
            </div>
            <div>
              <label for="input-bo-sung-so-tang" class="nhan">Số tầng</label>
              <input type="number" min="1" v-model.number="form.so_tang" required class="o" id="input-bo-sung-so-tang" />
            </div>
            <div>
              <label for="input-bo-sung-dien-tich" class="nhan">Diện tích sàn (m²)</label>
              <input type="number" step="0.1" min="1" v-model.number="form.dien_tich_san_m2" required class="o" id="input-bo-sung-dien-tich" />
            </div>
          </div>

          <label for="file-bo-sung" class="nhan mt-3">Giấy tờ bổ sung</label>
          <input type="file" id="file-bo-sung" class="chon-tep" :accept="DUOI_CHO_PHEP.join(',')" @change="handleFileUpload" />
          <p class="goi-y mt-1 mb-0">PDF, DWG, PNG hoặc JPG, tối đa 20 MB.</p>
          <p v-if="loiTep" id="loi-file-bo-sung" class="text-son text-[13px] mt-1 mb-0" role="alert">{{ loiTep }}</p>
          <p v-if="selectedFileName" class="text-[12.5px] text-xanh mt-1 mb-0">Đã chọn: {{ selectedFileName }}</p>

          <div class="flex justify-end gap-2 mt-6">
            <button type="button" class="btn" @click="$emit('close')">Hủy</button>
            <button type="submit" id="btn-submit-bo-sung" class="btn btn-chinh" :disabled="submitting">
              {{ submitting ? "Đang gửi…" : "Gửi bổ sung" }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import IconX from "./IconX.vue";
import { computed, ref } from "vue";
import type { HoSo } from "../types";
import { useModal } from "../composables/useModal";
import { ngayNgan } from "../utils/labels";

const DUOI_CHO_PHEP = [".pdf", ".dwg", ".png", ".jpg", ".jpeg"];
const TOI_DA_BYTE = 20 * 1024 * 1024;

const props = defineProps<{
  dossier: HoSo;
  submitting: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "submit", payload: { form: any; file?: File | null }): void;
}>();

const form = ref({
  dia_chi_cong_trinh: props.dossier.dia_chi_cong_trinh,
  thua_dat: props.dossier.thua_dat,
  so_tang: props.dossier.so_tang,
  dien_tich_san_m2: props.dossier.dien_tich_san_m2,
  khu_quan_ly_kien_truc: props.dossier.khu_quan_ly_kien_truc,
});

const hop = ref<HTMLElement | null>(null);
useModal(hop, () => emit("close"));

const quaHan = computed(() => {
  const t = props.dossier.han_buoc_at ? new Date(props.dossier.han_buoc_at).getTime() : NaN;
  return !isNaN(t) && t < Date.now();
});

const selectedFile = ref<File | null>(null);
const selectedFileName = ref<string>("");
const loiTep = ref("");

function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) {
    selectedFile.value = null;
    selectedFileName.value = "";
    return;
  }
  const ten = file.name.toLowerCase();
  if (!DUOI_CHO_PHEP.some((d) => ten.endsWith(d))) {
    loiTep.value = `Tệp "${file.name}" không đúng định dạng (PDF, DWG, PNG, JPG).`;
  } else if (file.size > TOI_DA_BYTE) {
    loiTep.value = `Tệp "${file.name}" vượt giới hạn 20 MB.`;
  } else {
    loiTep.value = "";
    selectedFile.value = file;
    selectedFileName.value = file.name;
    return;
  }
  target.value = "";
}

function handleSubmit() {
  emit("submit", { form: { ...form.value }, file: selectedFile.value });
}
</script>

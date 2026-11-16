<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div class="nen-hop" @click.self="$emit('close')">
    <div class="hop max-w-[600px]" role="dialog" aria-modal="true" aria-labelledby="tieu-de-bo-sung">
      <div class="hop-dau">
        <div>
          <h3 id="tieu-de-bo-sung">Bổ sung hồ sơ cấp phép</h3>
          <p class="ma m-0 mt-1 text-[13px]">{{ dossier.ma_ho_so }}</p>
        </div>
        <button type="button" class="nut-dong" aria-label="Đóng" @click="$emit('close')"><IconX /></button>
      </div>

      <div class="hop-than">
        <div v-if="dossier.ly_do_bo_sung" id="box-ly-do-bo-sung" class="thong-bao-vang">
          <b class="font-semibold block mb-0.5">Phường yêu cầu bổ sung</b>
          <span class="whitespace-pre-wrap">{{ dossier.ly_do_bo_sung }}</span>
        </div>

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
          <input type="file" id="file-bo-sung" class="chon-tep" accept=".pdf,.dwg,.png,.jpg,.jpeg" @change="handleFileUpload" />
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
import { ref } from "vue";
import type { HoSo } from "../types";

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

const selectedFile = ref<File | null>(null);
const selectedFileName = ref<string>("");

function handleFileUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    selectedFile.value = target.files[0];
    selectedFileName.value = target.files[0].name;
  } else {
    selectedFile.value = null;
    selectedFileName.value = "";
  }
}

function handleSubmit() {
  emit("submit", { form: { ...form.value }, file: selectedFile.value });
}
</script>

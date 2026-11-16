<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div id="document-checklist">
    <p class="goi-y m-0 mb-3">
      Đã chọn <b class="text-chu">{{ selectedCount }}/{{ requiredCount }}</b> giấy tờ bắt buộc. Tải tệp đính kèm riêng cho từng loại giấy.
    </p>

    <div
      v-for="req in requirements"
      :key="req.loai"
      :id="`doc-${req.loai}`"
      :class="['giay', hasError(req.loai) && 'giay-loi', entry(req.loai).file && 'giay-du']"
    >
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="font-medium text-chu">
            {{ req.ten }}<span v-if="req.bat_buoc" class="text-son" aria-label="bắt buộc"> *</span>
          </div>
          <div class="text-[12.5px] text-phu">
            {{ req.yeu_cau_hieu_luc ? "Phải còn hiệu lực" : req.bat_buoc ? "Bắt buộc" : "Không bắt buộc" }}
          </div>
        </div>
        <span :class="['tt shrink-0', entry(req.loai).file ? 'tt-xanh' : req.bat_buoc ? 'tt-vang' : 'tt-xam']">
          {{ entry(req.loai).file ? "Đã chọn" : req.bat_buoc ? "Còn thiếu" : "Tùy chọn" }}
        </span>
      </div>

      <input
        type="file"
        :id="`file-${req.loai}`"
        :aria-label="`Chọn tệp ${req.ten}`"
        accept=".pdf,.dwg"
        class="chon-tep mt-3"
        @change="onFileSelected(req, $event)"
      />

      <div v-if="req.yeu_cau_hieu_luc" class="grid sm:grid-cols-2 gap-3 mt-3">
        <label class="block">
          <span class="nhan">Ngày cấp</span>
          <input type="date" :id="`ngay-cap-${req.loai}`" v-model="entry(req.loai).ngay_cap" class="o" />
        </label>
        <label class="block">
          <span class="nhan">Ngày hết hạn</span>
          <input type="date" :id="`ngay-het-han-${req.loai}`" v-model="entry(req.loai).ngay_het_han" class="o" />
        </label>
      </div>

      <div v-if="req.thong_tin.length" class="grid sm:grid-cols-2 gap-3 mt-3">
        <label v-for="field in req.thong_tin" :key="field" class="block">
          <span class="nhan">{{ fieldLabel(field) }}</span>
          <input
            :id="`tt-${req.loai}-${field}`"
            v-model="entry(req.loai).thong_tin[field]"
            :type="field === 'dien_tich' || field === 'so_tang' ? 'number' : 'text'"
            class="o"
            :placeholder="placeholder(field)"
          />
        </label>
      </div>

      <p v-if="hasError(req.loai)" class="text-son text-[13px] mt-2 mb-0" role="alert">{{ errorFor(req.loai) }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { DocEntry, DocError, DocRequirement, NopHoSoPayload } from "../types";

const props = defineProps<{
  requirements: DocRequirement[];
  errors: DocError[];
  formValues: NopHoSoPayload;
}>();

const docs = defineModel<Record<string, DocEntry>>({ required: true });

const requiredCount = computed(() => props.requirements.filter((r) => r.bat_buoc).length);
const selectedCount = computed(
  () => props.requirements.filter((r) => r.bat_buoc && docs.value[r.loai]?.file).length,
);

function entry(loai: string): DocEntry {
  return (
    docs.value[loai] || {
      loai,
      file: null,
      ngay_cap: "",
      ngay_het_han: "",
      thong_tin: {},
    }
  );
}

function onFileSelected(req: DocRequirement, event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] || null;
  const current = entry(req.loai);
  current.file = file;
  if (file && Object.keys(current.thong_tin).length === 0) {
    // Chốt giá trị tại thời điểm chọn tệp để phát hiện lệch với form sau đó.
    if (req.thong_tin.includes("ho_ten") && props.formValues.ho_ten) {
      current.thong_tin.ho_ten = props.formValues.ho_ten;
    }
    if (req.thong_tin.includes("cccd") && props.formValues.cccd) {
      current.thong_tin.cccd = props.formValues.cccd;
    }
    if (req.thong_tin.includes("so_thua") && props.formValues.thua_dat) {
      current.thong_tin.so_thua = props.formValues.thua_dat;
    }
    if (req.thong_tin.includes("dien_tich") && props.formValues.dien_tich_san_m2) {
      current.thong_tin.dien_tich = String(props.formValues.dien_tich_san_m2);
    }
    if (req.thong_tin.includes("so_tang") && props.formValues.so_tang) {
      current.thong_tin.so_tang = String(props.formValues.so_tang);
    }
  }
}

function errorsFor(loai: string): DocError[] {
  return props.errors.filter((e) => e.loai_giay === loai);
}

function hasError(loai: string): boolean {
  return errorsFor(loai).length > 0;
}

function errorFor(loai: string): string {
  return errorsFor(loai).map((e) => e.reason).join('; ');
}

function fieldLabel(field: string): string {
  const labels: Record<string, string> = {
    ho_ten: "Họ tên trên đơn",
    cccd: "CCCD trên đơn",
    so_thua: "Số thửa trên giấy đất",
    dien_tich: "Diện tích trên giấy đất (m²)",
    so_tang: "Số tầng trên bản vẽ",
  };
  return labels[field] || field;
}

function placeholder(field: string): string {
  const values: Record<string, string> = {
    ho_ten: "Nguyễn Văn A",
    cccd: "001099001234",
    so_thua: "Thửa 12, Tờ 34",
    dien_tich: "120",
    so_tang: "3",
  };
  return values[field] || "";
}
</script>

<style scoped>
.giay {
  padding: 16px 18px;
  border-radius: 16px;
  background: var(--mat-2);
  border: 1px solid var(--vien-nhat);
  transition: background 500ms var(--em), border-color 500ms var(--em), box-shadow 500ms var(--em);
}
.giay + .giay {
  margin-top: 10px;
}
.giay:hover {
  background: var(--mat);
  border-color: var(--vien);
}
/* Đã chọn tệp: vạch xanh ở mép trái; lỗi từ máy chủ: viền đỏ */
.giay-du {
  box-shadow: inset 2px 0 0 rgb(var(--c-xanh) / 0.8);
}
.giay-loi,
.giay-loi:hover {
  border-color: rgb(var(--c-son) / 0.6);
  background: var(--do-nen);
}
</style>

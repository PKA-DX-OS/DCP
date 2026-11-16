<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div id="modal-break-glass" class="nen-hop" @click.self="$emit('close')">
    <div class="hop max-w-[520px]" role="dialog" aria-modal="true" aria-labelledby="tieu-de-khan">
      <div class="hop-dau">
        <h3 id="tieu-de-khan">Xin truy cập khẩn hồ sơ {{ maHoSo }}</h3>
        <button type="button" class="nut-dong" aria-label="Đóng" @click="$emit('close')"><IconX /></button>
      </div>
      <div class="hop-than">
        <p class="text-phu mt-0 leading-relaxed">
          Bạn chưa được phân công hồ sơ này. Yêu cầu sẽ gửi tới lãnh đạo phường; khi được duyệt, bạn mở được hồ sơ trong thời hạn cho phép.
          Chủ đầu tư sẽ thấy lần truy cập này trong nhật ký hồ sơ.
        </p>
        <label for="txt-break-glass-reason" class="nhan">Lý do</label>
        <textarea
          v-model="reason"
          id="txt-break-glass-reason"
          rows="3"
          required
          class="o"
          placeholder="Ví dụ: hỗ trợ đồng nghiệp thẩm định kết cấu"
        ></textarea>
      </div>
      <div class="hop-chan">
        <button type="button" class="btn" @click="$emit('close')">Hủy</button>
        <button type="button" id="btn-confirm-break-glass" class="btn btn-chinh" :disabled="!reason.trim() || submitting" @click="handleConfirm">
          {{ submitting ? "Đang gửi…" : "Gửi yêu cầu" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import IconX from "./IconX.vue";
import { ref } from "vue";

const props = defineProps<{
  hoSoId: string;
  maHoSo?: string;
  submitting: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "confirm", hoSoId: string, reason: string): void;
}>();

const reason = ref("");

function handleConfirm() {
  if (!reason.value.trim()) return;
  emit("confirm", props.hoSoId, reason.value);
}
</script>

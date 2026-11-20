<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div id="modal-break-glass" class="nen-hop" @click.self="$emit('close')">
    <div ref="hop" tabindex="-1" class="hop max-w-[520px]" role="dialog" aria-modal="true" aria-labelledby="tieu-de-khan">
      <div class="hop-dau">
        <h2 id="tieu-de-khan">Xin truy cập khẩn hồ sơ {{ maHoSo }}</h2>
        <button type="button" class="nut-dong" aria-label="Đóng" @click="$emit('close')"><IconX /></button>
      </div>

      <div v-if="buoc === 1" class="hop-than">
        <p class="text-phu mt-0 leading-relaxed">
          Bạn chưa được phân công hồ sơ này. Yêu cầu sẽ gửi tới lãnh đạo phường; khi được duyệt, bạn mở được hồ sơ trong thời hạn cho phép.
        </p>
        <p class="nhan mb-1">Phạm vi</p>
        <p class="mt-0">Chỉ hồ sơ <b class="ma">{{ maHoSo || hoSoId }}</b>, quyền xem, trong thời hạn lãnh đạo duyệt.</p>
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

      <div v-else class="hop-than">
        <p class="mt-0 leading-relaxed" role="note">
          <b>Lưu ý pháp lý.</b> Mọi lần truy cập khẩn được ghi vào nhật ký không sửa được, kèm lý do và thời điểm;
          chủ đầu tư thấy lần truy cập này trong lịch sử hồ sơ. Chỉ dùng cho nhu cầu công vụ;
          truy cập dữ liệu cá nhân không đúng mục đích có thể bị xử lý theo quy định về bảo vệ dữ liệu cá nhân.
        </p>
        <p class="text-phu">Lý do đã nhập: “{{ reason.trim() }}”</p>
        <label class="flex items-start gap-2">
          <input id="chk-break-glass-ack" v-model="daHieu" type="checkbox" class="mt-1" />
          <span>Tôi hiểu và chịu trách nhiệm về yêu cầu này.</span>
        </label>
      </div>

      <div class="hop-chan">
        <button v-if="buoc === 1" type="button" class="btn" @click="$emit('close')">Hủy</button>
        <button v-else type="button" class="btn" @click="buoc = 1">Quay lại</button>
        <button
          v-if="buoc === 1"
          type="button"
          id="btn-next-break-glass"
          class="btn btn-chinh"
          :disabled="!reason.trim()"
          @click="buoc = 2"
        >
          Tiếp tục
        </button>
        <button
          v-else
          type="button"
          id="btn-confirm-break-glass"
          class="btn btn-chinh"
          :disabled="!daHieu || submitting"
          @click="handleConfirm"
        >
          {{ submitting ? "Đang gửi…" : "Gửi yêu cầu" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import IconX from "./IconX.vue";
import { useModal } from "../composables/useModal";

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
const buoc = ref<1 | 2>(1);
const daHieu = ref(false);
const hop = ref<HTMLElement | null>(null);
useModal(hop, () => emit("close"));

function handleConfirm() {
  if (!reason.value.trim() || !daHieu.value) return;
  emit("confirm", props.hoSoId, reason.value.trim());
}
</script>

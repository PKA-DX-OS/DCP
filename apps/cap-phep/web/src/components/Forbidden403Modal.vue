<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div id="modal-403-forbidden" class="nen-hop" @click.self="$emit('close')">
    <div ref="hop" tabindex="-1" class="hop max-w-[480px]" role="alertdialog" aria-modal="true" aria-labelledby="tieu-de-403" aria-describedby="mo-ta-403">
      <div class="hop-dau">
        <h2 id="tieu-de-403">Bạn chưa có quyền mở hồ sơ này</h2>
        <button type="button" class="nut-dong" aria-label="Đóng" @click="$emit('close')"><IconX /></button>
      </div>
      <div id="mo-ta-403" class="hop-than">
        <p class="m-0 leading-relaxed">
          Hồ sơ <b class="ma">{{ maHoSo }}</b> không được giao cho bạn, nên hệ thống chặn theo phân quyền của phường.
          Nếu cần xem gấp vì công việc, gửi yêu cầu truy cập khẩn để lãnh đạo phường duyệt;
          nếu cho rằng phân công chưa đúng, liên hệ lãnh đạo phường hoặc quản trị viên phường.
        </p>
      </div>
      <div class="hop-chan">
        <button type="button" class="btn" @click="$emit('close')">Đóng</button>
        <button type="button" id="btn-open-break-glass-modal" class="btn btn-chinh" @click="$emit('request-break-glass')">Xin truy cập khẩn</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import IconX from "./IconX.vue";
import { useModal } from "../composables/useModal";

defineProps<{ maHoSo: string }>();
const emit = defineEmits<{ (e: "close"): void; (e: "request-break-glass"): void }>();

const hop = ref<HTMLElement | null>(null);
useModal(hop, () => emit("close"));
</script>

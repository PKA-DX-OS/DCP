<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div id="modal-403-forbidden" class="nen-hop" @click.self="$emit('close')">
    <div class="hop max-w-[480px]" role="alertdialog" aria-modal="true" aria-labelledby="tieu-de-403">
      <div class="hop-dau">
        <h3 id="tieu-de-403">Bạn chưa có quyền mở hồ sơ này</h3>
        <button type="button" class="nut-dong" aria-label="Đóng" @click="$emit('close')"><IconX /></button>
      </div>
      <div class="hop-than">
        <p class="m-0 leading-relaxed">
          Hồ sơ <b class="ma">{{ maHoSo }}</b> không được giao cho bạn. Nếu cần xem gấp vì công việc, gửi yêu cầu truy cập khẩn để lãnh đạo phường duyệt.
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
import IconX from "./IconX.vue";
defineProps<{ maHoSo: string }>();
defineEmits<{ (e: "close"): void; (e: "request-break-glass"): void }>();
</script>

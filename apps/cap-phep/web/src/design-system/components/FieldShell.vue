<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
/** Khung chung của ô nhập: nhãn, gợi ý, lỗi; nối aria-describedby cho ô bên trong. */
defineProps<{ id: string; label?: string; hint?: string; error?: string; required?: boolean }>();
</script>

<template>
  <div class="flex flex-col gap-1">
    <label v-if="label" :for="id" class="text-ds-sm font-semibold text-ds-text">
      {{ label }}<span v-if="required" class="text-ds-danger" aria-hidden="true"> *</span>
    </label>
    <slot />
    <p v-if="error" :id="id + '-loi'" class="text-ds-xs text-ds-danger" role="alert">{{ error }}</p>
    <p v-else-if="hint" :id="id + '-goi-y'" class="text-ds-xs text-ds-muted">{{ hint }}</p>
  </div>
</template>

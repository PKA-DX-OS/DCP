<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import type { ToastKind } from "../../composables/useToast";

/** Một thông báo nổi; hàng đợi và thời gian tự đóng do composables/useToast quản lý. */
const props = defineProps<{ kind: ToastKind; text: string }>();
defineEmits<{ dismiss: [] }>();
const style = computed(
  () =>
    ({
      ok: { cls: "border-ds-success text-ds-success", label: "Thành công" },
      loi: { cls: "border-ds-danger text-ds-danger", label: "Lỗi" },
      canh_bao: { cls: "border-ds-warning text-ds-warning", label: "Cảnh báo" },
      tin: { cls: "border-ds-info text-ds-info", label: "Thông tin" },
    })[props.kind],
);
</script>

<template>
  <div
    :role="kind === 'loi' ? 'alert' : 'status'"
    class="flex w-80 max-w-[calc(100vw-2rem)] items-start gap-3 ds-hop rounded-ds-md border-l-4 p-3"
    :class="style.cls"
  >
    <div class="min-w-0 flex-1">
      <p class="m-0 text-ds-xs font-semibold">{{ style.label }}</p>
      <p class="m-0 text-ds-sm text-ds-text">{{ text }}</p>
    </div>
    <button
      type="button"
      class="ds-focus -m-1 flex h-8 w-8 items-center justify-center rounded-ds-sm text-ds-muted hover:bg-ds-surface-2"
      aria-label="Đóng thông báo"
      @click="$emit('dismiss')"
    >
      ✕
    </button>
  </div>
</template>

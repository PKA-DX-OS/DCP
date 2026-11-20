<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, ref, useId } from "vue";
import { checkFile, formatBytes, type FileRule } from "../files";

/**
 * Chọn hoặc kéo thả tệp. Component chỉ kiểm loại và kích thước rồi phát sự kiện `select`;
 * việc tải lên (qua dịch vụ files) do nơi dùng làm và báo tiến độ qua prop `progress`.
 */
const props = withDefaults(
  defineProps<{
    label: string;
    hint?: string;
    accept?: string[];
    maxBytes?: number;
    multiple?: boolean;
    disabled?: boolean;
    /** 0–100 khi đang tải, null khi không tải */
    progress?: number | null;
  }>(),
  { multiple: false, disabled: false, progress: null },
);
const emit = defineEmits<{ select: [files: File[]] }>();
const uid = useId();
const keo = ref(false);
const loi = ref<string[]>([]);
const rule = computed<FileRule>(() => ({ accept: props.accept, maxBytes: props.maxBytes }));
const moTa = computed(() => {
  const parts: string[] = [];
  if (props.accept?.length) parts.push(`Loại: ${props.accept.join(", ")}`);
  if (props.maxBytes) parts.push(`tối đa ${formatBytes(props.maxBytes)}`);
  return parts.join(", ");
});

function nhan(list: FileList | null) {
  if (!list || props.disabled) return;
  const files = Array.from(list).slice(0, props.multiple ? undefined : 1);
  loi.value = files.map((f) => checkFile(f, rule.value)).filter((x): x is string => !!x);
  const ok = files.filter((f) => !checkFile(f, rule.value));
  if (ok.length) emit("select", ok);
}
function onDrop(e: DragEvent) {
  keo.value = false;
  nhan(e.dataTransfer?.files ?? null);
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <label
      :for="uid"
      class="flex cursor-pointer flex-col items-center gap-1 rounded-ds-md border-2 border-dashed px-4 py-6 text-center transition-colors focus-within:outline focus-within:outline-2 focus-within:outline-offset-2"
      :class="[
        keo ? 'border-ds-brand bg-ds-brand/10' : 'border-ds-border bg-ds-surface hover:bg-ds-surface-2',
        disabled ? 'cursor-not-allowed opacity-60' : '',
      ]"
      @dragover.prevent="keo = !disabled"
      @dragleave="keo = false"
      @drop.prevent="onDrop"
    >
      <span class="text-ds-base font-semibold text-ds-text">{{ label }}</span>
      <span class="text-ds-sm text-ds-muted">Kéo thả tệp vào đây hoặc bấm để chọn</span>
      <span v-if="moTa || hint" class="text-ds-xs text-ds-muted">{{ hint || moTa }}</span>
      <input
        :id="uid"
        type="file"
        class="sr-only"
        :accept="accept?.join(',')"
        :multiple="multiple"
        :disabled="disabled"
        @change="nhan(($event.target as HTMLInputElement).files); ($event.target as HTMLInputElement).value = ''"
      />
    </label>
    <div
      v-if="progress !== null"
      class="h-2 overflow-hidden rounded-full bg-ds-surface-2"
      role="progressbar"
      :aria-valuenow="Math.round(progress)"
      aria-valuemin="0"
      aria-valuemax="100"
      aria-label="Tiến độ tải lên"
    >
      <div class="h-full bg-ds-brand transition-all" :style="{ width: `${Math.min(100, Math.max(0, progress))}%` }" />
    </div>
    <p v-for="l in loi" :key="l" class="m-0 text-ds-xs text-ds-danger" role="alert">{{ l }}</p>
  </div>
</template>

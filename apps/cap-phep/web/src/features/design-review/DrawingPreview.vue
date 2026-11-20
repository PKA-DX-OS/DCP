<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { downloadFile } from "../../api/files";
import { Drawer, PdfViewer } from "../../design-system";
import type { BanVe } from "./types";

const props = defineProps<{ drawing?: BanVe | null; token: string }>();
const open = defineModel<boolean>("open", { default: false });

const src = ref("");
const loading = ref(false);
const error = ref("");

function donUrl() {
  if (src.value) URL.revokeObjectURL(src.value);
  src.value = "";
}

async function tai() {
  donUrl();
  error.value = "";
  if (!props.drawing?.file_id) return;
  loading.value = true;
  try {
    const blob = await downloadFile(props.token, `/files/${encodeURIComponent(props.drawing.file_id)}/download`);
    if (blob.type && !blob.type.toLowerCase().includes("pdf")) {
      error.value = `Tệp ${blob.type} không phải PDF nên chưa xem trước được. Hãy tải về để mở.`;
      return;
    }
    src.value = URL.createObjectURL(blob);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được bản vẽ";
  } finally {
    loading.value = false;
  }
}

watch(
  [open, () => props.drawing?.id],
  ([mo]) => {
    if (mo && props.drawing) void tai();
    else donUrl();
  },
  { immediate: true },
);
onBeforeUnmount(donUrl);
</script>

<template>
  <Drawer v-model:open="open" :title="drawing?.ten || 'Xem bản vẽ'" width="min(920px, 100vw)">
    <div id="design-review-preview" class="h-full">
      <p v-if="loading" class="text-ds-sm text-ds-muted">Đang tải bản vẽ…</p>
      <div v-else-if="error" class="rounded-ds-sm border border-ds-warning/40 bg-ds-warning/10 p-3 text-ds-sm text-ds-text">
        {{ error }}
      </div>
      <PdfViewer v-else-if="src" :src="src" :title="drawing?.ten || 'Bản vẽ'" :filename="`${drawing?.ten || 'ban-ve'}.pdf`" />
    </div>
  </Drawer>
</template>

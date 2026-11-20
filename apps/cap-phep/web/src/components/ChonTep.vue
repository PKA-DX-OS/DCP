<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { ref } from "vue";

/**
 * Ô chọn tệp có chữ tiếng Việt. Ô gốc của trình duyệt hiện "Choose File / No file chosen" theo ngôn
 * ngữ máy, nên ẩn ô gốc (vẫn nhận focus bàn phím) và hiện nút cùng tên tệp. Thuộc tính và sự kiện
 * (accept, id, aria-*, @change) chuyển thẳng xuống ô gốc nên nơi dùng giữ nguyên cách xử lý.
 */
defineOptions({ inheritAttrs: false });
const props = withDefaults(defineProps<{ nhan?: string }>(), { nhan: "Chọn tệp" });
const input = ref<HTMLInputElement | null>(null);
const tenTep = ref("");

function capNhat(e: Event): void {
  const t = (e.target as HTMLInputElement).files;
  tenTep.value = t && t.length ? Array.from(t).map((f) => f.name).join(", ") : "";
}

/** Bỏ tệp đã chọn (sau khi nộp xong). */
function xoa(): void {
  if (input.value) input.value.value = "";
  tenTep.value = "";
}

defineExpose({ xoa, input });
</script>

<template>
  <span class="chon-tep-vn">
    <label class="chon-tep-nut">
      <input ref="input" type="file" class="sr-only" v-bind="$attrs" @change="capNhat" />
      <span aria-hidden="true">{{ props.nhan }}</span>
    </label>
    <span class="chon-tep-ten" aria-live="polite">{{ tenTep || "Chưa chọn tệp" }}</span>
  </span>
</template>

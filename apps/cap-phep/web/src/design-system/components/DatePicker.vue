<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, useId } from "vue";
import FieldShell from "./FieldShell.vue";
import { fieldClasses } from "../variants";
import { isoToVn } from "../files";

/** Chọn ngày bằng ô date của trình duyệt; giá trị v-model là yyyy-mm-dd, hiển thị kèm dd/mm/yyyy. */
const props = defineProps<{
  label?: string;
  hint?: string;
  error?: string;
  min?: string;
  max?: string;
  required?: boolean;
  disabled?: boolean;
  id?: string;
}>();
const model = defineModel<string>();
const autoId = useId();
const fid = computed(() => props.id || autoId);
const goiY = computed(() => (model.value ? `Ngày đã chọn: ${isoToVn(model.value)}` : props.hint));
const describedBy = computed(() => (props.error ? fid.value + "-loi" : goiY.value ? fid.value + "-goi-y" : undefined));
</script>

<template>
  <FieldShell :id="fid" :label="label" :hint="goiY" :error="error" :required="required">
    <input
      :id="fid"
      v-model="model"
      type="date"
      lang="vi"
      :min="min"
      :max="max"
      :required="required"
      :disabled="disabled"
      :aria-invalid="!!error || undefined"
      :aria-describedby="describedBy"
      :class="fieldClasses('md', !!error)"
    />
  </FieldShell>
</template>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, useId } from "vue";
import FieldShell from "./FieldShell.vue";
import { fieldClasses } from "../variants";

const props = withDefaults(
  defineProps<{
    label?: string;
    hint?: string;
    error?: string;
    placeholder?: string;
    rows?: number;
    maxlength?: number;
    required?: boolean;
    disabled?: boolean;
    id?: string;
  }>(),
  { rows: 4 },
);
const model = defineModel<string>();
const autoId = useId();
const fid = computed(() => props.id || autoId);
const describedBy = computed(() => (props.error ? fid.value + "-loi" : props.hint ? fid.value + "-goi-y" : undefined));
/* Bỏ chiều cao cố định của ô một dòng, giữ viền, nền, chữ */
const cls = computed(() => fieldClasses("md", !!props.error).replace("h-11", "h-auto") + " py-2");
</script>

<template>
  <FieldShell :id="fid" :label="label" :hint="hint" :error="error" :required="required">
    <textarea
      :id="fid"
      v-model="model"
      :rows="rows"
      :maxlength="maxlength"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :aria-invalid="!!error || undefined"
      :aria-describedby="describedBy"
      :class="cls"
    />
    <p v-if="maxlength" class="self-end text-ds-xs text-ds-muted">{{ (model || "").length }}/{{ maxlength }}</p>
  </FieldShell>
</template>

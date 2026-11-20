<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, useId } from "vue";
import FieldShell from "./FieldShell.vue";
import { fieldClasses, type Size } from "../variants";

const props = withDefaults(
  defineProps<{
    label?: string;
    hint?: string;
    error?: string;
    type?: string;
    size?: Size;
    placeholder?: string;
    required?: boolean;
    disabled?: boolean;
    id?: string;
  }>(),
  { type: "text", size: "md" },
);
const model = defineModel<string | number>();
const autoId = useId();
const fid = computed(() => props.id || autoId);
const describedBy = computed(() => (props.error ? fid.value + "-loi" : props.hint ? fid.value + "-goi-y" : undefined));
</script>

<template>
  <FieldShell :id="fid" :label="label" :hint="hint" :error="error" :required="required">
    <input
      :id="fid"
      v-model="model"
      :type="type"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :aria-invalid="!!error || undefined"
      :aria-describedby="describedBy"
      :class="fieldClasses(size, !!error)"
    />
  </FieldShell>
</template>

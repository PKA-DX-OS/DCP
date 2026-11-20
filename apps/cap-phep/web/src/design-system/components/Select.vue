<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, useId } from "vue";
import FieldShell from "./FieldShell.vue";
import { fieldClasses, type Size } from "../variants";

export interface SelectOption {
  value: string | number;
  label: string;
  disabled?: boolean;
}

const props = withDefaults(
  defineProps<{
    options: SelectOption[];
    label?: string;
    hint?: string;
    error?: string;
    placeholder?: string;
    size?: Size;
    required?: boolean;
    disabled?: boolean;
    id?: string;
  }>(),
  { size: "md" },
);
const model = defineModel<string | number>();
const autoId = useId();
const fid = computed(() => props.id || autoId);
const describedBy = computed(() => (props.error ? fid.value + "-loi" : props.hint ? fid.value + "-goi-y" : undefined));
</script>

<template>
  <FieldShell :id="fid" :label="label" :hint="hint" :error="error" :required="required">
    <select
      :id="fid"
      v-model="model"
      :required="required"
      :disabled="disabled"
      :aria-invalid="!!error || undefined"
      :aria-describedby="describedBy"
      :class="fieldClasses(size, !!error)"
    >
      <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
      <option v-for="o in options" :key="o.value" :value="o.value" :disabled="o.disabled">{{ o.label }}</option>
    </select>
  </FieldShell>
</template>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, useId } from "vue";

const props = defineProps<{ label: string; hint?: string; disabled?: boolean; id?: string }>();
const model = defineModel<boolean>({ default: false });
const autoId = useId();
const fid = computed(() => props.id || autoId);
</script>

<template>
  <div class="flex items-start gap-2">
    <input
      :id="fid"
      v-model="model"
      type="checkbox"
      :disabled="disabled"
      class="ds-focus mt-0.5 h-5 w-5 shrink-0 rounded border-ds-border accent-[rgb(var(--ds-brand))]"
    />
    <label :for="fid" class="text-ds-base text-ds-text">
      {{ label }}
      <span v-if="hint" class="block text-ds-xs text-ds-muted">{{ hint }}</span>
    </label>
  </div>
</template>

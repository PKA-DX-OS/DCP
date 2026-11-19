<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import { buttonClasses, type ButtonVariant, type Size } from "../variants";

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariant;
    size?: Size;
    block?: boolean;
    loading?: boolean;
    disabled?: boolean;
    type?: "button" | "submit" | "reset";
  }>(),
  { variant: "primary", size: "md", block: false, loading: false, disabled: false, type: "button" },
);
const cls = computed(() => buttonClasses(props.variant, props.size, props.block));
</script>

<template>
  <button :type="type" :class="cls" :disabled="disabled || loading" :aria-busy="loading || undefined">
    <span
      v-if="loading"
      class="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent"
      aria-hidden="true"
    />
    <slot />
  </button>
</template>

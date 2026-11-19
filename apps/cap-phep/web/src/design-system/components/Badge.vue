<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import { badgeClasses, type Tone } from "../variants";

const props = withDefaults(defineProps<{ tone?: Tone; size?: "sm" | "md"; dot?: boolean }>(), {
  tone: "neutral",
  size: "md",
  dot: false,
});
const cls = computed(() => badgeClasses(props.tone, props.size));
</script>

<template>
  <span :class="cls">
    <span v-if="dot" class="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
    <slot />
  </span>
</template>

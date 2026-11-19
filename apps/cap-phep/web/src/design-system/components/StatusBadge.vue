<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import Badge from "./Badge.vue";
import { statusTone, type Tone } from "../variants";

/** Nhãn trạng thái: màu theo nhóm trạng thái chung, hoặc theo `tone` nếu app chỉ định. */
const props = defineProps<{ status: string; label?: string; tone?: Tone; size?: "sm" | "md" }>();
const tone = computed(() => props.tone || statusTone(props.status));
</script>

<template>
  <Badge :tone="tone" :size="size" dot>{{ label || status }}</Badge>
</template>

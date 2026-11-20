<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed } from "vue";
import Badge from "./Badge.vue";
import { roleLabel, roleTone } from "../variants";

const props = defineProps<{ role: string; label?: string }>();
const text = computed(() => props.label || roleLabel(props.role));
</script>

<template>
  <Badge :tone="roleTone(role)" size="sm" :title="role">{{ text }}</Badge>
</template>

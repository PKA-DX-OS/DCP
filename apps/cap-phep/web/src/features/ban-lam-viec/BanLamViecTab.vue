<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import WorkspaceView from "../../views/WorkspaceView.vue";
import { useFeatureContext } from "../context";

const { moHoSo } = useFeatureContext();
</script>

<template>
  <WorkspaceView @mo-ho-so="moHoSo" />
</template>

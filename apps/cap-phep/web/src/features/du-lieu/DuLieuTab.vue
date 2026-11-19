<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import ConsentView from "../../views/ConsentView.vue";
import { useFeatureContext } from "../context";

const { cd } = useFeatureContext();
</script>

<template>
  <ConsentView
    :dsar-list="cd.dsarList.value"
    :consent-list="cd.consents.value"
    @save-consents="cd.luuDongY"
    @dsar="cd.guiYeuCauDuLieu"
  />
</template>

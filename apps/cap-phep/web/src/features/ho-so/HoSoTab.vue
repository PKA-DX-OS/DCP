<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import DossiersView from "../../views/DossiersView.vue";
import { useFeatureContext } from "../context";
import type { HoSo } from "../../types";

const { cd, moHoSo, moNopHoSo, moBoSung } = useFeatureContext();
</script>

<template>
  <DossiersView
    :dossiers="cd.dossiers.value"
    :error-msg="cd.loi.value"
    :loading="cd.dangTai.value"
    :is-applicant="true"
    @create-dossier="moNopHoSo()"
    @refresh="cd.taiHoSo()"
    @view-detail="(d: HoSo) => moHoSo(d.id, d.ma_ho_so)"
    @supplement="moBoSung"
    @open-by-code="(ma: string) => moHoSo(ma, ma)"
  />
</template>

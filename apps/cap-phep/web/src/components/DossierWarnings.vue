<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { confirmDossierWarnings, fetchDossierWarnings } from "../api/planning";
import { readRoles } from "../auth";
import { notify } from "../composables/useToast";

const props = defineProps<{ dossier: any; token: string; vaiTro?: string[] }>();

/** DB chỉ cho ba vai nghiệp vụ xác nhận; các vai khác chỉ được xem cảnh báo. */
const VAI_XAC_NHAN = ["app:cap-phep:mot-cua", "app:cap-phep:tham-dinh", "app:cap-phep:lanh-dao"];
const coTheXacNhan = computed(() => (props.vaiTro ?? readRoles(props.token)).some((r) => VAI_XAC_NHAN.includes(r)));

const duLieu = ref<any>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const ghiChu = ref("");

async function tai() {
  loading.value = true;
  error.value = "";
  try {
    duLieu.value = await fetchDossierWarnings(props.token, props.dossier.id);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được cảnh báo hồ sơ";
  } finally {
    loading.value = false;
  }
}

async function xacNhan() {
  saving.value = true;
  try {
    duLieu.value = await confirmDossierWarnings(props.token, props.dossier.id, ghiChu.value.trim());
    notify("Đã xác nhận cảnh báo hồ sơ", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không xác nhận được cảnh báo", "loi");
  } finally {
    saving.value = false;
  }
}

onMounted(tai);
</script>

<template>
  <section v-if="loading || error || duLieu?.items?.length" id="block-dossier-warnings" class="mt-4 p-3 rounded-[10px] border border-vien bg-mat" aria-labelledby="tieu-de-canh-bao">
    <div class="flex flex-wrap items-baseline justify-between gap-2 mb-2">
      <h3 id="tieu-de-canh-bao" class="text-[13px] font-semibold m-0">Cảnh báo hồ sơ</h3>
      <span class="goi-y">Cảnh báo không chặn hồ sơ hợp pháp</span>
    </div>
    <p v-if="loading" class="text-phu m-0">Đang tải cảnh báo…</p>
    <p v-else-if="error" class="canh-bao m-0">{{ error }}</p>
    <template v-else>
      <ul class="list-none m-0 p-0 text-[13px]">
        <li v-for="(w, i) in duLieu.items" :key="i" class="flex flex-wrap items-center gap-2 py-1 border-b border-vien-nhat">
          <span :class="w.severity === 'error' ? 'tt tt-do' : 'tt tt-vang'">{{ w.severity === "error" ? "Lỗi" : "Cảnh báo" }}</span>
          <span>{{ w.reason }}</span>
          <span v-if="w.legal_citation_key" class="goi-y">· {{ w.legal_citation_key }}</span>
        </li>
      </ul>
      <p v-if="duLieu.xac_nhan_at" class="text-[13px] mt-2 mb-0">
        Đã xác nhận lúc {{ new Date(duLieu.xac_nhan_at).toLocaleString("vi-VN") }}<template v-if="duLieu.ghi_chu"> — {{ duLieu.ghi_chu }}</template>
      </p>
      <div v-else-if="coTheXacNhan" class="mt-2 flex flex-wrap items-end gap-2">
        <label class="block flex-1 min-w-[220px]">
          <span class="nhan">Ghi chú xác nhận (không bắt buộc)</span>
          <input v-model="ghiChu" class="o w-full" maxlength="2000" />
        </label>
        <button id="btn-confirm-warnings" class="btn btn-sm btn-chinh" :disabled="saving" @click="xacNhan">
          {{ saving ? "Đang lưu…" : "Xác nhận cảnh báo" }}
        </button>
      </div>
      <p v-else class="goi-y mt-2 mb-0">
        Chỉ cán bộ một cửa, thẩm định hoặc lãnh đạo được xác nhận cảnh báo. Cảnh báo không chặn hồ sơ hợp pháp.
      </p>
    </template>
  </section>
</template>

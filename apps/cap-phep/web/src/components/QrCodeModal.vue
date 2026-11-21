<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import QRCode from "qrcode";
import IconX from "./IconX.vue";
import { useModal } from "../composables/useModal";
import { notify } from "../composables/useToast";

const props = withDefaults(defineProps<{ url: string; ma: string; tieuDe?: string }>(), {
  tieuDe: "QR tra cứu giấy phép",
});
const emit = defineEmits<{ (e: "close"): void }>();

const hop = ref<HTMLElement | null>(null);
const anh = ref("");
const loi = ref("");
const dangTai = ref(true);
const daChep = ref(false);
const tenFileQr = computed(() => `qr-${props.ma.replace(/[^a-zA-Z0-9._-]+/g, "-")}.png`);

useModal(hop, () => emit("close"));

onMounted(async () => {
  try {
    anh.value = await QRCode.toDataURL(props.url, {
      width: 280,
      margin: 1,
      color: { dark: "#0b1322", light: "#ffffff" },
      errorCorrectionLevel: "M",
    });
  } catch (e) {
    loi.value = e instanceof Error ? e.message : "Không tạo được mã QR";
  } finally {
    dangTai.value = false;
  }
});

async function chepLienKet(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.url);
    daChep.value = true;
    setTimeout(() => (daChep.value = false), 2000);
  } catch {
    notify("Trình duyệt không cho chép tự động", "loi");
  }
}
</script>

<template>
  <div class="nen-hop" @click.self="$emit('close')">
    <div ref="hop" class="hop max-w-[440px] p-5" role="dialog" aria-modal="true" aria-labelledby="tieu-de-qr">
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="mo m-0">Tra cứu công khai</p>
          <h2 id="tieu-de-qr" class="m-0 text-[20px] font-semibold">{{ tieuDe }}</h2>
          <p class="ma m-0 mt-1">{{ ma }}</p>
        </div>
        <button type="button" class="nut-dong" aria-label="Đóng" @click="$emit('close')"><IconX /></button>
      </div>

      <div class="mt-4 rounded-[16px] border border-vien-nhat bg-white p-4 text-center">
        <p v-if="dangTai" class="m-0 py-12 text-[13px] text-slate-600" role="status">Đang tạo mã QR…</p>
        <p v-else-if="loi" class="m-0 py-8 text-[13px] text-red-700" role="alert">{{ loi }}</p>
        <img v-else :src="anh" alt="Mã QR tra cứu giấy phép" class="mx-auto block h-auto w-full max-w-[280px]" />
      </div>

      <p class="goi-y mt-3">Quét mã để mở trang tra cứu công khai. Không chứa CCCD hay dữ liệu cá nhân.</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <button type="button" class="btn btn-sm" @click="chepLienKet">{{ daChep ? "Đã chép" : "Chép liên kết" }}</button>
        <a v-if="anh" :href="anh" :download="tenFileQr" class="btn btn-sm">Tải ảnh QR</a>
        <a :href="url" target="_blank" rel="noopener" class="btn btn-sm">Mở trang tra cứu</a>
      </div>
    </div>
  </div>
</template>

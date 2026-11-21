<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <section class="max-w-[760px]">
    <h1 class="tieu-de-trang">Dữ liệu cá nhân</h1>
    <p class="text-phu text-[16px] mt-2">
      Bạn quyết định phường được dùng dữ liệu của bạn vào việc gì, và có thể yêu cầu xem, sửa hoặc xóa dữ liệu bất cứ lúc nào.
      <a v-if="privacyUrl" :href="privacyUrl" target="_blank" rel="noopener" id="lnk-chinh-sach-rieng-tu">Đọc chính sách riêng tư</a>
    </p>

    <div class="the mt-5">
      <h2 class="text-[15px] font-semibold m-0 px-5 pt-4 pb-1">Đồng thuận xử lý dữ liệu</h2>
      <ul class="list-none m-0 p-0">
        <li v-for="c in consentItems" :key="c.key" class="px-5 py-3.5 border-b border-vien-nhat last:border-b-0">
          <label class="flex items-start gap-3 cursor-pointer">
            <input type="checkbox" v-model="consents[c.key]" class="mt-1 w-4 h-4 accent-[rgb(var(--c-cham))]" />
            <span>
              <span class="font-medium block">{{ c.title }}</span>
              <span class="text-phu text-[13px] block">{{ c.desc }}</span>
              <span class="text-phu text-[12.5px] block mt-0.5">Thời hạn lưu: {{ c.luu }}</span>
            </span>
          </label>
        </li>
      </ul>
      <div v-if="canXacNhanRut" class="px-5 py-4 border-t border-vien-nhat" role="alertdialog" aria-labelledby="tieu-de-rut">
        <p id="tieu-de-rut" class="m-0 font-medium">Rút đồng ý: {{ mucRut.map((c) => c.title).join(", ") }}?</p>
        <p class="text-phu text-[13px] mt-1 mb-3">
          Sau khi rút, phường ngừng dùng dữ liệu cho mục đích này; dữ liệu đã gắn với hồ sơ đã nộp vẫn lưu theo quy định lưu trữ.
        </p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn" @click="canXacNhanRut = false">Giữ nguyên</button>
          <button type="button" id="btn-confirm-withdraw" class="btn btn-nguy" @click="luuThat">Xác nhận rút</button>
        </div>
      </div>
      <div v-else class="px-5 py-4 border-t border-vien-nhat flex items-center justify-end gap-3">
        <span v-if="consentStatusMsg" class="text-xanh text-[13px]" role="status">{{ consentStatusMsg }}</span>
        <button type="button" id="btn-save-consents" class="btn btn-chinh" :disabled="!coThayDoi" @click="saveConsents">Lưu lựa chọn</button>
      </div>
    </div>

    <div class="the mt-5 p-5">
      <h2 class="text-[15px] font-semibold m-0">Yêu cầu về dữ liệu của bạn</h2>
      <p class="text-phu text-[13px] mt-1">Phường xác nhận trong 2 ngày làm việc và giải quyết trong thời hạn luật định.</p>
      <label for="txt-dsar-note" class="nhan mt-3">Nội dung yêu cầu</label>
      <textarea v-model="dsarNote" id="txt-dsar-note" rows="2" class="o" placeholder="Ví dụ: cung cấp toàn bộ dữ liệu cá nhân phường đang lưu về tôi"></textarea>
      <div class="flex flex-wrap gap-2 mt-3">
        <button type="button" id="btn-dsar-access" class="btn" @click="$emit('dsar', 'access', dsarNote)">Yêu cầu cung cấp dữ liệu</button>
        <button type="button" id="btn-dsar-withdraw" class="btn" @click="$emit('dsar', 'withdraw', dsarNote)">Rút đồng thuận</button>
        <button type="button" id="btn-dsar-erase" class="btn btn-nguy" @click="$emit('dsar', 'erase', dsarNote)">Yêu cầu xóa dữ liệu</button>
      </div>

      <div v-if="dsarList.length > 0" class="overflow-x-auto mt-5 -mx-5 border-t border-vien-nhat">
        <table class="bang" id="table-dsar">
          <thead>
            <tr>
              <th>Yêu cầu</th>
              <th>Trạng thái</th>
              <th>Ngày gửi</th>
              <th>Hạn xác nhận</th>
              <th>Hạn giải quyết</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="req in dsarList" :key="req.id">
              <td class="whitespace-nowrap" :data-loai="req.type">{{ tenYeuCauDuLieu(req.type) }}</td>
              <td class="whitespace-nowrap"><span class="tt tt-lam">{{ trangThai(req.status) }}</span></td>
              <td class="whitespace-nowrap">{{ ngayNgan(req.received_at) }}</td>
              <td class="whitespace-nowrap text-phu">
                {{ ngayNgan(req.ack_due_at) }}
                <span v-if="req.status === 'received' && daQua(req.ack_due_at)" class="block text-[12px] text-son">Phường chưa xác nhận, đã quá hạn</span>
              </td>
              <td class="whitespace-nowrap">
                {{ ngayNgan(req.due_at) }}
                <span v-if="!req.closed_at && daQua(req.due_at)" class="block text-[12px] text-son">Đã quá hạn</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { SOURCE_URL } from "../config";
import { ngayNgan, tenYeuCauDuLieu } from "../utils/labels";

function daQua(iso: string | null | undefined): boolean {
  return !!iso && new Date(iso).getTime() < Date.now();
}

const props = defineProps<{
  dsarList: any[];
  /** Bản ghi đồng ý hiện có (core.consents); tùy chọn, dùng để hiện đúng trạng thái đang bật. */
  consentList?: { purpose: string; withdrawn_at?: string | null }[];
}>();

/** Chính sách riêng tư nằm trong kho mã nguồn công khai (docs/privacy.md). */
const privacyUrl = SOURCE_URL ? `${SOURCE_URL.replace(/\/+$/, "")}/blob/main/docs/privacy.md` : "";

const emit = defineEmits<{
  (e: "save-consents", consents: any): void;
  (e: "dsar", action: string, note?: string): void;
}>();

const dsarNote = ref("");

type ConsentKey = "identity" | "notification" | "iot_monitoring";
const consentItems: { key: ConsentKey; title: string; desc: string; luu: string }[] = [
  {
    key: "identity",
    title: "Đối chiếu danh tính",
    desc: "Dùng họ tên và số CCCD để đối chiếu hồ sơ với thông tin thửa đất.",
    luu: "cùng hồ sơ cấp phép, theo thời hạn lưu trữ hồ sơ hành chính.",
  },
  {
    key: "notification",
    title: "Nhận thông báo tiến độ",
    desc: "Nhận tin nhắn khi hồ sơ cần bổ sung hoặc đã được cấp phép.",
    luu: "đến khi bạn rút đồng ý.",
  },
  {
    key: "iot_monitoring",
    title: "Giám sát công trường bằng cảm biến",
    desc: "Thu số đo tiếng ồn, bụi tại công trình để phường kiểm tra khi vượt ngưỡng.",
    luu: "trong thời gian thi công công trình.",
  },
];

function trangThai(st: string): string {
  const map: Record<string, string> = { received: "Đã tiếp nhận", acknowledged: "Đã xác nhận", in_progress: "Đang xử lý", done: "Đã giải quyết", completed: "Đã giải quyết", rejected: "Từ chối" };
  return map[st] || st;
}

function tuDanhSach(): Record<ConsentKey, boolean> {
  const dangBat = new Set((props.consentList || []).filter((c) => !c.withdrawn_at).map((c) => c.purpose));
  return { identity: dangBat.has("identity"), notification: dangBat.has("notification"), iot_monitoring: dangBat.has("iot_monitoring") };
}

/** Trạng thái đã lưu (đối chiếu để biết mục nào bị bỏ chọn) và lựa chọn đang sửa. */
const daLuu = ref<Record<ConsentKey, boolean>>(tuDanhSach());
const consents = ref<Record<ConsentKey, boolean>>({ ...daLuu.value });
watch(
  () => props.consentList,
  () => {
    daLuu.value = tuDanhSach();
    consents.value = { ...daLuu.value };
  },
);

const coThayDoi = computed(() => consentItems.some((c) => consents.value[c.key] !== daLuu.value[c.key]));
const mucRut = computed(() => consentItems.filter((c) => daLuu.value[c.key] && !consents.value[c.key]));
const canXacNhanRut = ref(false);
const consentStatusMsg = ref("");

/** Có mục bị rút thì hỏi xác nhận trước; chỉ bật thêm thì lưu ngay. */
function saveConsents() {
  if (mucRut.value.length) {
    canXacNhanRut.value = true;
    return;
  }
  luuThat();
}

function luuThat() {
  canXacNhanRut.value = false;
  emit("save-consents", { ...consents.value });
  daLuu.value = { ...consents.value };
  consentStatusMsg.value = "Đã lưu lựa chọn.";
  setTimeout(() => {
    consentStatusMsg.value = "";
  }, 3000);
}
</script>

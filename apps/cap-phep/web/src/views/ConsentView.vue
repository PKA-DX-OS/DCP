<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <section class="max-w-[760px]">
    <h1 class="tieu-de-trang">Dữ liệu cá nhân</h1>
    <p class="text-phu text-[16px] mt-2">Bạn quyết định phường được dùng dữ liệu của bạn vào việc gì, và có thể yêu cầu xem, sửa hoặc xóa dữ liệu bất cứ lúc nào.</p>

    <div class="the mt-5">
      <h2 class="text-[15px] font-semibold m-0 px-5 pt-4 pb-1">Đồng thuận xử lý dữ liệu</h2>
      <ul class="list-none m-0 p-0">
        <li v-for="c in consentItems" :key="c.key" class="px-5 py-3.5 border-b border-vien-nhat last:border-b-0">
          <label class="flex items-start gap-3 cursor-pointer">
            <input type="checkbox" v-model="consents[c.key]" class="mt-1 w-4 h-4 accent-[rgb(var(--c-cham))]" />
            <span>
              <span class="font-medium block">{{ c.title }}</span>
              <span class="text-phu text-[13px]">{{ c.desc }}</span>
            </span>
          </label>
        </li>
      </ul>
      <div class="px-5 py-4 border-t border-vien-nhat flex items-center justify-end gap-3">
        <span v-if="consentStatusMsg" class="text-xanh text-[13px]" role="status">{{ consentStatusMsg }}</span>
        <button type="button" id="btn-save-consents" class="btn btn-chinh" @click="saveConsents">Lưu lựa chọn</button>
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
              <td class="whitespace-nowrap text-phu">{{ ngayNgan(req.ack_due_at) }}</td>
              <td class="whitespace-nowrap">{{ ngayNgan(req.due_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { ngayNgan, tenYeuCauDuLieu } from "../utils/labels";

defineProps<{
  dsarList: any[];
}>();

const emit = defineEmits<{
  (e: "save-consents", consents: any): void;
  (e: "dsar", action: string, note?: string): void;
}>();

const dsarNote = ref("");

type ConsentKey = "identity" | "notification" | "iot_monitoring";
const consentItems: { key: ConsentKey; title: string; desc: string }[] = [
  { key: "identity", title: "Đối chiếu danh tính", desc: "Dùng họ tên và số CCCD để đối chiếu hồ sơ với thông tin thửa đất." },
  { key: "notification", title: "Nhận thông báo tiến độ", desc: "Nhận tin nhắn khi hồ sơ cần bổ sung hoặc đã được cấp phép." },
  { key: "iot_monitoring", title: "Giám sát công trường bằng cảm biến", desc: "Thu số đo tiếng ồn, bụi tại công trình để phường kiểm tra khi vượt ngưỡng." },
];

function trangThai(st: string): string {
  const map: Record<string, string> = { received: "Đã tiếp nhận", acknowledged: "Đã xác nhận", in_progress: "Đang xử lý", done: "Đã giải quyết", completed: "Đã giải quyết", rejected: "Từ chối" };
  return map[st] || st;
}

const consents = ref<Record<ConsentKey, boolean>>({
  identity: false,
  notification: false,
  iot_monitoring: false,
});

const consentStatusMsg = ref("");

function saveConsents() {
  emit("save-consents", consents.value);
  consentStatusMsg.value = "Đã lưu lựa chọn.";
  setTimeout(() => {
    consentStatusMsg.value = "";
  }, 3000);
}
</script>

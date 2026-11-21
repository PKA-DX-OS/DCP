<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { ref } from "vue";
import IconX from "./IconX.vue";
import { useModal } from "../composables/useModal";

const emit = defineEmits<{ (e: "close"): void }>();
const hop = ref<HTMLElement | null>(null);
useModal(hop, () => emit("close"));

const PHIM_TAT = [
  { phim: "Ctrl / Cmd + K", viec: "Mở tìm kiếm toàn cục" },
  { phim: "F1", viec: "Mở trợ giúp" },
  { phim: "Tab / Shift + Tab", viec: "Di chuyển giữa các nút và ô nhập" },
  { phim: "Enter / Space", viec: "Kích hoạt nút đang chọn" },
  { phim: "Esc", viec: "Đóng hộp thoại đang mở" },
];

const MAN_HINH = [
  {
    ten: "Hồ sơ của tôi",
    moTa: "Nộp hồ sơ mới, theo dõi trạng thái, bổ sung khi được yêu cầu và mở chi tiết hồ sơ.",
  },
  {
    ten: "Tự phục vụ",
    moTa: "Xem tiến độ, bổ sung, tải giấy phép PDF và tạo QR tra cứu công khai.",
  },
  {
    ten: "Bàn làm việc",
    moTa: "Hàng đợi việc, lọc theo hạn/loại việc, chọn nhiều để nhắc hoặc phân công; panel Hỗ trợ xử lý gợi ý cán bộ và soạn nháp.",
  },
  {
    ten: "Duyệt OCR",
    moTa: "So sánh tệp gốc với trường trích xuất, sửa và xác nhận hoặc từ chối.",
  },
  {
    ten: "Hiện trường",
    moTa: "Tạo phiếu kiểm tra offline, chụp ảnh, lấy GPS, ký tay và đồng bộ khi có mạng.",
  },
  {
    ten: "Bảng điều hành",
    moTa: "Chỉ số điều hành, hiệu quả vận hành, kiểm toán và quản trị địa bàn.",
  },
];
</script>

<template>
  <div class="nen-hop" @click.self="$emit('close')">
    <div
      ref="hop"
      class="hop max-w-[680px] p-5"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tieu-de-tro-giup"
      aria-describedby="mo-ta-tro-giup"
    >
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="mo m-0">DX-OS Cấp phép</p>
          <h2 id="tieu-de-tro-giup" class="m-0 text-[22px] font-semibold">Trợ giúp &amp; phím tắt</h2>
          <p id="mo-ta-tro-giup" class="m-0 mt-1 text-[13px] text-phu">
            Hướng dẫn ngắn để dùng bàn phím và tìm đúng màn hình.
          </p>
        </div>
        <button type="button" class="nut-dong" aria-label="Đóng trợ giúp" @click="$emit('close')"><IconX /></button>
      </div>

      <section class="mt-4" aria-labelledby="tro-giup-phim-tat">
        <h3 id="tro-giup-phim-tat" class="m-0 text-[14px] font-semibold">Phím tắt</h3>
        <dl class="mt-2 grid gap-x-4 gap-y-2 text-[13px] sm:grid-cols-[180px_1fr]">
          <template v-for="p in PHIM_TAT" :key="p.phim">
            <dt class="font-medium text-chu"><kbd class="rounded-[8px] border border-vien-nhat px-2 py-0.5 text-[12px]">{{ p.phim }}</kbd></dt>
            <dd class="m-0 text-phu">{{ p.viec }}</dd>
          </template>
        </dl>
      </section>

      <section class="mt-5 border-t border-vien-nhat pt-4" aria-labelledby="tro-giup-man-hinh">
        <h3 id="tro-giup-man-hinh" class="m-0 text-[14px] font-semibold">Màn hình theo vai</h3>
        <div class="mt-2 grid gap-2 sm:grid-cols-2">
          <article v-for="m in MAN_HINH" :key="m.ten" class="rounded-[14px] border border-vien-nhat bg-mat-2 p-3">
            <h4 class="m-0 text-[13px] font-semibold">{{ m.ten }}</h4>
            <p class="m-0 mt-1 text-[12.5px] text-phu">{{ m.moTa }}</p>
          </article>
        </div>
      </section>

      <section class="mt-5 border-t border-vien-nhat pt-4" aria-labelledby="tro-giup-lien-he">
        <h3 id="tro-giup-lien-he" class="m-0 text-[14px] font-semibold">Cần hỗ trợ thêm?</h3>
        <p class="m-0 mt-1 text-[13px] text-phu">
          Liên hệ Bộ phận Một cửa nơi tiếp nhận hồ sơ. Khi báo lỗi, gửi kèm mã hồ sơ và thời điểm xảy ra.
        </p>
        <p class="goi-y mt-2">
          Giao diện hỗ trợ giảm chuyển động theo cài đặt hệ điều hành; mọi hộp thoại đều đóng được bằng Esc.
        </p>
      </section>

      <div class="mt-4 flex justify-end">
        <button type="button" class="btn btn-chinh" @click="$emit('close')">Đã hiểu</button>
      </div>
    </div>
  </div>
</template>

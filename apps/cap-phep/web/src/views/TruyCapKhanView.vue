<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { getValidToken } from "../auth";
import { approveBreakGlass, fetchPendingBreakGlass } from "../api/break_glass";
import { notify } from "../composables/useToast";
import { ngayGio } from "../utils/labels";

interface YeuCau {
  id: string;
  requester_sub: string;
  requester_name?: string | null;
  object_id: string;
  ma_ho_so?: string | null;
  reason: string;
  created_at: string;
}

const ds = ref<YeuCau[]>([]);
const dangTai = ref(false);
const dangXuLy = ref<string | null>(null);

async function tai(): Promise<void> {
  dangTai.value = true;
  try {
    const t = await getValidToken();
    ds.value = t ? ((await fetchPendingBreakGlass(t)) as YeuCau[]) : [];
  } finally {
    dangTai.value = false;
  }
}

async function xuLy(y: YeuCau, dongY: boolean): Promise<void> {
  dangXuLy.value = y.id;
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    await approveBreakGlass(t, y.object_id, y.requester_sub, dongY);
    notify(dongY ? "Đã duyệt truy cập khẩn." : "Đã từ chối yêu cầu truy cập khẩn.", "ok");
    await tai();
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không xử lý được yêu cầu", "loi");
  } finally {
    dangXuLy.value = null;
  }
}

onMounted(tai);
defineExpose({ tai });
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-end gap-4">
      <div class="min-w-0">
        <h1 class="tieu-de-trang">Truy cập khẩn chờ duyệt</h1>
        <p class="text-phu mt-1">Cán bộ chưa được giao hồ sơ xin mở trong thời gian ngắn. Người xin không tự duyệt được.</p>
      </div>
      <div class="flex-1"></div>
      <button class="btn" @click="tai()">Làm mới</button>
    </div>

    <p v-if="dangTai" class="text-phu" role="status">Đang tải yêu cầu...</p>
    <p v-else-if="!ds.length" id="empty-break-glass" class="the p-4 text-phu">Không có yêu cầu nào chờ duyệt.</p>

    <ul v-else id="list-pending-break-glass" class="space-y-3">
      <li v-for="y in ds" :key="y.id" class="the flex flex-wrap items-center gap-3 p-4">
        <div class="min-w-0 flex-1">
          <div class="font-semibold">
            {{ y.requester_name || y.requester_sub }} xin mở hồ sơ <span class="ma">{{ y.ma_ho_so || y.object_id }}</span>
          </div>
          <div class="goi-y">Lý do: {{ y.reason }} · Gửi lúc {{ ngayGio(y.created_at) }}</div>
        </div>
        <button class="btn btn-nguy" :disabled="dangXuLy === y.id" @click="xuLy(y, false)">Từ chối</button>
        <button class="btn-chinh" :disabled="dangXuLy === y.id" @click="xuLy(y, true)">Duyệt</button>
      </li>
    </ul>
  </section>
</template>

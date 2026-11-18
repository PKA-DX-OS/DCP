<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { getUser, getValidToken, readRoles } from "../auth";
import { fetchTasks } from "../api/flow";
import { useDossierActions, type NguoiDung } from "../composables/useDossierActions";
import type { FlowTask } from "../types";

type BoLoc = "tat-ca" | "qua-han" | "sap-han";
const nguoi = ref<NguoiDung | null>(null);
const tasks = ref<FlowTask[]>([]);
const dangTai = ref(false);
const loi = ref("");
const boLoc = ref<BoLoc>("tat-ca");
const dangLam = ref<string | null>(null);

const actions = useDossierActions(getValidToken, () => nguoi.value);
const emit = defineEmits<{ (e: "mo-ho-so", idHoacMa: string, ma: string): void }>();

/** Hồ sơ gắn với việc: lấy từ biến quy trình ho_so_id, không có thì dùng mã hồ sơ (businessKey). */
function hoSoCuaViec(t: FlowTask): { id: string; ma: string } | null {
  const bien = (ten: string) => ((t.variables as any[] | undefined) || []).find((v: any) => v.name === ten)?.value as string | undefined;
  const ma = bien("ma_ho_so") || t.businessKey || "";
  const id = bien("ho_so_id") || ma;
  return id ? { id, ma } : null;
}

function hanCuaViec(t: FlowTask): number | null {
  return t.dueDate ? new Date(t.dueDate).getTime() : null;
}

const danhSachLoc = computed(() => {
  const now = Date.now();
  const ngay = 24 * 3600 * 1000;
  return tasks.value.filter((t) => {
    const han = hanCuaViec(t);
    if (boLoc.value === "qua-han") return han !== null && han < now;
    if (boLoc.value === "sap-han") return han !== null && han >= now && han - now <= ngay;
    return true;
  });
});

async function taiViec(): Promise<void> {
  dangTai.value = true;
  loi.value = "";
  try {
    const t = await getValidToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    tasks.value = await fetchTasks(t);
  } catch (e) {
    loi.value = e instanceof Error ? e.message : "Không tải được việc";
  } finally {
    dangTai.value = false;
  }
}

async function hoanThanh(t: FlowTask): Promise<void> {
  dangLam.value = t.id;
  const ok = await actions.hoanThanhViec(t);
  dangLam.value = null;
  if (ok) await taiViec();
}

function dinhDangHan(t: FlowTask): string {
  const han = hanCuaViec(t);
  return han ? new Date(han).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "Không có hạn";
}

onMounted(async () => {
  const user = await getUser();
  const roles = readRoles(user?.access_token);
  nguoi.value = { sub: user?.profile?.sub as string | undefined, roles };
  await taiViec();
});

defineExpose({ taiViec });
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-end gap-4">
      <div class="min-w-0">
        <h2 class="tieu-de-trang">Bàn làm việc</h2>
        <p class="text-phu mt-1">Chỉ hiện việc được giao cho bạn.</p>
      </div>
      <div class="flex-1"></div>
      <label class="nhan" for="loc-viec">Lọc theo hạn</label>
      <select id="loc-viec" v-model="boLoc" class="o">
        <option value="tat-ca">Tất cả</option>
        <option value="qua-han">Quá hạn</option>
        <option value="sap-han">Sắp đến hạn (24 giờ)</option>
      </select>
      <button class="btn" @click="taiViec()">Làm mới</button>
    </div>

    <p v-if="dangTai" class="text-phu" role="status">Đang tải việc...</p>

    <div v-else-if="loi" class="the p-4">
      <p class="canh-bao">{{ loi }}</p>
      <button class="btn mt-2" @click="taiViec()">Thử lại</button>
    </div>

    <p v-else-if="!danhSachLoc.length" class="the p-4 text-phu">Không có việc nào cần xử lý.</p>

    <ul v-else class="space-y-3">
      <li v-for="t in danhSachLoc" :key="t.id" class="the flex flex-wrap items-center gap-3 p-4">
        <div class="min-w-0 flex-1">
          <div class="font-semibold">{{ t.name || t.taskDefinitionKey || "Nhiệm vụ" }}</div>
          <div class="goi-y">Mã hồ sơ: {{ hoSoCuaViec(t)?.ma || "—" }} · Hạn: {{ dinhDangHan(t) }}</div>
        </div>
        <button
          v-if="hoSoCuaViec(t)"
          class="btn"
          @click="emit('mo-ho-so', hoSoCuaViec(t)!.id, hoSoCuaViec(t)!.ma)"
        >
          Xem hồ sơ
        </button>
        <button
          v-if="actions.laNguoiDuocGiao(t)"
          class="btn-chinh"
          :disabled="dangLam === t.id"
          @click="hoanThanh(t)"
        >
          {{ dangLam === t.id ? "Đang xử lý..." : "Hoàn thành" }}
        </button>
      </li>
    </ul>
  </section>
</template>
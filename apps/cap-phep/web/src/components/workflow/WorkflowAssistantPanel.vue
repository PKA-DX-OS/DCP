<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { assignTask, fetchOfficers, fetchWorkload, remindTask, type WorkloadItem } from "../../api/flow";
import { notify } from "../../composables/useToast";
import {
  NHAN_NHAP,
  NHAN_VAI,
  loaiNhapMacDinh,
  taoNhapThongBao,
  vaiGoiY,
  xepHangCanBo,
  type CanBoGoiY,
  type LoaiNhap,
} from "../../utils/workflow-assist";
import { ngayGio } from "../../utils/labels";

const props = defineProps<{
  task: any;
  dossier: any;
  token: string;
  laQuanLy: boolean;
}>();

const emit = defineEmits<{
  (e: "assigned"): void;
  (e: "reminded"): void;
}>();

const DS_NHAP = Object.entries(NHAN_NHAP) as [LoaiNhap, string][];

const vai = computed(() => vaiGoiY(props.task?.taskDefinitionKey));
const canBo = ref<any[]>([]);
const workload = ref<WorkloadItem[]>([]);
const dangTai = ref(false);
const loi = ref("");
const chon = ref("");
const lyDo = ref("Gợi ý theo tải việc hiện tại");
const dangGiao = ref(false);
const dangNhac = ref(false);
const loaiNhap = ref<LoaiNhap>(loaiNhapMacDinh(props.dossier));
const nhap = ref(taoNhapThongBao(loaiNhap.value, props.dossier, props.task));
const daChep = ref(false);

const goiY = computed<CanBoGoiY[]>(() => xepHangCanBo(canBo.value, workload.value).slice(0, 3));

const slaText = computed(() => {
  const value = props.task?.dueDate;
  if (!value) return "Không có hạn xử lý";
  const t = new Date(value).getTime();
  if (!Number.isFinite(t)) return "Hạn không hợp lệ";
  const conLai = t - Date.now();
  if (conLai < 0) return `Quá hạn ${Math.ceil(-conLai / 86_400_000)} ngày`;
  const gio = Math.ceil(conLai / 3_600_000);
  if (gio <= 48) return `Còn ${gio} giờ`;
  return `Còn ${Math.ceil(gio / 24)} ngày`;
});

const slaClass = computed(() => {
  const value = props.task?.dueDate;
  if (!value) return "text-phu";
  const conLai = new Date(value).getTime() - Date.now();
  return conLai < 0 ? "text-son font-semibold" : conLai <= 48 * 3_600_000 ? "text-vang font-semibold" : "text-phu";
});

function tenCanBo(c: CanBoGoiY): string {
  return c.ho_ten || c.username || c.sub;
}

async function taiGoiY(): Promise<void> {
  if (!props.laQuanLy || !props.token) return;
  dangTai.value = true;
  loi.value = "";
  try {
    const [dsCanBo, dsWorkload] = await Promise.all([
      fetchOfficers(props.token, vai.value),
      fetchWorkload(props.token).catch(() => []),
    ]);
    canBo.value = Array.isArray(dsCanBo) ? dsCanBo : [];
    workload.value = Array.isArray(dsWorkload) ? dsWorkload : [];
    if (!canBo.value.length) loi.value = `Chưa có cán bộ nhóm ${NHAN_VAI[vai.value]} trong địa bàn.`;
  } catch (e) {
    canBo.value = [];
    workload.value = [];
    loi.value = e instanceof Error ? e.message : "Không tải được gợi ý phân công";
  } finally {
    dangTai.value = false;
  }
}

function taoLaiNhap(): void {
  nhap.value = taoNhapThongBao(loaiNhap.value, props.dossier, props.task);
}

async function chepNhap(): Promise<void> {
  try {
    await navigator.clipboard.writeText(nhap.value);
    daChep.value = true;
    setTimeout(() => (daChep.value = false), 2000);
  } catch {
    notify("Trình duyệt không cho chép tự động", "loi");
  }
}

async function giaoViec(): Promise<void> {
  if (!chon.value) {
    notify("Chọn cán bộ trước khi giao việc", "canh_bao");
    return;
  }
  dangGiao.value = true;
  try {
    await assignTask(props.token, props.task.id, chon.value, lyDo.value.trim() || "Gợi ý theo tải việc");
    notify("Đã giao việc cho cán bộ được chọn", "ok");
    chon.value = "";
    emit("assigned");
    await taiGoiY();
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không giao được việc", "loi");
  } finally {
    dangGiao.value = false;
  }
}

async function nhacViec(): Promise<void> {
  dangNhac.value = true;
  try {
    await remindTask(props.token, props.task.id, nhap.value);
    notify("Đã gửi nhắc việc nội bộ", "ok");
    emit("reminded");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không gửi được nhắc việc", "loi");
  } finally {
    dangNhac.value = false;
  }
}

watch(
  () => [props.task?.id, props.dossier?.id],
  () => {
    chon.value = "";
    loaiNhap.value = loaiNhapMacDinh(props.dossier);
    nhap.value = taoNhapThongBao(loaiNhap.value, props.dossier, props.task);
  },
);

watch(vai, () => {
  chon.value = "";
  void taiGoiY();
});

onMounted(() => {
  if (props.laQuanLy) void taiGoiY();
});
</script>

<template>
  <section class="mt-4 rounded-[16px] border border-vien-nhat p-3" aria-labelledby="tieu-de-ho-tro-xu-ly">
    <h2 id="tieu-de-ho-tro-xu-ly" class="m-0 text-[14px] font-semibold">Hỗ trợ xử lý</h2>

    <div class="mt-2 rounded-[12px] bg-mat-2 p-2 text-[12.5px]">
      <p class="m-0">
        Việc: <b>{{ task.name || task.taskDefinitionKey || "Nhiệm vụ" }}</b>
      </p>
      <p class="m-0 mt-1">
        Hạn xử lý: <span :class="slaClass">{{ slaText }}</span>
        <template v-if="task.dueDate"> · {{ ngayGio(task.dueDate) }}</template>
      </p>
    </div>

    <template v-if="laQuanLy">
      <h3 class="mt-4 text-[13px] font-semibold">Gợi ý phân công · {{ NHAN_VAI[vai] }}</h3>
      <p v-if="dangTai" class="m-0 mt-1 text-[12.5px] text-phu" role="status">Đang tải tải việc cán bộ…</p>
      <div v-else-if="loi" class="mt-1 text-[12.5px]">
        <p class="m-0 text-vang">{{ loi }}</p>
        <button type="button" class="btn btn-sm mt-2" @click="taiGoiY">Thử lại</button>
      </div>
      <p v-else-if="!goiY.length" class="m-0 mt-1 text-[12.5px] text-phu">Chưa có cán bộ phù hợp để gợi ý.</p>
      <ul v-else class="m-0 mt-2 list-none space-y-1.5 p-0">
        <li v-for="(c, i) in goiY" :key="c.sub" class="flex flex-wrap items-center gap-2 rounded-[12px] bg-mat-2 p-2 text-[12.5px]">
          <span class="min-w-0 flex-1">
            <b class="block">{{ tenCanBo(c) }}</b>
            <span class="text-phu">{{ c.dangXuLy }} việc đang xử lý · {{ c.tongHoSo }} hồ sơ được giao</span>
          </span>
          <span v-if="i === 0" class="tt tt-xanh">Ít việc nhất</span>
          <button type="button" class="btn btn-sm" @click="chon = c.sub">
            {{ chon === c.sub ? "Đang chọn" : "Chọn" }}
          </button>
        </li>
      </ul>

      <div v-if="chon" class="mt-2 rounded-[12px] border border-vien-nhat p-2">
        <label class="block">
          <span class="nhan">Lý do giao việc</span>
          <input v-model="lyDo" class="o w-full" maxlength="300" aria-label="Lý do giao việc" />
        </label>
        <div class="mt-2 flex flex-wrap gap-2">
          <button type="button" class="btn btn-sm btn-chinh" :disabled="dangGiao" @click="giaoViec">
            {{ dangGiao ? "Đang giao…" : "Xác nhận giao việc" }}
          </button>
          <button type="button" class="btn btn-sm" :disabled="dangGiao" @click="chon = ''">Hủy</button>
        </div>
      </div>
    </template>

    <div class="mt-4 border-t border-vien-nhat pt-3">
      <h3 class="m-0 text-[13px] font-semibold">Nháp thông báo</h3>
      <label class="mt-2 block">
        <span class="nhan">Mẫu văn bản</span>
        <select v-model="loaiNhap" class="o w-full" aria-label="Mẫu nháp thông báo" @change="taoLaiNhap">
          <option v-for="[key, label] in DS_NHAP" :key="key" :value="key">{{ label }}</option>
        </select>
      </label>
      <textarea
        v-model="nhap"
        class="o mt-2 min-h-[150px] w-full resize-y text-[12.5px]"
        maxlength="4000"
        aria-label="Nội dung nháp thông báo"
      ></textarea>
      <div class="mt-2 flex flex-wrap gap-2">
        <button type="button" class="btn btn-sm" @click="taoLaiNhap">Tạo lại</button>
        <button type="button" class="btn btn-sm" @click="chepNhap">{{ daChep ? "Đã chép" : "Chép nội dung" }}</button>
        <button
          v-if="laQuanLy"
          type="button"
          class="btn btn-sm text-vang"
          :disabled="dangNhac"
          @click="nhacViec"
        >
          {{ dangNhac ? "Đang gửi…" : "Gửi nhắc việc nội bộ" }}
        </button>
      </div>
      <p class="goi-y mt-2">
        Nháp chỉ để hỗ trợ soạn thảo. Cán bộ phải kiểm tra và gửi cho công dân qua kênh chính thức.
      </p>
    </div>
  </section>
</template>

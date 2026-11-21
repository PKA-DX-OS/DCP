<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { assignTask, completeTask, fetchOfficers, fetchTasks } from "../api/flow";
import { openHoSo } from "../api/dossiers";
import { notify } from "../composables/useToast";

const props = defineProps<{
  dossier: any;
  token: string;
  compact?: boolean;
  id?: string;
}>();
const emit = defineEmits<{ (e: "done", hoSo: any): void }>();

interface HanhDong {
  key: string;
  nhan: string;
  variables: Record<string, any>;
  canLyDo?: boolean;
  varLyDo?: string;
  tone?: "chinh" | "do" | "vang";
  canChonCanBo?: boolean;
}

const rootId = computed(() => props.id || "block-dossier-actions");
const titleId = computed(() => (props.id ? `${props.id}-title` : "tieu-de-hanh-dong"));

const tasks = ref<any[]>([]);
const dangTai = ref(false);
const dangGui = ref(false);
const hanhDongChon = ref<HanhDong | null>(null);
const lyDo = ref("");
const nguoiThamDinh = ref("");
const canBo = ref<any[]>([]);

const sub = computed(() => {
  try {
    const part = props.token.split(".")[1] || "";
    const json = JSON.parse(decodeURIComponent(escape(atob(part.replace(/-/g, "+").replace(/_/g, "/")))));
    return json?.sub || "";
  } catch {
    return "";
  }
});

const roles = computed<string[]>(() => {
  try {
    const part = props.token.split(".")[1] || "";
    const json = JSON.parse(decodeURIComponent(escape(atob(part.replace(/-/g, "+").replace(/_/g, "/")))));
    const ds = json?.realm_access?.roles ?? json?.roles ?? [];
    return Array.isArray(ds) ? ds.map(String) : [];
  } catch {
    return [];
  }
});
const laQuanLy = computed(() => roles.value.some((r) => ["app:cap-phep:lanh-dao", "app:cap-phep:mot-cua", "dx:tenant-admin", "dx:platform-admin"].includes(r)));

function bien(task: any, ten: string): any {
  return ((task?.variables as any[] | undefined) || []).find((v: any) => v.name === ten)?.value;
}

const viecCuaHoSo = computed(() =>
  tasks.value.filter((t) => {
    const id = bien(t, "ho_so_id");
    const ma = bien(t, "ma_ho_so") || t.businessKey;
    return id === props.dossier.id || ma === props.dossier.ma_ho_so;
  }),
);

const viecHienTai = computed(() => viecCuaHoSo.value[0] || null);

function coTheXuLy(t: any): boolean {
  return !t?.assignee || t.assignee === sub.value;
}

function hanhDongCoBan(t: any): HanhDong[] {
  const key = t?.taskDefinitionKey || "";
  if (key === "taskKiemTraHopLe") {
    return [
      { key: "nhan", nhan: "Tiếp nhận hợp lệ", variables: { hoSoHopLe: true }, tone: "chinh" },
      { key: "bo-sung", nhan: "Yêu cầu bổ sung", variables: { hoSoHopLe: false }, canLyDo: true, varLyDo: "lyDoBoSung", tone: "vang" },
    ];
  }
  if (key === "taskPhanCong") {
    return [{ key: "phan-cong", nhan: "Phân công thẩm định", variables: {}, canChonCanBo: true, tone: "chinh" }];
  }
  if (key.startsWith("taskThamDinh")) {
    return [
      { key: "dat", nhan: "Đạt thẩm định", variables: { ketQuaThamDinh: "dat" }, tone: "chinh" },
      { key: "khong-dat", nhan: "Không đạt — chuyển lãnh đạo", variables: { ketQuaThamDinh: "khong_dat" }, canLyDo: true, varLyDo: "noiDungThamDinh", tone: "do" },
    ];
  }
  if (key === "taskDuyetCapPhep" || key === "taskPheDuyet") {
    return [
      { key: "duyet", nhan: "Phê duyệt và ký", variables: { pheDuyet: true, dongYCapPhep: true }, tone: "chinh" },
      { key: "tu-choi", nhan: "Từ chối", variables: { pheDuyet: false, dongYCapPhep: false }, canLyDo: true, varLyDo: "yKienPheDuyet", tone: "do" },
    ];
  }
  if (key === "taskKiemTraQuyHoach") {
    return [
      { key: "q-dat", nhan: "Quy hoạch đạt", variables: { quy_hoach_pass: true }, tone: "chinh" },
      { key: "q-khong-dat", nhan: "Quy hoạch không đạt", variables: { quy_hoach_pass: false }, canLyDo: true, varLyDo: "quy_hoach_fail_rules", tone: "do" },
    ];
  }
  if (key.startsWith("taskNghiemThu") || key === "taskHoanCong") {
    // Cổng rẽ nhánh sau nghiệm thu móng đọc mong_dat (mặc định true); thiếu biến này thì "Không đạt" vẫn đi nhánh đạt
    const laMong = key === "taskNghiemThuMong";
    return [
      { key: "dat", nhan: "Đạt", variables: { ket_qua_nghiem_thu: "dat", ...(laMong ? { mong_dat: true } : {}) }, tone: "chinh" },
      {
        key: "khong-dat",
        nhan: "Không đạt",
        variables: { ket_qua_nghiem_thu: "khong_dat", ...(laMong ? { mong_dat: false } : {}) },
        canLyDo: true,
        varLyDo: "ghi_chu",
        tone: "do",
      },
    ];
  }
  if (key === "taskKhacPhucMong") {
    return [{ key: "khac-phuc", nhan: "Đã khắc phục", variables: {}, canLyDo: true, varLyDo: "noi_dung_khac_phuc", tone: "chinh" }];
  }
  return [];
}

function hanhDongCua(t: any): HanhDong[] {
  const ds = hanhDongCoBan(t);
  const key = t?.taskDefinitionKey || "";
  if (laQuanLy.value && t?.assignee && key !== "taskPhanCong") {
    ds.push({ key: "reassign", nhan: "Phân công lại", variables: {}, canChonCanBo: true, canLyDo: true, varLyDo: "reason", tone: "vang" });
  }
  return ds;
}

function moHanhDong(h: HanhDong) {
  hanhDongChon.value = h;
  lyDo.value = "";
  nguoiThamDinh.value = "";
  if (h.canChonCanBo && !canBo.value.length) {
    fetchOfficers(props.token, "tham-dinh").then((ds) => (canBo.value = ds)).catch(() => (canBo.value = []));
  }
}

async function gui() {
  const h = hanhDongChon.value;
  const t = viecHienTai.value;
  if (!h || !t) return;
  if (h.canLyDo && !lyDo.value.trim()) {
    notify("Nhập lý do trước khi gửi", "canh_bao");
    return;
  }
  if (h.canChonCanBo && !nguoiThamDinh.value) {
    notify("Chọn cán bộ thẩm định", "canh_bao");
    return;
  }
  if (h.key === "reassign") {
    dangGui.value = true;
    try {
      await assignTask(props.token, t.id, nguoiThamDinh.value, lyDo.value.trim());
      notify("Đã phân công lại việc", "ok");
      hanhDongChon.value = null;
      await tai();
      window.dispatchEvent(new CustomEvent("dxos:tasks-changed"));
    } catch (e) {
      notify(e instanceof Error ? e.message : "Không phân công lại được", "loi");
    } finally {
      dangGui.value = false;
    }
    return;
  }
  const variables: Record<string, any> = { ...h.variables };
  if (h.canLyDo && h.varLyDo) variables[h.varLyDo] = lyDo.value.trim();
  if (h.canChonCanBo) {
    variables.nguoiThamDinh = nguoiThamDinh.value;
    variables.lanhDaoPhanCong = sub.value;
  }
  dangGui.value = true;
  try {
    await completeTask(props.token, t.id, variables);
    notify("Đã cập nhật hồ sơ", "ok");
    hanhDongChon.value = null;
    const hs = await openHoSo(props.token, props.dossier.id);
    emit("done", hs);
    await tai();
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không cập nhật được hồ sơ", "loi");
  } finally {
    dangGui.value = false;
  }
}

async function tai() {
  dangTai.value = true;
  try {
    tasks.value = await fetchTasks(props.token);
  } catch {
    tasks.value = [];
  } finally {
    dangTai.value = false;
  }
}

function han(t: any): string {
  return t?.dueDate ? new Date(t.dueDate).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "Không có hạn";
}

function taiKhiThayDoi() {
  void tai();
}

onMounted(() => {
  window.addEventListener("dxos:tasks-changed", taiKhiThayDoi);
  void tai();
});
onUnmounted(() => window.removeEventListener("dxos:tasks-changed", taiKhiThayDoi));
</script>

<template>
  <section v-if="viecHienTai && hanhDongCua(viecHienTai).length" :id="rootId" class="mt-4 rounded-[18px] border border-vien-nhat bg-mat-2 p-3" :aria-labelledby="titleId">
    <div :class="compact ? 'flex flex-col items-stretch gap-2' : 'flex flex-wrap items-center gap-2'">
      <div class="min-w-0 flex-1">
        <h3 :id="titleId" class="text-[13px] font-semibold m-0">Việc đang chờ bạn: {{ viecHienTai.name || viecHienTai.taskDefinitionKey }}</h3>
        <p class="goi-y m-0">Hạn: {{ han(viecHienTai) }}</p>
      </div>
      <template v-if="coTheXuLy(viecHienTai)">
        <button
          v-for="h in hanhDongCua(viecHienTai)"
          :key="h.key"
          class="btn btn-sm"
          :class="[h.tone === 'chinh' ? 'btn-chinh' : '', compact ? 'w-full justify-center' : '']"
          :disabled="dangGui"
          @click="moHanhDong(h)"
        >{{ h.nhan }}</button>
      </template>
      <span v-else class="goi-y">Việc đã được giao cho cán bộ khác.</span>
    </div>

    <div v-if="hanhDongChon" class="mt-3 border-t border-vien-nhat pt-3">
      <p class="font-medium text-[13px] mt-0 mb-2">{{ hanhDongChon.nhan }}</p>
      <label v-if="hanhDongChon.canChonCanBo" class="block mb-2">
        <span class="nhan">Cán bộ thẩm định</span>
        <select v-model="nguoiThamDinh" class="o w-full">
          <option value="">Chọn cán bộ</option>
          <option v-for="c in canBo" :key="c.sub" :value="c.sub">{{ c.ho_ten }} ({{ c.username }})</option>
        </select>
      </label>
      <label v-if="hanhDongChon.canLyDo" class="block mb-2">
        <span class="nhan">Lý do / nội dung (bắt buộc)</span>
        <textarea v-model="lyDo" class="o w-full" rows="3"></textarea>
      </label>
      <div class="flex gap-2">
        <button class="btn btn-chinh btn-sm" :disabled="dangGui" @click="gui">{{ dangGui ? "Đang gửi…" : "Xác nhận" }}</button>
        <button class="btn btn-sm" :disabled="dangGui" @click="hanhDongChon = null">Hủy</button>
      </div>
    </div>
  </section>
</template>

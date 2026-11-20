<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { createMilestone, fetchAcceptance, fetchAcceptanceHistory, submitAcceptanceRecord, submitAsBuilt } from "../../api/acceptance";
import { completeTask, fetchTasks, startWorkflow } from "../../api/flow";
import { uploadFile } from "../../api/files";
import { notify } from "../../composables/useToast";
import { Button, Skeleton } from "../../design-system";

const props = defineProps<{
  dossier: any;
  token: string;
}>();

const MILESTONES = [
  { code: "mong", ten: "Nghiệm thu móng" },
  { code: "ket_cau", ten: "Nghiệm thu kết cấu" },
  { code: "hoan_thien", ten: "Nghiệm thu hoàn thiện" },
  { code: "hoan_cong", ten: "Hoàn công" },
];

const duLieu = ref<any>(null);
const lichSu = ref<any[]>([]);
const loading = ref(false);
const saving = ref(false);
const dangTaoQuyTrinh = ref(false);
const error = ref("");
const selectedMoc = ref<any>(null);
const fileRef = ref<HTMLInputElement | null>(null);
const fileHoanCong = ref<File | null>(null);
const tasks = ref<any[]>([]);

const TASK_BY_MOC: Record<string, string> = {
  mong: "taskNghiemThuMong",
  ket_cau: "taskNghiemThuKetCau",
  hoan_thien: "taskNghiemThuHoanThien",
  hoan_cong: "taskHoanCong",
};

const form = reactive({
  loai_moc: "mong",
  ket_qua: "dat",
  ngay_nghiem_thu: new Date().toISOString().slice(0, 10),
  ghi_chu: "",
});

const record = reactive({
  so_bien_ban: "",
  ket_luan: "",
  ket_qua: "dat",
});

function mocMoiNhat(code: string): any {
  const ds = (duLieu.value?.milestones || []).filter((m: any) => m.loai_moc === code);
  return ds.length ? ds[ds.length - 1] : null;
}

const tienDo = computed(() => {
  const done = MILESTONES.filter((m) => mocMoiNhat(m.code)?.ket_qua === "dat").length;
  return { done, total: MILESTONES.length, pct: Math.round((done * 100) / MILESTONES.length) };
});

const viecNghiemThu = computed(() => tasks.value.find((t) => {
  const key = t.taskDefinitionKey || "";
  return key.startsWith("taskNghiemThu") || key === "taskHoanCong" || key === "taskKhacPhucMong";
}) || null);

function mocClass(code: string): string {
  const m = mocMoiNhat(code);
  if (!m) return "tt tt-xam";
  if (m.ket_qua === "dat") return "tt tt-xanh";
  if (m.ket_qua === "khong_dat") return "tt tt-do";
  return "tt tt-vang";
}

function mocNhan(code: string): string {
  const m = mocMoiNhat(code);
  if (!m) return "Chưa nghiệm thu";
  if (m.ket_qua === "dat") return "Đạt";
  if (m.ket_qua === "khong_dat") return "Không đạt";
  return "Chờ nghiệm thu";
}

async function tai() {
  loading.value = true;
  error.value = "";
  try {
    duLieu.value = await fetchAcceptance(props.token, props.dossier.id);
    lichSu.value = await fetchAcceptanceHistory(props.token, props.dossier.id).catch(() => []);
    const tiep = duLieu.value.moc_tiep_theo || "mong";
    form.loai_moc = tiep;
    selectedMoc.value = mocMoiNhat(tiep) || null;
    await taiViec();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được nghiệm thu";
  } finally {
    loading.value = false;
  }
}

function phatSuKienViec() {
  window.dispatchEvent(new CustomEvent("dxos:tasks-changed"));
}

async function taiViec() {
  try {
    const ds = await fetchTasks(props.token);
    tasks.value = (ds || []).filter((t) => {
      const id = (t.variables || []).find((v: any) => v.name === "ho_so_id")?.value;
      const ma = (t.variables || []).find((v: any) => v.name === "ma_ho_so")?.value || t.businessKey;
      return id === props.dossier?.id || ma === props.dossier?.ma_ho_so;
    });
  } catch {
    tasks.value = [];
  }
}

async function batDauNghiemThu() {
  dangTaoQuyTrinh.value = true;
  try {
    await startWorkflow(props.token, "nghiem-thu", props.dossier.ma_ho_so, {
      ho_so_id: props.dossier.id,
      ma_ho_so: props.dossier.ma_ho_so,
      dia_chi_cong_trinh: props.dossier.dia_chi_cong_trinh,
      trang_thai_ho_so: props.dossier.trang_thai,
    });
    await new Promise((r) => setTimeout(r, 300));
    await taiViec();
    phatSuKienViec();
    notify("Đã tạo quy trình nghiệm thu trong Bàn làm việc", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tạo được quy trình nghiệm thu", "loi");
  } finally {
    dangTaoQuyTrinh.value = false;
  }
}

async function hoanThanhViecMoc(loaiMoc: string, ketQua: string, ghiChu: string) {
  const taskDef = TASK_BY_MOC[loaiMoc];
  if (!taskDef) return;
  const viec = tasks.value.find((t) => t.taskDefinitionKey === taskDef);
  if (!viec) return;
  try {
    const vars: Record<string, any> = { ket_qua_nghiem_thu: ketQua, ghi_chu: ghiChu || null };
    if (loaiMoc === "mong") vars.mong_dat = ketQua === "dat";
    await completeTask(props.token, viec.id, vars);
    await taiViec();
    phatSuKienViec();
    notify(`Đã cập nhật việc ${viec.name || taskDef}`, "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Đã lưu mốc nhưng chưa hoàn thành được việc nghiệm thu", "canh_bao");
  }
}

async function taoMoc() {
  saving.value = true;
  const loaiMoc = form.loai_moc;
  const ketQua = form.ket_qua;
  const ghiChu = form.ghi_chu;
  try {
    await createMilestone(props.token, props.dossier.id, { ...form });
    notify(`Đã ghi nhận ${MILESTONES.find((m) => m.code === loaiMoc)?.ten || loaiMoc}`, "ok");
    await tai();
    selectedMoc.value = mocMoiNhat(loaiMoc) || selectedMoc.value;
    await hoanThanhViecMoc(loaiMoc, ketQua, ghiChu);
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tạo được mốc nghiệm thu", "loi");
  } finally {
    saving.value = false;
  }
}

async function nopBienBan() {
  if (!selectedMoc.value) {
    notify("Chọn mốc nghiệm thu trước", "canh_bao");
    return;
  }
  if (!record.so_bien_ban.trim() || !record.ket_luan.trim()) {
    notify("Nhập số biên bản và kết luận", "canh_bao");
    return;
  }
  saving.value = true;
  try {
    await submitAcceptanceRecord(props.token, selectedMoc.value.id, { ...record });
    notify("Đã nộp biên bản nghiệm thu", "ok");
    record.so_bien_ban = "";
    record.ket_luan = "";
    await tai();
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không nộp được biên bản", "loi");
  } finally {
    saving.value = false;
  }
}

async function nopBanVe() {
  if (!fileHoanCong.value) {
    notify("Chọn tệp bản vẽ hoàn công", "canh_bao");
    return;
  }
  saving.value = true;
  try {
    const up = await uploadFile(props.token, fileHoanCong.value, "ho_so", props.dossier.id);
    await submitAsBuilt(props.token, props.dossier.id, { file_id: up.file_id, ghi_chu: "Bản vẽ hoàn công" });
    notify("Đã nộp bản vẽ hoàn công", "ok");
    fileHoanCong.value = null;
    if (fileRef.value) fileRef.value.value = "";
    await tai();
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không nộp được bản vẽ hoàn công", "loi");
  } finally {
    saving.value = false;
  }
}

onMounted(tai);
</script>

<template>
  <section id="block-dossier-acceptance" class="mt-5" aria-labelledby="tieu-de-nghiem-thu">
    <div class="flex flex-wrap items-baseline justify-between gap-3 mb-2">
      <h4 id="tieu-de-nghiem-thu" class="text-[14px] font-semibold m-0">Nghiệm thu và hoàn công</h4>
      <span class="goi-y">Căn cứ NĐ 207/2026/NĐ-CP</span>
    </div>

    <div v-if="loading" class="the p-3" role="status" aria-busy="true">
      <p class="sr-only">Đang tải nghiệm thu…</p>
      <Skeleton :lines="4" height="2rem" />
    </div>
    <div v-else-if="error" class="the p-3">
      <p class="canh-bao m-0">{{ error }}</p>
      <button class="btn btn-sm mt-2" @click="tai">Thử lại</button>
    </div>
    <template v-else>
      <div class="the p-3 mb-3">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
          <span class="font-medium">Tiến độ: {{ tienDo.done }}/{{ tienDo.total }} mốc</span>
          <span class="mo">{{ tienDo.pct }}%</span>
        </div>
        <div class="h-2 rounded overflow-hidden" style="background: var(--tien-do-nen)" role="progressbar" aria-label="Tiến độ nghiệm thu" :aria-valuenow="tienDo.pct" aria-valuemin="0" aria-valuemax="100">
          <div class="h-full bg-[#0E7C7B]" :style="{ width: tienDo.pct + '%' }"></div>
        </div>
        <ol class="list-none m-0 p-0 mt-3 grid gap-2 sm:grid-cols-4">
          <li v-for="m in MILESTONES" :key="m.code" class="rounded-md border border-vien-nhat p-2">
            <div class="text-[13px] font-medium">{{ m.ten }}</div>
            <span :class="mocClass(m.code)">{{ mocNhan(m.code) }}</span>
            <div v-if="mocMoiNhat(m.code)?.ngay_nghiem_thu" class="goi-y">{{ mocMoiNhat(m.code).ngay_nghiem_thu }}</div>
          </li>
        </ol>
      </div>

      <div class="the p-3 mb-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <span v-if="viecNghiemThu" class="text-[13px] text-phu">
            Việc <b>{{ viecNghiemThu.name || viecNghiemThu.taskDefinitionKey }}</b> đang chờ trong Bàn làm việc.
          </span>
          <span v-else class="text-[13px] text-phu">Chưa có quy trình nghiệm thu cho hồ sơ này.</span>
          <Button v-if="!viecNghiemThu" size="sm" variant="secondary" :disabled="dangTaoQuyTrinh" @click="batDauNghiemThu">
            {{ dangTaoQuyTrinh ? "Đang tạo…" : "Bắt đầu quy trình nghiệm thu" }}
          </Button>
        </div>
      </div>

      <div class="grid gap-3 md:grid-cols-2">
        <div class="the p-3">
          <h5 class="text-[13px] font-semibold mt-0 mb-2">Tạo mốc / nghiệm thu lại</h5>
          <div class="grid gap-2">
            <label class="block"><span class="nhan">Mốc</span>
              <select v-model="form.loai_moc" class="o w-full">
                <option v-for="m in MILESTONES" :key="m.code" :value="m.code">{{ m.ten }}</option>
              </select>
            </label>
            <label class="block"><span class="nhan">Kết quả</span>
              <select v-model="form.ket_qua" class="o w-full">
                <option value="dat">Đạt</option>
                <option value="khong_dat">Không đạt</option>
                <option value="cho_nghiem_thu">Chờ nghiệm thu</option>
              </select>
            </label>
            <label class="block"><span class="nhan">Ngày nghiệm thu</span><input v-model="form.ngay_nghiem_thu" type="date" class="o w-full" /></label>
            <label class="block"><span class="nhan">Ghi chú</span><textarea v-model="form.ghi_chu" class="o w-full" rows="2"></textarea></label>
          </div>
          <Button class="mt-2" :disabled="saving" @click="taoMoc">{{ saving ? "Đang lưu…" : "Ghi nhận mốc" }}</Button>
        </div>

        <div class="the p-3">
          <h5 class="text-[13px] font-semibold mt-0 mb-2">Nộp biên bản</h5>
          <label class="block"><span class="nhan">Mốc áp dụng</span>
            <select class="o w-full" :value="selectedMoc?.id || ''" @change="selectedMoc = (duLieu?.milestones || []).find((m: any) => m.id === ($event.target as HTMLSelectElement).value) || null">
              <option value="">Chọn mốc</option>
              <option v-for="m in duLieu?.milestones || []" :key="m.id" :value="m.id">{{ m.loai_moc }} — lần {{ m.version }} ({{ m.ket_qua }})</option>
            </select>
          </label>
          <label class="block mt-2"><span class="nhan">Số biên bản</span><input v-model="record.so_bien_ban" class="o w-full" /></label>
          <label class="block mt-2"><span class="nhan">Kết luận</span><textarea v-model="record.ket_luan" class="o w-full" rows="2"></textarea></label>
          <label class="block mt-2"><span class="nhan">Kết quả mốc</span>
            <select v-model="record.ket_qua" class="o w-full">
              <option value="dat">Đạt</option>
              <option value="khong_dat">Không đạt</option>
            </select>
          </label>
          <Button variant="secondary" class="mt-2" :disabled="saving || !selectedMoc" @click="nopBienBan">Nộp biên bản</Button>
        </div>
      </div>

      <div class="the p-3 mt-3">
        <h5 id="tieu-de-hoan-cong" class="text-[13px] font-semibold mt-0 mb-2">Bản vẽ hoàn công</h5>
        <input ref="fileRef" type="file" class="chon-tep inline-block w-auto" accept="application/pdf" aria-labelledby="tieu-de-hoan-cong" @change="fileHoanCong = ($event.target as HTMLInputElement).files?.[0] || null" />
        <Button size="sm" variant="secondary" class="ml-2" :disabled="saving" @click="nopBanVe">Nộp bản vẽ</Button>
        <ul v-if="duLieu?.as_built?.length" class="list-none m-0 p-0 mt-2 text-[13px]">
          <li v-for="a in duLieu.as_built" :key="a.id" class="flex justify-between gap-2 py-1 border-b border-vien-nhat">
            <span>Bản vẽ v{{ a.version }} — {{ new Date(a.ngay_nop).toLocaleString("vi-VN") }}</span>
            <span class="tt tt-xam">{{ a.trang_thai }}</span>
          </li>
        </ul>
        <p v-else class="text-phu text-[13px] mt-2 mb-0">Chưa có bản vẽ hoàn công.</p>
      </div>

      <div v-if="lichSu.length" class="mt-3">
        <h5 class="text-[13px] font-semibold m-0 mb-1">Lịch sử nghiệm thu</h5>
        <div class="the overflow-hidden">
          <table class="bang w-full text-[12.5px]">
            <thead><tr><th>Loại</th><th>Sự kiện</th><th>Trạng thái</th><th>Nội dung</th><th>Thời điểm</th></tr></thead>
            <tbody>
              <tr v-for="h in lichSu" :key="`${h.loai}-${h.id}`">
                <td class="whitespace-nowrap">{{ h.loai === "bien_ban" ? "Biên bản" : h.loai === "ban_ve" ? "Bản vẽ" : "Mốc" }}</td>
                <td class="whitespace-nowrap">{{ h.su_kien }}</td>
                <td class="whitespace-nowrap"><span class="tt tt-lam">{{ h.trang_thai }}</span></td>
                <td class="max-w-[260px]">{{ h.noi_dung || "—" }}</td>
                <td class="whitespace-nowrap text-phu">{{ new Date(h.created_at).toLocaleString("vi-VN") }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="duLieu?.milestones?.length" class="mt-3">
        <h5 class="text-[13px] font-semibold m-0 mb-1">Biên bản đã nộp</h5>
        <ul class="list-none m-0 p-0 text-[13px]">
          <template v-for="m in duLieu.milestones" :key="m.id">
            <li v-for="b in m.bien_ban" :key="b.id" class="py-1 border-b border-vien-nhat">
              <span class="font-medium">{{ b.so_bien_ban }}</span> — {{ m.loai_moc }} lần {{ m.version }}: {{ b.ket_luan }}
            </li>
          </template>
        </ul>
      </div>
    </template>
  </section>
</template>

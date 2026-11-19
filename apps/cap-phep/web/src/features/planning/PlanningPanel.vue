<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { askAssistant, checkPlanning, fetchPlanningDocuments, fetchPlanningParcels, fetchPlanningResults, fetchPlanningZones, type PlanningCheckBody } from "../../api/planning";
import { completeTask, fetchTasks, startWorkflow } from "../../api/flow";
import { notify } from "../../composables/useToast";
import { Badge, Button } from "../../design-system";
import PlanningMap from "./PlanningMap.vue";

const props = defineProps<{
  dossier: any;
  token: string;
  laCanBo: boolean;
}>();

const parcels = ref<any[]>([]);
const zones = ref<any[]>([]);
const documents = ref<any[]>([]);
const history = ref<any[]>([]);
const tasks = ref<any[]>([]);
const selectedId = ref<string>("");
const loading = ref(false);
const checking = ref(false);
const dangTaoViec = ref(false);
const error = ref("");
const ketQua = ref<any>(null);
const traLoiTroLy = ref("");
const trichDanTroLy = ref<any[]>([]);
const dangHoi = ref(false);

const proposal = reactive({
  so_tang: Number(props.dossier?.so_tang ?? 1),
  chieu_cao_m: null as number | null,
  mat_do_xay_dung_pct: null as number | null,
  far: null as number | null,
  khoang_lui_truoc_m: null as number | null,
  khoang_lui_hong_m: null as number | null,
  khoang_lui_sau_m: null as number | null,
  loai_dat: "dat_o",
});

const selectedParcel = computed(() => parcels.value.find((p) => p.id === selectedId.value) || null);
const viecQuyHoach = computed(() => tasks.value.find((t) => {
  const key = t.taskDefinitionKey || "";
  return key === "taskKiemTraQuyHoach" || key === "taskXuLyQuyHoach";
}) || null);
const ketQuaHienTai = computed(() => ketQua.value || history.value[0] || null);
const rules = computed<any[]>(() => ketQuaHienTai.value?.ket_qua || ketQuaHienTai.value?.results || []);
const soLoi = computed(() => rules.value.filter((r) => r.severity === "error").length);
const soCanhBao = computed(() => rules.value.filter((r) => r.severity === "warning").length);

function chonThuaDat(p: any) {
  selectedId.value = p.id;
  proposal.loai_dat = p.loai_dat || proposal.loai_dat;
}

function dinhDang(v: any): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "object") return Object.entries(v).map(([k, x]) => `${k}: ${x ?? "—"}`).join("; ");
  return String(v);
}

function citationText(c: any): string {
  if (!c) return "—";
  const parts = [c.document_code, c.article, c.clause, c.point].filter(Boolean);
  return parts.join(" · ");
}

function trangThaiClass(r: any): string {
  if (r.severity === "error" || r.passed === false) return "tt tt-do";
  if (r.severity === "warning") return "tt tt-vang";
  return "tt tt-xanh";
}

function nhanKetQua(r: any): string {
  if (r.severity === "error" || r.passed === false) return "Không đạt";
  if (r.severity === "warning") return "Cảnh báo";
  if (r.severity === "info" && r.limit === null) return "Chưa cấu hình";
  return "Đạt";
}

async function taiDuLieu() {
  loading.value = true;
  error.value = "";
  try {
    const [p, z, d, h] = await Promise.all([
      fetchPlanningParcels(props.token),
      fetchPlanningZones(props.token),
      fetchPlanningDocuments(props.token),
      props.dossier?.id ? fetchPlanningResults(props.token, props.dossier.id) : Promise.resolve([]),
    ]);
    parcels.value = p;
    zones.value = z;
    documents.value = d;
    history.value = h;
    const m = p.find((x) => x.ma_thua_dat === props.dossier?.thua_dat || x.so_thua === props.dossier?.thua_dat);
    selectedId.value = (m || p[0])?.id || "";
    if (selectedId.value) {
      const sp = p.find((x) => x.id === selectedId.value);
      if (sp?.loai_dat) proposal.loai_dat = sp.loai_dat;
    }
    await taiViec();
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Không tải được dữ liệu quy hoạch";
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

async function taoViecQuyHoach() {
  if (!props.dossier?.id) return;
  dangTaoViec.value = true;
  try {
    await startWorkflow(props.token, "quy-hoach", props.dossier.ma_ho_so, {
      ho_so_id: props.dossier.id,
      ma_ho_so: props.dossier.ma_ho_so,
      dia_chi_cong_trinh: props.dossier.dia_chi_cong_trinh,
      trang_thai_ho_so: props.dossier.trang_thai,
    });
    await new Promise((r) => setTimeout(r, 300));
    await taiViec();
    phatSuKienViec();
    notify("Đã tạo việc kiểm tra quy hoạch trong Bàn làm việc", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tạo được việc kiểm tra quy hoạch", "loi");
  } finally {
    dangTaoViec.value = false;
  }
}

async function hoanThanhViecQuyHoach(kq: any) {
  const viec = viecQuyHoach.value;
  if (!viec) return;
  try {
    const loi = (kq.results || []).filter((r: any) => r.severity === "error").map((r: any) => r.rule_id).join(",");
    await completeTask(props.token, viec.id, {
      quy_hoach_pass: Boolean(kq.pass),
      ket_qua_kiem_tra_id: kq.id,
      quy_hoach_fail_rules: loi,
    });
    await taiViec();
    phatSuKienViec();
    notify("Đã cập nhật việc kiểm tra quy hoạch", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Kết quả đã lưu nhưng chưa hoàn thành được việc quy hoạch", "canh_bao");
  }
}

async function kiemTra() {
  if (!selectedId.value) {
    notify("Chọn thửa đất trước khi kiểm tra", "canh_bao");
    return;
  }
  checking.value = true;
  try {
    const body: PlanningCheckBody = { thua_dat_id: selectedId.value, proposal: { ...proposal } };
    if (props.dossier?.id) body.ho_so_id = props.dossier.id;
    ketQua.value = await checkPlanning(props.token, body);
    traLoiTroLy.value = "";
    trichDanTroLy.value = [];
    notify(ketQua.value.pass ? "Quy hoạch đạt" : `Quy hoạch không đạt: ${ketQua.value.so_loi} lỗi`, ketQua.value.pass ? "ok" : "loi");
    if (props.dossier?.id) history.value = await fetchPlanningResults(props.token, props.dossier.id);
    await hoanThanhViecQuyHoach(ketQua.value);
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không kiểm tra được quy hoạch", "loi");
  } finally {
    checking.value = false;
  }
}

async function hoiTroLy() {
  if (!ketQuaHienTai.value) return;
  dangHoi.value = true;
  try {
    const loi = rules.value
      .filter((r) => r.severity === "error")
      .map((r) => `${r.rule_id} ${r.name}: ${r.reason}`)
      .join("; ");
    const cauHoi = `Vì sao hồ sơ ${props.dossier?.ma_ho_so || ""} không đạt kiểm tra quy hoạch? Các lỗi: ${loi}`;
    const res = await askAssistant(props.token, cauHoi.slice(0, 500));
    traLoiTroLy.value = res?.answer || res?.tra_loi || "Không có câu trả lời.";
    trichDanTroLy.value = Array.isArray(res?.citations) ? res.citations : [];
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không hỏi được trợ lý", "loi");
  } finally {
    dangHoi.value = false;
  }
}

onMounted(taiDuLieu);
</script>

<template>
  <section id="block-dossier-planning" class="mt-5" aria-labelledby="tieu-de-quy-hoach">
    <div class="flex flex-wrap items-baseline justify-between gap-3 mb-2">
      <h4 id="tieu-de-quy-hoach" class="text-[14px] font-semibold m-0">Quy hoạch và chỉ tiêu xây dựng</h4>
      <span class="goi-y">Dữ liệu quy hoạch tổng hợp phục vụ demo</span>
    </div>

    <p v-if="loading" class="text-phu m-0">Đang tải dữ liệu quy hoạch…</p>
    <div v-else-if="error" class="the p-3">
      <p class="canh-bao m-0">{{ error }}</p>
      <button class="btn btn-sm mt-2" @click="taiDuLieu">Thử lại</button>
    </div>
    <template v-else>
      <div class="grid gap-3 md:grid-cols-[1fr_240px] mb-3">
        <PlanningMap :zones="zones" :parcels="parcels" :selected-id="selectedId" @select="chonThuaDat" />
        <div class="the p-3">
          <label class="nhan" for="planning-parcel">Thửa đất kiểm tra</label>
          <select id="planning-parcel" v-model="selectedId" class="o w-full">
            <option v-for="p in parcels" :key="p.id" :value="p.id">{{ p.ma_thua_dat }} — {{ p.so_thua }}, {{ p.to_ban_do }}</option>
          </select>
          <dl v-if="selectedParcel" class="ds-thong-tin mt-2">
            <dt>Địa chỉ</dt><dd>{{ selectedParcel.dia_chi }}</dd>
            <dt>Diện tích</dt><dd>{{ selectedParcel.dien_tich_m2 }} m²</dd>
            <dt>Loại đất</dt><dd>{{ selectedParcel.loai_dat }}</dd>
            <dt>Mã địa điểm</dt><dd>{{ selectedParcel.ma_dinh_danh_dia_diem || "Chưa có" }}</dd>
          </dl>
          <p v-if="!parcels.length" class="text-phu text-[13px] mt-2 mb-0">Địa bàn chưa có dữ liệu thửa đất quy hoạch.</p>
        </div>
      </div>

      <div v-if="laCanBo" class="the p-3 mb-3">
        <h5 class="text-[13px] font-semibold mt-0 mb-2">Thông số đề xuất</h5>
        <div class="grid gap-2 sm:grid-cols-3">
          <label class="block"><span class="nhan">Số tầng</span><input id="planning-floors" v-model.number="proposal.so_tang" type="number" min="1" class="o w-full" /></label>
          <label class="block"><span class="nhan">Chiều cao (m)</span><input id="planning-height" v-model.number="proposal.chieu_cao_m" type="number" min="0" step="0.1" class="o w-full" /></label>
          <label class="block"><span class="nhan">Mật độ xây dựng (%)</span><input id="planning-density" v-model.number="proposal.mat_do_xay_dung_pct" type="number" min="0" max="100" class="o w-full" /></label>
          <label class="block"><span class="nhan">Hệ số sử dụng đất</span><input id="planning-far" v-model.number="proposal.far" type="number" min="0" step="0.1" class="o w-full" /></label>
          <label class="block"><span class="nhan">Khoảng lùi trước (m)</span><input id="planning-setback-front" v-model.number="proposal.khoang_lui_truoc_m" type="number" min="0" step="0.1" class="o w-full" /></label>
          <label class="block"><span class="nhan">Khoảng lùi hông (m)</span><input id="planning-setback-side" v-model.number="proposal.khoang_lui_hong_m" type="number" min="0" step="0.1" class="o w-full" /></label>
          <label class="block"><span class="nhan">Khoảng lùi sau (m)</span><input id="planning-setback-back" v-model.number="proposal.khoang_lui_sau_m" type="number" min="0" step="0.1" class="o w-full" /></label>
          <label class="block"><span class="nhan">Loại đất</span>
            <select v-model="proposal.loai_dat" class="o w-full">
              <option value="dat_o">Đất ở</option>
              <option value="dat_nong_nghiep">Đất nông nghiệp</option>
              <option value="dat_thuong_mai">Đất thương mại, dịch vụ</option>
            </select>
          </label>
        </div>
        <Button id="planning-check-btn" class="mt-3" :disabled="checking || !parcels.length" @click="kiemTra">
          {{ checking ? "Đang kiểm tra…" : "Kiểm tra quy hoạch" }}
        </Button>
        <div class="mt-2 flex flex-wrap items-center gap-2 text-[13px]">
          <Button v-if="!viecQuyHoach" size="sm" variant="secondary" :disabled="dangTaoViec" @click="taoViecQuyHoach">
            {{ dangTaoViec ? "Đang tạo việc…" : "Tạo việc kiểm tra quy hoạch (workflow)" }}
          </Button>
          <span v-else class="text-phu">Việc {{ viecQuyHoach.name || viecQuyHoach.taskDefinitionKey }} đang chờ trong Bàn làm việc.</span>
        </div>
      </div>

      <div v-if="ketQuaHienTai" class="the p-3">
        <div class="flex flex-wrap items-center gap-2 mb-2">
          <Badge id="planning-result-badge" :tone="ketQuaHienTai.pass ? 'success' : 'danger'">{{ ketQuaHienTai.pass ? "Đạt quy hoạch" : "Không đạt quy hoạch" }}</Badge>
          <span class="mo">{{ soLoi }} lỗi · {{ soCanhBao }} cảnh báo</span>
          <span class="mo">Lúc {{ new Date(ketQuaHienTai.created_at || Date.now()).toLocaleString("vi-VN") }}</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-[13px] border-collapse">
            <thead>
              <tr class="text-left border-b border-vien-nhat">
                <th class="py-1.5 pr-2">Quy tắc</th>
                <th class="py-1.5 pr-2">Giá trị</th>
                <th class="py-1.5 pr-2">Giới hạn</th>
                <th class="py-1.5 pr-2">Kết quả</th>
                <th class="py-1.5">Căn cứ</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in rules" :key="r.rule_id" class="border-b border-vien-nhat align-top">
                <td class="py-1.5 pr-2">{{ r.rule_id }} — {{ r.name }}</td>
                <td class="py-1.5 pr-2">{{ dinhDang(r.value) }}</td>
                <td class="py-1.5 pr-2">{{ dinhDang(r.limit) }}</td>
                <td class="py-1.5 pr-2"><span :class="trangThaiClass(r)">{{ nhanKetQua(r) }}</span></td>
                <td class="py-1.5">
                  <template v-if="r.citation">
                    <a v-if="r.citation.source_url" :href="r.citation.source_url" target="_blank" rel="noopener" class="btn-lien-ket">{{ citationText(r.citation) }}</a>
                    <span v-else>{{ citationText(r.citation) }}</span>
                    <span v-if="r.citation.can_doi_chieu" class="block goi-y">Cần đối chiếu bản gốc</span>
                  </template>
                  <span v-else class="text-phu">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!rules.length" class="text-phu m-0">Chưa có kết quả kiểm tra.</p>
        <p v-for="r in rules.filter((x) => x.severity === 'warning')" :key="'w-' + r.rule_id" class="text-vang text-[13px] mt-1 mb-0">
          Cảnh báo {{ r.rule_id }}: {{ r.reason }}
        </p>
        <div v-if="laCanBo && !ketQuaHienTai.pass" class="mt-3 border-t border-vien-nhat pt-3">
          <button class="btn btn-sm" :disabled="dangHoi" @click="hoiTroLy">
            {{ dangHoi ? "Đang hỏi trợ lý…" : "Giải thích bằng trợ lý (có trích dẫn)" }}
          </button>
          <div v-if="traLoiTroLy" class="mt-2 text-[13px] whitespace-pre-wrap">{{ traLoiTroLy }}</div>
          <ul v-if="trichDanTroLy.length" class="list-none m-0 p-0 mt-2 text-[12.5px]">
            <li v-for="(c, i) in trichDanTroLy" :key="i" class="py-1 border-b border-vien-nhat">
              <span class="font-medium">[{{ c.so || i + 1 }}]</span> {{ c.nguon }} — {{ c.trich }}
            </li>
          </ul>
        </div>
      </div>

      <div v-if="documents.length" class="mt-3">
        <h5 class="text-[13px] font-semibold m-0 mb-1">Văn bản quy hoạch</h5>
        <ul class="list-none m-0 p-0 text-[13px]">
          <li v-for="d in documents" :key="d.id" class="py-1 border-b border-vien-nhat">
            <a v-if="d.file_url" :href="d.file_url" target="_blank" rel="noopener" class="btn-lien-ket">{{ d.ma_van_ban }} — {{ d.ten }}</a>
            <span v-else>{{ d.ma_van_ban }} — {{ d.ten }}</span>
            <span v-if="d.legal_document_code" class="goi-y"> · Căn cứ {{ d.legal_document_code }}</span>
          </li>
        </ul>
      </div>

      <div v-if="history.length > 1" class="mt-3">
        <h5 class="text-[13px] font-semibold m-0 mb-1">Lịch sử kiểm tra</h5>
        <ul class="list-none m-0 p-0 text-[13px]">
          <li v-for="h in history" :key="h.id" class="flex justify-between gap-2 py-1 border-b border-vien-nhat">
            <span>{{ new Date(h.created_at).toLocaleString("vi-VN") }}</span>
            <span :class="h.pass ? 'tt tt-xanh' : 'tt tt-do'">{{ h.pass ? "Đạt" : "Không đạt" }}</span>
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>

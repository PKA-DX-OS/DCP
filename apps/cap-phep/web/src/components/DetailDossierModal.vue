<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div id="modal-detail-dossier" class="nen-hop" @click.self="$emit('close')">
    <div ref="hop" tabindex="-1" class="hop max-w-[1100px]" role="dialog" aria-modal="true" aria-labelledby="detail-ma-ho-so">
      <div class="hop-dau">
        <div>
          <span class="mo">Chi tiết hồ sơ</span>
          <h2 id="detail-ma-ho-so" class="ma">{{ hoSoHienTai.ma_ho_so }}</h2>
          <div class="flex flex-wrap items-center gap-2 mt-1.5">
            <span id="detail-trang-thai" :class="getStatusBadgeClass(hoSoHienTai.trang_thai)">{{ formatStatus(hoSoHienTai.trang_thai) }}</span>
            <span class="mo">Bước hiện tại: <span id="detail-buoc">{{ tenBuoc(hoSoHienTai.buoc) }}</span></span>
          </div>
        </div>
        <button type="button" class="nut-dong" aria-label="Đóng" @click="$emit('close')"><IconX /></button>
      </div>

      <DossierActionBar v-if="laCanBo && userToken" :dossier="dossier" :token="userToken" class="mx-5" @done="hoSoCapNhat = $event" />
      <DossierWarnings v-if="laCanBo && userToken" :dossier="dossier" :token="userToken" class="mx-5" />

      <nav class="flex gap-1 overflow-x-auto border-b border-vien-nhat px-5" aria-label="Các phần của hồ sơ">
        <button
          v-for="m in mucHien"
          :key="m.id"
          type="button"
          :id="`tab-chi-tiet-${m.id}`"
          :aria-controls="m.id"
          :aria-current="mucDangXem === m.id ? 'true' : undefined"
          :class="[
            'shrink-0 border-b-2 px-2.5 py-2 text-[12.5px] whitespace-nowrap transition',
            mucDangXem === m.id
              ? 'border-[rgb(var(--c-cham))] font-semibold text-chu'
              : 'border-transparent text-phu hover:text-chu',
          ]"
          @click="denMuc(m.id)"
        >{{ m.ten }}</button>
      </nav>

      <div ref="than" class="hop-than">
        <div class="grid gap-5 lg:grid-cols-2">
          <div :class="mobileMuc('muc-thong-tin')">
            <h3 id="muc-thong-tin" class="muc-con">Chủ đầu tư</h3>
            <dl class="ds-thong-tin">
              <dt>Họ tên</dt><dd id="detail-chu-dau-tu">{{ dossier.ho_ten }}</dd>
              <dt>CCCD</dt><dd>{{ cheCccd(dossier.cccd) }}</dd>
              <dt>Điện thoại</dt><dd>{{ dossier.dien_thoai }}</dd>
              <dt>Địa bàn</dt><dd>{{ tenDonVi(dossier.tenant) }}</dd>
            </dl>
          </div>
          <div :class="mobileMuc('muc-thong-tin')">
            <h3 class="muc-con">Công trình</h3>
            <dl class="ds-thong-tin">
              <dt>Địa chỉ</dt><dd id="detail-dia-chi">{{ dossier.dia_chi_cong_trinh }}</dd>
              <dt>Thửa đất</dt><dd>{{ dossier.thua_dat }}</dd>
              <dt>Quy mô</dt><dd>{{ dossier.so_tang }} tầng, diện tích sàn {{ formatNumberVi(dossier.dien_tich_san_m2) }} m²</dd>
            </dl>
          </div>
        </div>

        <Dossier360Panel
          v-if="userToken"
          :dossier="dossier"
          :token="userToken"
          :class="mobileMuc('block-dossier-360')"
        />

        <section v-if="dossier.trang_thai === 'DA_CAP' || permitInfo" id="block-giay-phep-signature" class="mt-5 p-4 rounded-[10px] border border-vien bg-mat" :class="mobileMuc('muc-thong-tin')">
          <div class="flex items-center justify-between gap-3 mb-3">
            <h3 class="text-[14px] font-semibold m-0">Giấy phép và chữ ký số</h3>
            <span id="badge-permit-status" :class="permitInfo?.trang_thai === 'revoked' ? 'tt tt-do' : 'tt tt-xanh'">
              {{ permitInfo?.trang_thai === "revoked" ? "Đã thu hồi" : permitInfo?.trang_thai === "valid" ? "Hợp lệ" : "Đã cấp" }}
            </span>
          </div>
          <p v-if="loadingPermit" class="text-phu m-0">Đang tải thông tin giấy phép…</p>
          <template v-else-if="permitInfo">
            <dl class="ds-thong-tin">
              <dt>Số giấy phép</dt><dd><b id="val-so-giay-phep" class="font-semibold">{{ permitInfo.so_giay_phep }}</b></dd>
              <dt>Ngày cấp</dt><dd>{{ ngayNgan(permitInfo.ngay_cap) }}</dd>
              <dt>Người ký</dt><dd id="val-nguoi-ky">{{ permitInfo.nguoi_ky || "Không xác định" }}</dd>
              <dt>Chữ ký số</dt>
              <dd><span id="val-thuat-toan">{{ permitInfo.thuat_toan || "Không xác định" }}</span><template v-if="permitInfo.khoa_phien_ban && !isPades">, khóa phiên bản {{ permitInfo.khoa_phien_ban }}</template></dd>
              <dt>Mã tra cứu</dt>
              <dd><a id="link-public-code" :href="'/kiem-tra/' + permitInfo.ma_cong_khai" target="_blank" rel="noopener" class="btn-lien-ket break-all">{{ permitInfo.ma_cong_khai }}</a></dd>
              <dt>Mã băm SHA-256</dt>
              <dd class="text-[12.5px] text-phu break-all">
                {{ permitInfo.ma_bam }}
                <button type="button" class="btn-lien-ket ml-1" @click="copyText(permitInfo.ma_bam, 'hash')">{{ copiedField === "hash" ? "Đã chép" : "Chép" }}</button>
              </dd>
              <dt>Chữ ký</dt>
              <dd v-if="isPades" class="text-[12.5px] text-phu">Nhúng trong tệp PDF, kiểm tra được bằng trình đọc PDF hoặc trang tra cứu</dd>
              <dd v-else class="text-[12.5px] text-phu">
                <span class="break-all">{{ shortSig }}</span>
                <button type="button" class="btn-lien-ket ml-1" @click="copyText(permitInfo.chu_ky, 'sig')">{{ copiedField === "sig" ? "Đã chép" : "Chép đầy đủ" }}</button>
              </dd>
            </dl>
            <div class="flex flex-wrap gap-2 mt-4">
              <a :href="'/kiem-tra/' + permitInfo.ma_cong_khai" target="_blank" rel="noopener" class="btn btn-sm">Mở trang tra cứu</a>
              <button type="button" id="btn-download-permit" class="btn btn-sm btn-chinh" @click="downloadPermit">Tải giấy phép (PDF)</button>
              <button
                v-if="laLanhDao && permitInfo.trang_thai === 'valid' && permitDocId"
                type="button"
                class="btn btn-sm text-son"
                @click="hienThuHoi = !hienThuHoi"
              >
                Thu hồi giấy phép
              </button>
            </div>
            <form v-if="hienThuHoi" class="mt-3 rounded-[12px] border border-vien-nhat p-2" @submit.prevent="thuHoiGiayPhep">
              <label class="block">
                <span class="nhan">Lý do thu hồi (bắt buộc)</span>
                <input v-model="lyDoThuHoi" class="o w-full" required placeholder="Ví dụ: phát hiện sai lệch thông tin cấp phép" />
              </label>
              <div class="mt-2 flex flex-wrap gap-2">
                <button type="submit" class="btn btn-sm text-son" :disabled="dangThuHoi || !lyDoThuHoi.trim()">
                  {{ dangThuHoi ? "Đang thu hồi…" : "Xác nhận thu hồi" }}
                </button>
                <button type="button" class="btn btn-sm" @click="hienThuHoi = false">Hủy</button>
              </div>
            </form>
          </template>
        </section>

        <section id="block-dossier-files" class="mt-5" :class="mobileMuc('block-dossier-files')" aria-labelledby="tieu-de-giay-to">
          <div class="flex items-baseline justify-between gap-3 mb-2">
            <h3 id="tieu-de-giay-to" class="text-[14px] font-semibold m-0">Giấy tờ đã nộp</h3>
            <span class="mo">{{ docs.length }} tệp</span>
          </div>
          <p v-if="loadingDocs" class="text-phu m-0">Đang tải danh sách giấy tờ…</p>
          <p v-else-if="docs.length === 0" class="text-phu m-0">Chưa có giấy tờ đính kèm.</p>
          <ul v-else class="list-none m-0 p-0">
            <li v-for="d in docs" :key="d.id" class="the-tep flex-col !items-stretch">
              <div class="flex items-center justify-between gap-3">
                <span class="font-medium">{{ d.ten_loai || d.loai }}<span class="text-phu font-normal">, lần nộp {{ d.version || 1 }}</span></span>
                <span :class="['tt', docTone(d)]">{{ docStatusLabel(d) }}</span>
              </div>
              <p v-if="d.trang_thai_kiem_tra === 'khong_dat' && d.ly_do" class="text-son text-[13px] mt-1 mb-0">Lý do: {{ d.ly_do }}</p>
              <div v-if="d.file_id && (d.mime === 'application/pdf' || String(d.ten_file || '').toLowerCase().endsWith('.pdf'))" class="mt-2">
                <button type="button" class="btn btn-sm" :disabled="dangXemTruoc === d.id" @click="xemTruocTep(d)">
                  {{ dangXemTruoc === d.id ? "Đang tải…" : "Xem trước PDF" }}
                </button>
              </div>
              <div v-if="laCanBo && userToken" class="mt-2 flex flex-wrap items-center gap-2">
                <span class="goi-y">Đánh giá giấy tờ:</span>
                <button type="button" class="btn btn-sm" :disabled="dangLuuTep === d.id" @click="danhGiaTep(d, 'dat')">Đạt</button>
                <button type="button" class="btn btn-sm text-vang" :disabled="dangLuuTep === d.id" @click="moDanhGiaTep(d)">Không đạt</button>
              </div>
              <form v-if="dangDanhGia === d.id" class="mt-2 flex flex-wrap gap-2" @submit.prevent="danhGiaTep(d, 'khong_dat')">
                <label class="min-w-[220px] flex-1">
                  <span class="sr-only">Lý do không đạt</span>
                  <input v-model="lyDoTep" class="o w-full" required placeholder="Lý do không đạt, ví dụ: bản vẽ thiếu chữ ký" />
                </label>
                <button type="submit" class="btn btn-sm" :disabled="dangLuuTep === d.id || !lyDoTep.trim()">
                  {{ dangLuuTep === d.id ? "Đang lưu…" : "Lưu" }}
                </button>
                <button type="button" class="btn btn-sm" @click="dangDanhGia = ''">Hủy</button>
              </form>
            </li>
          </ul>
        </section>

        <PlanningPanel v-if="laCanBo && userToken" :class="mobileMuc('block-dossier-planning')" :dossier="dossier" :token="userToken" :la-can-bo="laCanBo" />
        <AcceptancePanel v-if="laCanBo && userToken" :class="mobileMuc('block-dossier-acceptance')" :dossier="dossier" :token="userToken" />
        <DossierLegalPanel
          v-if="laCanBo && userToken"
          :class="mobileMuc('block-dossier-legal')"
          :dossier="dossier"
          :token="userToken"
          :co-the-kiem-tra="coTheKiemTra"
        />

        <section id="block-dossier-progress" class="mt-5" :class="mobileMuc('block-dossier-progress')" aria-labelledby="tieu-de-tien-trinh">
          <h3 id="tieu-de-tien-trinh" class="text-[14px] font-semibold m-0 mb-2">Tiến trình quy trình</h3>
          <ol id="list-dossier-progress" class="list-none m-0 p-0 flex flex-wrap gap-x-2 gap-y-1 text-[13px]">
            <li v-for="(b, i) in TIEN_TRINH" :key="b" class="flex items-center gap-2">
              <span
                :class="[
                  'tt',
                  i < viTriBuoc ? 'tt-xanh' : i === viTriBuoc ? 'tt-lam' : 'tt-xam',
                ]"
                :aria-current="i === viTriBuoc ? 'step' : undefined"
              >{{ tenBuoc(b) }}</span>
              <span v-if="i < TIEN_TRINH.length - 1" class="text-phu" aria-hidden="true">›</span>
            </li>
          </ol>
          <p v-if="hoSoHienTai.trang_thai === 'TU_CHOI'" class="text-son text-[13px] mt-2 mb-0">Hồ sơ đã bị từ chối.</p>
          <p v-else-if="hoSoHienTai.trang_thai === 'CAN_BO_SUNG'" class="text-vang text-[13px] mt-2 mb-0">Đang chờ chủ đầu tư bổ sung hồ sơ.</p>
        </section>

        <section id="block-dossier-audit" class="mt-5" :class="mobileMuc('block-dossier-audit')" aria-labelledby="tieu-de-lich-su">
          <div class="flex items-baseline justify-between gap-3 mb-1">
            <h3 id="tieu-de-lich-su" class="text-[14px] font-semibold m-0">Ai đã xem và xử lý hồ sơ</h3>
            <span class="mo">{{ auditList.length }} ghi nhận</span>
          </div>
          <p class="goi-y mt-0 mb-2">Mọi lần mở hồ sơ, xem tệp và xử lý đều được ghi lại và không sửa được. Sắp theo thời gian, cũ nhất trước.</p>
          <p v-if="loadingAudit" class="text-phu m-0">Đang tải nhật ký…</p>
          <p v-else-if="auditList.length === 0" class="text-phu m-0">Chưa có ghi nhận nào.</p>
          <ol v-else id="list-dossier-audit" tabindex="0" aria-labelledby="tieu-de-lich-su" class="list-none m-0 p-0 max-h-[260px] overflow-y-auto border-t border-vien-nhat">
            <li
              v-for="(item, idx) in lichSuTheoThoiGian"
              :key="idx"
              :class="['grid grid-cols-[110px_1fr] gap-3 py-2.5 border-b border-vien-nhat text-[13px]', isBreakGlass(item) && 'text-son']"
            >
              <time class="text-phu">{{ ngayGio(item.at) }}</time>
              <span>
                <b class="font-medium">{{ tenHanhDong(item.action) }}</b>
                <span class="block" :class="isBreakGlass(item) ? '' : 'text-phu'">
                  {{ item.actor_name || item.actor_sub || "Hệ thống" }}<template v-if="vaiNghiepVu(item.actor_roles)">, {{ vaiNghiepVu(item.actor_roles) }}</template>
                </span>
                <span v-if="getAuditReason(item)" class="block">Lý do: {{ getAuditReason(item) }}</span>
              </span>
            </li>
          </ol>
        </section>

        <!-- Phần do feature đăng ký (features/registry.ts: DOSSIER_TABS) -->
        <section v-for="t in tabMoRong" :id="'muc-' + t.ma" :key="t.ma" class="mt-5" :class="mobileMuc('muc-' + t.ma)">
          <h3 class="muc-con">{{ t.ten }}</h3>
          <component :is="t.component" :dossier="dossier" :user-token="userToken" />
        </section>
      </div>

      <div class="hop-chan">
        <button
          v-if="hoSoHienTai.trang_thai === 'CAN_BO_SUNG'"
          type="button"
          id="btn-modal-supplement"
          class="btn mr-auto text-vang"
          @click="$emit('supplement', hoSoHienTai)"
        >Bổ sung hồ sơ</button>
        <button type="button" id="btn-close-modal-detail" class="btn" @click="$emit('close')">Đóng</button>
      </div>
    </div>

    <div v-if="previewUrl" class="fixed inset-0 z-[90] flex flex-col bg-black/70 p-3 sm:p-6" role="dialog" aria-modal="true" aria-label="Xem trước tệp PDF">
      <div class="mx-auto flex w-full max-w-[1000px] items-center justify-between gap-3 rounded-t-[14px] bg-white px-4 py-2 text-slate-900">
        <b class="min-w-0 truncate text-[13.5px]">{{ previewName }}</b>
        <div class="flex gap-2">
          <a :href="previewUrl" target="_blank" rel="noopener" class="btn btn-sm">Mở tab mới</a>
          <button type="button" class="btn btn-sm" @click="dongXemTruoc">Đóng</button>
        </div>
      </div>
      <iframe :src="previewUrl" title="Xem trước tệp PDF" class="mx-auto h-full w-full max-w-[1000px] rounded-b-[14px] bg-white"></iframe>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import IconX from "./IconX.vue";
import { notify } from "../composables/useToast";
import { useModal } from "../composables/useModal";
import PlanningPanel from "../features/planning/PlanningPanel.vue";
import AcceptancePanel from "../features/acceptance/AcceptancePanel.vue";
import DossierActionBar from "./DossierActionBar.vue";
import DossierWarnings from "./DossierWarnings.vue";
import DossierLegalPanel from "./DossierLegalPanel.vue";
import Dossier360Panel from "./Dossier360Panel.vue";
import { readRoles } from "../auth";
import { downloadFile, fetchDossierFiles, fetchDossierHistory, fetchPermitInfo, reviewDossierFile } from "../api";
import { revokeSignedDocument } from "../api/legal";
import { API_BASE } from "../config";
import { cheCccd, tenDonVi, tenBuoc, tenHanhDong, vaiNghiepVu, ngayNgan, ngayGio } from "../utils/labels";
import type { HoSo } from "../types";
import { formatStatus, getStatusBadgeClass, formatNumberVi } from "../utils/formatters";
import { dossierTabsChoVai } from "../features/registry";
import { useOptionalFeatureContext } from "../features/context";

const props = defineProps<{
  dossier: HoSo;
  userToken?: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "supplement", dossier: HoSo): void;
}>();

const hop = ref<HTMLElement | null>(null);
const than = ref<HTMLElement | null>(null);
const hoSoCapNhat = ref<any>(null);
const hoSoHienTai = computed(() => hoSoCapNhat.value || props.dossier);
useModal(hop, () => emit("close"));

/** Thanh tab chuyển nhanh tới từng phần; mọi phần vẫn hiển thị để đọc liền một mạch. */
const MUC_CO_BAN = [
  { id: "muc-thong-tin", ten: "Thông tin" },
  { id: "block-dossier-360", ten: "Tổng hợp" },
  { id: "block-dossier-files", ten: "Giấy tờ" },
  { id: "block-dossier-planning", ten: "Quy hoạch" },
  { id: "block-dossier-acceptance", ten: "Nghiệm thu" },
  { id: "block-dossier-legal", ten: "Pháp lý" },
  { id: "block-dossier-audit", ten: "Lịch sử xử lý" },
  { id: "block-dossier-progress", ten: "Tiến trình" },
] as const;
const VAI_CAN_BO = [
  "app:cap-phep:mot-cua",
  "app:cap-phep:tham-dinh",
  "app:cap-phep:lanh-dao",
  "app:cap-phep:trat-tu-xd",
  "dx:auditor",
  "dx:platform-admin",
];
const VAI_KIEM_TRA = [
  "app:cap-phep:mot-cua",
  "app:cap-phep:tham-dinh",
  "app:cap-phep:lanh-dao",
  "dx:platform-admin",
  "dx:tenant-admin",
];
const laCanBo = computed(() => readRoles(props.userToken).some((r) => VAI_CAN_BO.includes(r)));
const coTheKiemTra = computed(() => readRoles(props.userToken).some((r) => VAI_KIEM_TRA.includes(r)));
const laLanhDao = computed(() => readRoles(props.userToken).includes("app:cap-phep:lanh-dao"));
const featureCtx = useOptionalFeatureContext();
const tabMoRong = computed(() => dossierTabsChoVai(featureCtx?.vaiTro.value ?? [], props.dossier));
const MUC = computed(() =>
  MUC_CO_BAN.filter(
    (m) =>
      (m.id !== "block-dossier-360" || Boolean(props.userToken)) &&
      (laCanBo.value ||
        (m.id !== "block-dossier-planning" &&
          m.id !== "block-dossier-acceptance" &&
          m.id !== "block-dossier-legal")),
  ),
);
const mucHien = computed(() => [...MUC.value, ...tabMoRong.value.map((t) => ({ id: `muc-${t.ma}`, ten: t.ten }))]);
const mucDangXem = ref<string>(MUC_CO_BAN[0].id);
function denMuc(id: string) {
  mucDangXem.value = id;
  than.value?.querySelector<HTMLElement>(`#${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
}
/** Mobile: chỉ mở mục đang chọn (accordion); desktop: hiện đủ như cũ. */
function mobileMuc(id: string): string {
  return mucDangXem.value === id ? "" : "hidden md:block";
}

const TIEN_TRINH = ["tiep_nhan", "phan_cong", "tham_dinh", "phe_duyet", "hoan_thanh"];
const viTriBuoc = computed(() => {
  if (hoSoHienTai.value.trang_thai === "DA_CAP") return TIEN_TRINH.length;
  const i = TIEN_TRINH.indexOf(String(hoSoHienTai.value.buoc || ""));
  return i < 0 ? 0 : i;
});

const permitInfo = ref<any>(null);
const loadingPermit = ref(false);
const hienThuHoi = ref(false);
const lyDoThuHoi = ref("");
const dangThuHoi = ref(false);
const isPades = computed(() => String(permitInfo.value?.thuat_toan || "").startsWith("PAdES"));
const permitDocId = computed(() => {
  const match = String(permitInfo.value?.file_url || "").match(/\/docs\/([^/]+)\/download/);
  return match?.[1] || "";
});
const docs = ref<any[]>([]);
const loadingDocs = ref(false);
const dangDanhGia = ref("");
const lyDoTep = ref("");
const dangLuuTep = ref("");
const previewUrl = ref("");
const previewName = ref("");
const dangXemTruoc = ref("");

// Trạng thái kiểm tra từng giấy tờ do cán bộ đánh giá (đạt / không đạt / cách ly)
function docStatusLabel(d: any): string {
  const st = d.trang_thai_kiem_tra || "cho_kiem_tra";
  if (st === "dat") return "Đạt";
  if (st === "khong_dat") return "Không đạt";
  if (st === "cach_ly") return "Cách ly";
  return "Chờ kiểm tra";
}
function docTone(d: any): string {
  const st = d.trang_thai_kiem_tra || "cho_kiem_tra";
  if (st === "dat") return "tt-xanh";
  if (st === "khong_dat") return "tt-do";
  if (st === "cach_ly") return "tt-xam";
  return "tt-vang";
}
async function loadDocs() {
  if (!props.userToken) return;
  loadingDocs.value = true;
  try {
    docs.value = await fetchDossierFiles(props.userToken, props.dossier.id);
  } catch {
    docs.value = [];
  } finally {
    loadingDocs.value = false;
  }
}

function moDanhGiaTep(d: any): void {
  dangDanhGia.value = d.id;
  lyDoTep.value = "";
}

async function danhGiaTep(d: any, trangThai: "dat" | "khong_dat"): Promise<void> {
  if (!props.userToken) return;
  if (trangThai === "khong_dat" && !lyDoTep.value.trim()) {
    notify("Nhập lý do không đạt", "canh_bao");
    return;
  }
  dangLuuTep.value = d.id;
  try {
    await reviewDossierFile(
      props.userToken,
      d.id,
      trangThai,
      trangThai === "khong_dat" ? lyDoTep.value.trim() : "",
    );
    d.trang_thai_kiem_tra = trangThai;
    d.ly_do = trangThai === "khong_dat" ? lyDoTep.value.trim() : null;
    notify(trangThai === "dat" ? "Đã đánh giá giấy tờ đạt" : "Đã ghi nhận giấy tờ không đạt", "ok");
    dangDanhGia.value = "";
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không đánh giá được giấy tờ", "loi");
  } finally {
    dangLuuTep.value = "";
  }
}
async function xemTruocTep(d: any): Promise<void> {
  if (!props.userToken || !d.file_id) return;
  dangXemTruoc.value = d.id;
  try {
    const blob = await downloadFile(props.userToken, `/files/${encodeURIComponent(d.file_id)}/download`);
    if (!String(d.mime || "").includes("pdf") && !blob.type.includes("pdf")) {
      notify("Tệp này không phải PDF nên chưa xem trước được. Hãy tải về để mở.", "canh_bao");
      return;
    }
    dongXemTruoc();
    previewUrl.value = window.URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
    previewName.value = d.ten_loai || d.loai || "Tệp đính kèm";
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không xem trước được tệp", "loi");
  } finally {
    dangXemTruoc.value = "";
  }
}

function dongXemTruoc(): void {
  if (previewUrl.value) window.URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = "";
  previewName.value = "";
}

onBeforeUnmount(dongXemTruoc);

const auditList = ref<any[]>([]);
const lichSuTheoThoiGian = computed(() =>
  [...auditList.value].sort((a, b) => new Date(a.at || 0).getTime() - new Date(b.at || 0).getTime()),
);
const loadingAudit = ref(false);
const copiedField = ref("");
const shortSig = computed(() => {
  const sig = String(permitInfo.value?.chu_ky || "");
  return sig.length > 28 ? sig.slice(0, 14) + "…" + sig.slice(-10) : sig;
});

function copyText(text: string, field: string) {
  if (!text) return;
  navigator.clipboard?.writeText(text).catch(() => notify("Trình duyệt không cho chép tự động.", "loi"));
  copiedField.value = field;
  setTimeout(() => {
    copiedField.value = "";
  }, 2000);
}

// U-01: bản gốc giấy phép chỉ tải được kèm token đăng nhập
async function downloadPermit() {
  if (!permitInfo.value?.file_url || !props.userToken) return;
  try {
    // file_url dạng "/api/v1/docs/<id>/download": bỏ gốc API để client chung ghép lại
    const url0 = String(permitInfo.value.file_url);
    const duongDan = url0.startsWith(`${API_BASE}/`) ? url0.slice(API_BASE.length) : url0;
    const blob = await downloadFile(props.userToken, duongDan);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${permitInfo.value.so_giay_phep || "giay-phep"}.pdf`;
    a.click();
    setTimeout(() => window.URL.revokeObjectURL(url), 5000);
  } catch (err: any) {
    notify(`Không tải được giấy phép: ${err.message}`, "loi");
  }
}

async function thuHoiGiayPhep() {
  if (!props.userToken || !permitDocId.value) {
    notify("Không xác định được văn bản cần thu hồi", "loi");
    return;
  }
  if (!lyDoThuHoi.value.trim()) {
    notify("Nhập lý do thu hồi giấy phép", "canh_bao");
    return;
  }
  dangThuHoi.value = true;
  try {
    await revokeSignedDocument(props.userToken, permitDocId.value, lyDoThuHoi.value.trim());
    permitInfo.value = await fetchPermitInfo(props.userToken, props.dossier.id);
    hienThuHoi.value = false;
    lyDoThuHoi.value = "";
    notify("Đã thu hồi giấy phép và ghi nhận vào nhật ký", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không thu hồi được giấy phép", "loi");
  } finally {
    dangThuHoi.value = false;
  }
}

function isBreakGlass(item: any): boolean {
  if (!item) return false;
  const act = String(item.action || "").toLowerCase();
  return act.includes("break_glass") || act.includes("truy_cap_khan");
}

function getAuditReason(item: any): string {
  if (!item || !item.detail) return "";
  return item.detail.reason || item.detail.ly_do || item.detail.loi || "";
}



onMounted(async () => {
  if (!props.dossier?.id || !props.userToken) return;

  loadDocs();

  // 1. Tải thông tin giấy phép (nếu đã cấp phép hoặc đang trong quy trình)
  loadingPermit.value = true;
  try {
    const data = await fetchPermitInfo(props.userToken, props.dossier.id);
    if (data && data.so_giay_phep) {
      permitInfo.value = data;
    }
  } catch (err) {
    console.debug("Lỗi tải thông tin giấy phép:", err);
  } finally {
    loadingPermit.value = false;
  }

  // 2. Tải nhật ký kiểm toán hồ sơ
  loadingAudit.value = true;
  try {
    const data = await fetchDossierHistory(props.userToken, props.dossier.id);
    auditList.value = Array.isArray(data) ? data : [];
  } catch (err) {
    console.debug("Lỗi tải nhật ký hồ sơ:", err);
  } finally {
    loadingAudit.value = false;
  }
});
</script>

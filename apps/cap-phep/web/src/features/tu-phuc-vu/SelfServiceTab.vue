<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useFeatureContext } from "../context";
import { getValidToken } from "../../auth";
import { fetchPermitInfo } from "../../api/dossiers";
import { downloadFile } from "../../api/files";
import { API_BASE } from "../../config";
import { notify } from "../../composables/useToast";
import { formatNumberVi, formatStatus, getStatusBadgeClass } from "../../utils/formatters";
import { ngayGio, ngayNgan, tenBuoc } from "../../utils/labels";
import QrCodeModal from "../../components/QrCodeModal.vue";
import type { HoSo } from "../../types";

const { cd, moHoSo, moBoSung, moNopHoSo } = useFeatureContext();

type Loc = "tat-ca" | "dang-xu-ly" | "can-bo-sung" | "da-cap";
const TIEN_TRINH = ["tiep_nhan", "phan_cong", "tham_dinh", "phe_duyet", "hoan_thanh"];
const loc = ref<Loc>("tat-ca");
const dangTaiKetQua = ref<string | null>(null);
const qr = ref<{ url: string; ma: string; tieuDe: string } | null>(null);
const cacheGiayPhep = new Map<string, any>();

const ds = computed(() => [...cd.dossiers.value].sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime()));
const dangXuLy = computed(() => ds.value.filter((d) => !["DA_CAP", "TU_CHOI", "CAN_BO_SUNG"].includes(String(d.trang_thai))).length);
const canBoSung = computed(() => ds.value.filter((d) => d.trang_thai === "CAN_BO_SUNG").length);
const daCap = computed(() => ds.value.filter((d) => d.trang_thai === "DA_CAP").length);

const dsLoc = computed(() => {
  if (loc.value === "tat-ca") return ds.value;
  if (loc.value === "can-bo-sung") return ds.value.filter((d) => d.trang_thai === "CAN_BO_SUNG");
  if (loc.value === "da-cap") return ds.value.filter((d) => d.trang_thai === "DA_CAP");
  return ds.value.filter((d) => !["DA_CAP", "TU_CHOI", "CAN_BO_SUNG"].includes(String(d.trang_thai)));
});

const dsCanBoSung = computed(() => ds.value.filter((d) => d.trang_thai === "CAN_BO_SUNG").slice(0, 3));
const tongQuan = computed(() => [
  { key: "tat-ca" as Loc, nhan: "Tổng hồ sơ", so: ds.value.length, lop: "tt tt-lam" },
  { key: "dang-xu-ly" as Loc, nhan: "Đang xử lý", so: dangXuLy.value, lop: "tt tt-lam" },
  { key: "can-bo-sung" as Loc, nhan: "Cần bổ sung", so: canBoSung.value, lop: "tt tt-vang" },
  { key: "da-cap" as Loc, nhan: "Đã cấp", so: daCap.value, lop: "tt tt-xanh" },
]);

function viTriBuoc(d: HoSo): number {
  if (d.trang_thai === "DA_CAP" || d.trang_thai === "TU_CHOI") return TIEN_TRINH.length;
  const i = TIEN_TRINH.indexOf(String(d.buoc || ""));
  return i < 0 ? 0 : i;
}

function phanTramBuoc(d: HoSo): number {
  if (d.trang_thai === "DA_CAP" || d.trang_thai === "TU_CHOI") return 100;
  return Math.round(((viTriBuoc(d) + 1) / TIEN_TRINH.length) * 100);
}

function lopTienTrinh(d: HoSo): string {
  if (d.trang_thai === "TU_CHOI") return "bg-son";
  if (d.trang_thai === "CAN_BO_SUNG") return "bg-vang";
  if (d.trang_thai === "DA_CAP") return "bg-xanh";
  return "bg-cham";
}

function buocHienTai(d: HoSo): string {
  if (d.trang_thai === "DA_CAP") return "Đã cấp giấy phép";
  if (d.trang_thai === "TU_CHOI") return "Hồ sơ bị từ chối";
  return `Bước ${Math.min(viTriBuoc(d) + 1, TIEN_TRINH.length)}/${TIEN_TRINH.length}: ${tenBuoc(d.buoc)}`;
}

function hanText(d: HoSo): string {
  const value = d.han_tong_at || d.han_buoc_at;
  if (!value) return "Chưa có hạn xử lý";
  const t = new Date(value).getTime();
  if (!Number.isFinite(t)) return "Hạn không hợp lệ";
  if (d.trang_thai === "DA_CAP" || d.trang_thai === "TU_CHOI") return `Hạn: ${ngayNgan(value)}`;
  const conLai = Math.ceil((t - Date.now()) / 86_400_000);
  if (conLai < 0) return `Quá hạn ${-conLai} ngày`;
  if (conLai === 0) return "Hết hạn hôm nay";
  return `Còn ${conLai} ngày`;
}

function hanGap(d: HoSo): boolean {
  if (d.trang_thai === "DA_CAP" || d.trang_thai === "TU_CHOI") return false;
  const value = d.han_tong_at || d.han_buoc_at;
  if (!value) return false;
  const conLai = new Date(value).getTime() - Date.now();
  return conLai < 2 * 86_400_000;
}

async function taiKetQua(d: HoSo): Promise<void> {
  if (dangTaiKetQua.value) return;
  dangTaiKetQua.value = d.id;
  try {
    const token = await getValidToken();
    if (!token) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    const info = await layGiayPhep(token, d);
    if (!info?.file_url) {
      notify("Giấy phép chưa có tệp để tải. Vui lòng thử lại sau.", "canh_bao");
      return;
    }
    const url0 = String(info.file_url);
    const duongDan = url0.startsWith(`${API_BASE}/`) ? url0.slice(API_BASE.length) : url0;
    const blob = await downloadFile(token, duongDan);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${info.so_giay_phep || d.ma_ho_so}.pdf`;
    a.click();
    setTimeout(() => window.URL.revokeObjectURL(url), 5000);
    notify("Đã tải giấy phép", "ok");
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tải được giấy phép", "loi");
  } finally {
    dangTaiKetQua.value = null;
  }
}

async function layGiayPhep(token: string, d: HoSo): Promise<any> {
  if (cacheGiayPhep.has(d.id)) return cacheGiayPhep.get(d.id);
  const info = await fetchPermitInfo(token, d.id);
  if (info) cacheGiayPhep.set(d.id, info);
  return info;
}

async function moQr(d: HoSo): Promise<void> {
  if (dangTaiKetQua.value) return;
  dangTaiKetQua.value = d.id;
  try {
    const token = await getValidToken();
    if (!token) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    const info = await layGiayPhep(token, d);
    if (!info?.ma_cong_khai) {
      notify("Giấy phép chưa có mã tra cứu công khai.", "canh_bao");
      return;
    }
    const url = new URL(`/kiem-tra/${encodeURIComponent(info.ma_cong_khai)}`, window.location.origin).toString();
    qr.value = { url, ma: info.ma_cong_khai, tieuDe: `QR tra cứu ${d.ma_ho_so}` };
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không mở được QR tra cứu", "loi");
  } finally {
    dangTaiKetQua.value = null;
  }
}

function moChiTiet(d: HoSo): void {
  void moHoSo(d.id, d.ma_ho_so);
}

function boSung(d: HoSo): void {
  moBoSung(d);
}

onMounted(() => {
  if (!cd.dossiers.value.length && !cd.dangTai.value) void cd.taiHoSo();
});
</script>

<template>
  <section id="tu-phuc-vu" aria-labelledby="tieu-de-tu-phuc-vu">
    <div class="mb-4 flex flex-wrap items-end gap-3">
      <div class="min-w-0">
        <h1 id="tieu-de-tu-phuc-vu" class="tieu-de-trang">Tự phục vụ</h1>
        <p class="mt-2 max-w-3xl text-[16px] text-phu">
          Theo dõi tiến độ, bổ sung hồ sơ, tải giấy phép và tra cứu bằng QR mà không cần gọi cán bộ.
        </p>
      </div>
      <div class="flex-1"></div>
      <button type="button" class="btn" :disabled="cd.dangTai.value" @click="cd.taiHoSo()">
        {{ cd.dangTai.value ? "Đang tải…" : "Làm mới" }}
      </button>
    </div>

    <div v-if="cd.dangTai.value && !ds.length" class="the p-3" role="status" aria-busy="true">
      <p class="m-0 py-6 text-center text-[13px] text-phu">Đang tải hồ sơ…</p>
    </div>

    <div v-else-if="cd.loi.value" class="thong-bao-loi mb-4" role="alert">
      <p class="m-0">{{ cd.loi.value }}</p>
      <button type="button" class="btn btn-sm mt-2" @click="cd.taiHoSo()">Thử lại</button>
    </div>

    <template v-else>
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Tổng quan hồ sơ">
        <button
          v-for="m in tongQuan"
          :key="m.key"
          type="button"
          class="the p-4 text-left transition"
          :class="loc === m.key ? 'ring-1 ring-[rgb(var(--c-cham))]' : 'hover:bg-mat-2'"
          :aria-pressed="loc === m.key"
          @click="loc = m.key"
        >
          <span class="text-[12.5px] text-phu">{{ m.nhan }}</span>
          <span class="mt-2 flex items-center justify-between gap-2">
            <b class="text-[30px] font-semibold leading-none">{{ m.so }}</b>
            <span :class="m.lop">Hồ sơ</span>
          </span>
        </button>
      </div>

      <section v-if="dsCanBoSung.length" class="mt-4 the p-4" aria-labelledby="tu-phuc-vu-bo-sung">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 id="tu-phuc-vu-bo-sung" class="m-0 text-[14px] font-semibold">Cần bạn bổ sung</h2>
            <p class="m-0 mt-1 text-[12.5px] text-phu">Bổ sung sớm để hồ sơ không bị quá hạn.</p>
          </div>
          <span class="tt tt-vang">{{ canBoSung }}</span>
        </div>
        <ul class="m-0 mt-3 list-none space-y-2 p-0">
          <li v-for="d in dsCanBoSung" :key="d.id" class="rounded-[14px] border border-vien-nhat p-3">
            <div class="flex flex-wrap items-start justify-between gap-2">
              <div class="min-w-0">
                <b class="ma">{{ d.ma_ho_so }}</b>
                <p class="m-0 mt-1 text-[13px]">{{ d.ly_do_bo_sung || "Cán bộ yêu cầu bổ sung hồ sơ." }}</p>
                <p class="m-0 mt-1 text-[12px]" :class="hanGap(d) ? 'text-son' : 'text-phu'">{{ hanText(d) }}</p>
              </div>
              <button type="button" class="btn btn-sm btn-chinh" @click="boSung(d)">Bổ sung ngay</button>
            </div>
          </li>
        </ul>
      </section>

      <div v-if="!ds.length" class="the mt-4 p-8 text-center">
        <h2 class="m-0 text-[16px] font-semibold">Bạn chưa có hồ sơ nào</h2>
        <p class="mt-2 text-[13px] text-phu">Nộp hồ sơ đầu tiên để theo dõi tiến độ tại đây.</p>
        <button type="button" class="btn btn-chinh mt-3" @click="moNopHoSo()">Nộp hồ sơ mới</button>
      </div>

      <div v-else-if="!dsLoc.length" class="the mt-4 p-6 text-center text-[13px] text-phu">
        Không có hồ sơ ở nhóm này.
      </div>

      <ul v-else class="mt-4 space-y-3">
        <li v-for="d in dsLoc" :key="d.id" class="the p-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <b class="ma text-[15px]">{{ d.ma_ho_so }}</b>
                <span :class="getStatusBadgeClass(d.trang_thai)">{{ formatStatus(d.trang_thai) }}</span>
                <span v-if="d.qua_han" class="tt tt-do">Quá hạn</span>
              </div>
              <p class="m-0 mt-1 text-[13px] text-phu">{{ d.ho_ten }} · {{ d.dia_chi_cong_trinh }}</p>
              <p class="m-0 mt-1 text-[12px] text-phu">
                Cập nhật: {{ ngayGio(d.updated_at || d.created_at) }} · {{ d.so_tang || "—" }} tầng · {{ formatNumberVi(d.dien_tich_san_m2) }} m²
              </p>
            </div>
            <div class="text-right">
              <p class="m-0 text-[13px] font-medium" :class="hanGap(d) ? 'text-son' : 'text-phu'">{{ hanText(d) }}</p>
              <p class="m-0 mt-0.5 text-[12px] text-phu">{{ buocHienTai(d) }}</p>
            </div>
          </div>

          <div class="mt-3">
            <div class="h-1.5 overflow-hidden rounded-full bg-mat-2">
              <span class="block h-full rounded-full transition-all" :class="lopTienTrinh(d)" :style="{ width: `${phanTramBuoc(d)}%` }"></span>
            </div>
            <div class="mt-1 flex justify-between text-[11px] text-phu">
              <span>{{ tenBuoc("tiep_nhan") }}</span>
              <span>{{ tenBuoc("hoan_thanh") }}</span>
            </div>
          </div>

          <p v-if="d.trang_thai === 'CAN_BO_SUNG'" class="thong-bao-vang mt-3 text-[12.5px]">
            <b>Yêu cầu bổ sung:</b> {{ d.ly_do_bo_sung || "Xem chi tiết để biết nội dung cần bổ sung." }}
          </p>

          <div class="mt-3 flex flex-wrap gap-2">
            <button type="button" class="btn btn-sm" @click="moChiTiet(d)">Xem chi tiết</button>
            <button v-if="d.trang_thai === 'CAN_BO_SUNG'" type="button" class="btn btn-sm btn-chinh" @click="boSung(d)">Bổ sung hồ sơ</button>
            <button
              v-if="d.trang_thai === 'DA_CAP'"
              type="button"
              class="btn btn-sm"
              :disabled="dangTaiKetQua === d.id"
              @click="taiKetQua(d)"
            >
              {{ dangTaiKetQua === d.id ? "Đang tải…" : "Tải giấy phép" }}
            </button>
            <button
              v-if="d.trang_thai === 'DA_CAP'"
              type="button"
              class="btn btn-sm"
              :disabled="dangTaiKetQua === d.id"
              @click="moQr(d)"
            >
              QR tra cứu
            </button>
          </div>
        </li>
      </ul>
    </template>

    <QrCodeModal
      v-if="qr"
      :url="qr.url"
      :ma="qr.ma"
      :tieu-de="qr.tieuDe"
      @close="qr = null"
    />
  </section>
</template>

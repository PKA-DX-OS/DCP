<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  fetchMdmCandidates,
  fetchMdmEntity,
  fetchMdmSearch,
  mergeMdmEntities,
  undoMdmMerge,
  type KetQuaGop,
  type LoaiThucThe,
  type ThucTheChiTiet,
  type ThucTheTomTat,
  type UngVienTrung,
} from "../../api/mdm";
import { formatThoiDiem } from "../../utils/metrics";

const props = defineProps<{ vaiTro: string[] }>();

const VAI_GOP = ["dx:tenant-admin", "dx:data-steward"];
const coTheGop = computed(() => props.vaiTro.some((r) => VAI_GOP.includes(r)));

const LOAI: Array<{ value: LoaiThucThe; label: string }> = [
  { value: "subject", label: "Công dân / chủ đầu tư" },
  { value: "parcel", label: "Thửa đất" },
  { value: "construction", label: "Công trình" },
  { value: "permit", label: "Giấy phép" },
  { value: "organization", label: "Tổ chức" },
];

const NHAN_LY_DO: Record<string, string> = {
  cccd: "CCCD",
  ho_ten: "Họ tên",
  dien_thoai: "Điện thoại",
  dia_chi: "Địa chỉ",
  thua_dat: "Thửa đất",
  ma_cong_trinh: "Mã công trình",
};

const NHAN_THUOC_TINH: Record<string, string> = {
  ma_cong_trinh: "Mã công trình",
  dia_chi_chuan: "Địa chỉ chuẩn",
  so_thua: "Số thửa",
  to_ban_do: "Tờ bản đồ",
  ma_dinh_danh_dia_diem: "Mã định danh địa điểm",
  dien_tich_m2: "Diện tích (m²)",
  ten: "Tên",
  mst: "Mã số thuế",
  so_giay_phep: "Số giấy phép",
  trang_thai: "Trạng thái",
  ngay_cap: "Ngày cấp",
  source: "Nguồn",
  created_at: "Tạo lúc",
  updated_at: "Cập nhật",
};

const loai = ref<LoaiThucThe>("subject");
const tuKhoa = ref("");
const trang = ref(1);
const tong = ref(0);
const pageSize = 10;
const ketQua = ref<ThucTheTomTat[]>([]);
const daTim = ref(false);
const dangTim = ref(false);
const loiTim = ref("");

const chon = ref<ThucTheTomTat | null>(null);
const chiTiet = ref<ThucTheChiTiet | null>(null);
const ungVien = ref<UngVienTrung[]>([]);
const dangTaiChiTiet = ref(false);
const loiChiTiet = ref("");

const gopVoi = ref<string | null>(null);
const lyDo = reactive<Record<string, string>>({});
const dangGop = ref(false);
const ketQuaGop = ref<KetQuaGop | null>(null);
const dangHoanTac = ref(false);
const thongBao = ref("");

const soTrang = computed(() => Math.max(1, Math.ceil(tong.value / pageSize)));

const danhSachThuocTinh = computed(() => {
  const t = chiTiet.value?.thuoc_tinh || {};
  return Object.entries(NHAN_THUOC_TINH)
    .filter(([k]) => t[k] !== undefined && t[k] !== null && t[k] !== "")
    .map(([k, nhan]) => ({
      nhan,
      giaTri: k === "created_at" || k === "updated_at" || k === "ngay_cap" ? ngay(String(t[k])) : String(t[k]),
    }));
});

const ungVienDangGop = computed(() =>
  ungVien.value.find((u) => u.ung_vien.id === gopVoi.value) || null,
);

function tenLoai(v: string): string {
  return LOAI.find((x) => x.value === v)?.label || v;
}

function tenLyDo(v: string): string {
  return NHAN_LY_DO[v] || v;
}

function phanTram(v: number): string {
  return Number(v * 100).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + "%";
}

function ngay(iso: string | null): string {
  return iso ? formatThoiDiem(iso) : "—";
}

function datLaiChiTiet(): void {
  chon.value = null;
  chiTiet.value = null;
  ungVien.value = [];
  gopVoi.value = null;
  ketQuaGop.value = null;
  thongBao.value = "";
}

async function tim(trangMoi = 1): Promise<void> {
  const q = tuKhoa.value.trim();
  if (q.length < 2) {
    loiTim.value = "Nhập ít nhất 2 ký tự để tìm.";
    return;
  }
  dangTim.value = true;
  loiTim.value = "";
  try {
    const r = await fetchMdmSearch(loai.value, q, trangMoi, pageSize);
    ketQua.value = r.items;
    tong.value = r.total;
    trang.value = r.page;
    daTim.value = true;
    datLaiChiTiet();
  } catch (e) {
    loiTim.value = e instanceof Error ? e.message : "Không tìm được thực thể";
  } finally {
    dangTim.value = false;
  }
}

async function moThucThe(t: ThucTheTomTat): Promise<void> {
  chon.value = t;
  chiTiet.value = null;
  ungVien.value = [];
  gopVoi.value = null;
  ketQuaGop.value = null;
  thongBao.value = "";
  loiChiTiet.value = "";
  dangTaiChiTiet.value = true;
  try {
    const [ct, uv] = await Promise.all([fetchMdmEntity(loai.value, t.id), fetchMdmCandidates(loai.value, t.id)]);
    chiTiet.value = ct;
    ungVien.value = uv;
  } catch (e) {
    loiChiTiet.value = e instanceof Error ? e.message : "Không tải được chi tiết thực thể";
  } finally {
    dangTaiChiTiet.value = false;
  }
}

async function taiLaiChiTiet(): Promise<void> {
  if (!chon.value) return;
  try {
    const [ct, uv] = await Promise.all([
      fetchMdmEntity(loai.value, chon.value.id),
      fetchMdmCandidates(loai.value, chon.value.id),
    ]);
    chiTiet.value = ct;
    ungVien.value = uv;
  } catch (e) {
    loiChiTiet.value = e instanceof Error ? e.message : "Không tải lại được chi tiết thực thể";
  }
}

function batDauGop(id: string): void {
  gopVoi.value = gopVoi.value === id ? null : id;
  thongBao.value = "";
}

async function xacNhanGop(): Promise<void> {
  const uv = ungVienDangGop.value;
  if (!uv || !chon.value || !chiTiet.value) return;
  const reason = (lyDo[uv.ung_vien.id] || "").trim();
  if (reason.length < 5) {
    thongBao.value = "Nhập lý do gộp ít nhất 5 ký tự.";
    return;
  }
  dangGop.value = true;
  thongBao.value = "";
  try {
    ketQuaGop.value = await mergeMdmEntities({
      entity_type: loai.value,
      giu_id: chon.value.id,
      gop_ids: [uv.ung_vien.id],
      ly_do: reason,
    });
    thongBao.value = `Đã gộp “${uv.ung_vien.nhan}” vào bản ghi đang xem và ghi audit.`;
    gopVoi.value = null;
    delete lyDo[uv.ung_vien.id];
    await taiLaiChiTiet();
  } catch (e) {
    thongBao.value = e instanceof Error ? e.message : "Không gộp được bản ghi";
  } finally {
    dangGop.value = false;
  }
}

async function hoanTac(): Promise<void> {
  if (!ketQuaGop.value) return;
  dangHoanTac.value = true;
  thongBao.value = "";
  try {
    await undoMdmMerge(ketQuaGop.value.merge_id);
    thongBao.value = "Đã hoàn tác lần gộp và ghi audit.";
    ketQuaGop.value = null;
    await taiLaiChiTiet();
  } catch (e) {
    thongBao.value = e instanceof Error ? e.message : "Không hoàn tác được lần gộp";
  } finally {
    dangHoanTac.value = false;
  }
}

watch(loai, () => {
  datLaiChiTiet();
  ketQua.value = [];
  tong.value = 0;
  daTim.value = false;
  loiTim.value = "";
});
</script>

<template>
  <section class="space-y-4" aria-labelledby="tieu-de-mdm">
    <div class="mb-2">
      <h1 id="tieu-de-mdm" class="tieu-de-trang">Dữ liệu chủ (MDM)</h1>
      <p class="mt-2 max-w-3xl text-[15px] text-phu">
        Tìm thực thể, xem hồ sơ liên kết và ứng viên trùng. Người quản lý dữ liệu có thể gộp bản ghi trùng
        và hoàn tác; mọi thay đổi đều ghi audit.
      </p>
    </div>

    <form class="the p-4" @submit.prevent="tim(1)">
      <div class="flex flex-wrap items-end gap-3">
        <label class="flex flex-col gap-1 text-[12.5px] text-phu">
          Loại thực thể
          <select v-model="loai" class="o w-auto">
            <option v-for="l in LOAI" :key="l.value" :value="l.value">{{ l.label }}</option>
          </select>
        </label>
        <label class="flex min-w-[240px] flex-1 flex-col gap-1 text-[12.5px] text-phu">
          Từ khóa
          <input
            v-model="tuKhoa"
            class="o w-full"
            maxlength="100"
            :placeholder="loai === 'subject' ? 'Ví dụ: Nguyễn Văn An' : loai === 'construction' ? 'Ví dụ: CT-01' : 'Nhập mã hoặc tên'"
          />
        </label>
        <button type="submit" class="btn btn-chinh" :disabled="dangTim">
          {{ dangTim ? "Đang tìm…" : "Tìm" }}
        </button>
      </div>
      <p class="m-0 mt-2 text-[11.5px] text-phu">
        Tìm theo tên hoặc mã không nhạy cảm. Không nhập CCCD, số điện thoại hay địa chỉ đầy đủ.
      </p>
    </form>

    <div v-if="loiTim" class="the p-4" role="alert">
      <p class="m-0 text-son">{{ loiTim }}</p>
    </div>

    <div v-if="dangTim" class="the p-4" role="status" aria-busy="true">Đang tìm thực thể…</div>

    <template v-else-if="daTim">
      <div class="the overflow-hidden">
        <div class="flex flex-wrap items-center justify-between gap-2 border-b border-vien-nhat p-4">
          <h2 class="m-0 text-[15px] font-semibold">Kết quả</h2>
          <span class="mo">{{ tong }} thực thể</span>
        </div>
        <table class="bang w-full text-[12.5px]">
          <thead>
            <tr>
              <th scope="col">Thực thể</th>
              <th scope="col">Mã</th>
              <th scope="col">Độ tin cậy</th>
              <th scope="col" class="text-right">Chi tiết</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in ketQua" :key="t.id" :class="chon?.id === t.id && 'bg-mat-2'">
              <td>
                <b class="font-medium">{{ t.nhan }}</b>
                <span class="block text-[11px] text-phu">
                  {{ tenLoai(t.type) }} · <code :title="t.id">{{ t.id.slice(0, 8) }}…</code>
                </span>
              </td>
              <td class="whitespace-nowrap">{{ t.ma || "—" }}</td>
              <td class="whitespace-nowrap">{{ phanTram(t.confidence) }}</td>
              <td class="text-right">
                <button type="button" class="btn btn-sm" @click="moThucThe(t)">Xem</button>
              </td>
            </tr>
            <tr v-if="!ketQua.length">
              <td colspan="4" class="py-6 text-center text-phu">Không tìm thấy thực thể khớp từ khóa.</td>
            </tr>
          </tbody>
        </table>
        <div v-if="soTrang > 1" class="flex items-center justify-between border-t border-vien-nhat p-3">
          <button type="button" class="btn btn-sm" :disabled="trang <= 1 || dangTim" @click="tim(trang - 1)">Trước</button>
          <span class="mo">Trang {{ trang }}/{{ soTrang }}</span>
          <button type="button" class="btn btn-sm" :disabled="trang >= soTrang || dangTim" @click="tim(trang + 1)">Sau</button>
        </div>
      </div>
    </template>

    <div v-if="thongBao" class="the p-3" :class="thongBao.startsWith('Đã') ? 'text-xanh' : 'text-son'" role="status">
      {{ thongBao }}
    </div>

    <div v-if="dangTaiChiTiet" class="the p-4" role="status" aria-busy="true">Đang tải chi tiết thực thể…</div>
    <div v-else-if="loiChiTiet" class="the p-4" role="alert">
      <p class="m-0 text-son">{{ loiChiTiet }}</p>
      <button type="button" class="btn btn-sm mt-3" @click="taiLaiChiTiet">Thử lại</button>
    </div>

    <template v-else-if="chiTiet">
      <div class="the p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 class="m-0 text-[16px] font-semibold">{{ chiTiet.nhan }}</h2>
            <p class="m-0 mt-1 text-[12.5px] text-phu">
              {{ tenLoai(chiTiet.type) }} · {{ chiTiet.ma || "không có mã" }} · độ tin cậy {{ phanTram(chiTiet.confidence) }}
            </p>
          </div>
          <span v-if="chiTiet.merged_into" class="tt tt-do">Đã được gộp</span>
          <span v-else class="tt tt-xanh">Bản ghi đang hoạt động</span>
        </div>

        <p v-if="chiTiet.merged_into" class="mt-3 mb-0 rounded-[12px] bg-mat-2 p-3 text-[12.5px] text-son">
          Bản ghi này đã được gộp vào một bản ghi khác. Không thể gộp tiếp; hãy mở bản ghi gốc nếu cần.
        </p>

        <dl class="ds-thong-tin mt-3">
          <template v-for="t in danhSachThuocTinh" :key="t.nhan">
            <dt>{{ t.nhan }}</dt><dd>{{ t.giaTri }}</dd>
          </template>
        </dl>
        <p v-if="!danhSachThuocTinh.length" class="mt-3 mb-0 text-[12.5px] text-phu">Không có thuộc tính hiển thị.</p>

        <h3 class="mt-4 mb-1 text-[13px] font-semibold">Hồ sơ liên kết</h3>
        <p v-if="!chiTiet.ho_so.length" class="m-0 text-[12.5px] text-phu">Chưa có hồ sơ liên kết.</p>
        <div v-else class="overflow-x-auto" tabindex="0" role="region" aria-label="Hồ sơ liên kết của thực thể">
          <table class="bang w-full text-[12.5px]">
            <thead><tr><th scope="col">Mã hồ sơ</th><th scope="col">Trạng thái</th></tr></thead>
            <tbody>
              <tr v-for="h in chiTiet.ho_so" :key="h.dossier_id">
                <td class="whitespace-nowrap font-medium">{{ h.ma_ho_so }}</td>
                <td class="whitespace-nowrap">{{ h.trang_thai }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <template v-if="chiTiet.external_refs.length">
          <h3 class="mt-4 mb-1 text-[13px] font-semibold">Tham chiếu hệ thống ngoài</h3>
          <ul class="m-0 list-none space-y-1 p-0 text-[12.5px] text-phu">
            <li v-for="r in chiTiet.external_refs" :key="`${r.system}-${r.external_id}`">
              {{ r.system }} · {{ r.external_id }} · {{ phanTram(r.confidence) }} · đồng bộ {{ ngay(r.last_synced_at) }}
            </li>
          </ul>
        </template>
      </div>

      <div class="the p-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 class="m-0 text-[15px] font-semibold">Ứng viên trùng</h2>
            <p class="m-0 mt-1 text-[12px] text-phu">Dưới ngưỡng tự liên kết, cần người xét.</p>
          </div>
          <span class="tt tt-vang">{{ ungVien.length }}</span>
        </div>

        <p v-if="!ungVien.length" class="mt-3 mb-0 text-[13px] text-phu">Không có ứng viên trùng đang mở.</p>
        <div v-else class="mt-3 overflow-x-auto" tabindex="0" role="region" aria-label="Ứng viên trùng của thực thể">
          <table class="bang w-full text-[12.5px]">
            <thead>
              <tr>
                <th scope="col">Ứng viên</th>
                <th scope="col">Độ tin cậy</th>
                <th scope="col">Trùng ở</th>
                <th v-if="coTheGop" scope="col" class="text-right">Xử lý</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in ungVien" :key="u.ung_vien.id">
                <td>
                  <b class="font-medium">{{ u.ung_vien.nhan }}</b>
                  <span class="block text-[11px] text-phu">{{ u.ung_vien.ma || "không có mã" }}</span>
                </td>
                <td class="whitespace-nowrap">{{ phanTram(u.confidence) }}</td>
                <td>
                  <span v-for="l in u.ly_do" :key="l" class="tt tt-xam mr-1">{{ tenLyDo(l) }}</span>
                </td>
                <td v-if="coTheGop" class="text-right">
                  <button type="button" class="btn btn-sm" :disabled="!!chiTiet.merged_into || dangGop" @click="batDauGop(u.ung_vien.id)">
                    {{ gopVoi === u.ung_vien.id ? "Hủy" : "Gộp" }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="coTheGop && ungVienDangGop" class="mt-3 rounded-[14px] border border-vien-nhat bg-mat-2 p-3" role="region" aria-label="Xác nhận gộp bản ghi">
          <p class="m-0 text-[12.5px]">
            Gộp <b>{{ ungVienDangGop.ung_vien.nhan }}</b> vào <b>{{ chiTiet.nhan }}</b>. Bản ghi bị gộp sẽ
            trỏ về bản ghi này và có thể hoàn tác.
          </p>
          <label class="mt-2 block">
            <span class="nhan">Lý do gộp (bắt buộc, ít nhất 5 ký tự)</span>
            <input v-model="lyDo[ungVienDangGop.ung_vien.id]" class="o w-full" maxlength="500" placeholder="Ví dụ: cùng một chủ đầu tư, trùng số điện thoại" />
          </label>
          <div class="mt-2 flex flex-wrap gap-2">
            <button type="button" class="btn btn-sm btn-chinh" :disabled="dangGop" @click="xacNhanGop">
              {{ dangGop ? "Đang gộp…" : "Xác nhận gộp" }}
            </button>
            <button type="button" class="btn btn-sm" :disabled="dangGop" @click="gopVoi = null">Hủy</button>
          </div>
        </div>

        <div v-if="ketQuaGop" class="mt-3 flex flex-wrap items-center gap-3 rounded-[14px] border border-vien-nhat p-3 text-[12.5px]">
          <span>Lần gộp <code>{{ ketQuaGop.merge_id.slice(0, 8) }}…</code> lúc {{ ngay(ketQuaGop.thuc_hien_luc) }}.</span>
          <button type="button" class="btn btn-sm" :disabled="dangHoanTac" @click="hoanTac">
            {{ dangHoanTac ? "Đang hoàn tác…" : "Hoàn tác lần gộp" }}
          </button>
        </div>
      </div>
    </template>
  </section>
</template>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { fetchDossier360, type HoSo360 } from "../api/dh";
import { cheCccd, ngayGio, ngayNgan, tenBuoc } from "../utils/labels";
import { formatNumberVi, formatStatus } from "../utils/formatters";

const props = defineProps<{
  dossier: any;
  token: string;
}>();

const duLieu = ref<HoSo360 | null>(null);
const nguon = ref<"api" | "ho-so">("ho-so");
const loading = ref(false);
let lanTai = 0;

function tenKetQua(value: string): string {
  return { dat: "Đạt", khong_dat: "Không đạt", cho_xu_ly: "Chờ xử lý" }[value] || value || "—";
}
function lopKetQua(value: string): string {
  if (value === "dat") return "tt tt-xanh";
  if (value === "khong_dat") return "tt tt-do";
  return "tt tt-vang";
}
function tenLoaiKiemTra(value: string): string {
  return {
    quy_hoach: "Quy hoạch",
    thiet_ke: "Thiết kế",
    nghiem_thu: "Nghiệm thu",
    hien_truong: "Hiện trường",
  }[value] || value || "—";
}
function tenNguonCanhBao(value: string): string {
  return { dq: "Chất lượng dữ liệu", mdm: "Liên kết dữ liệu" }[value] || value || "Cảnh báo";
}
function tenTrangThaiGiayPhep(value: string): string {
  return { valid: "Hợp lệ", revoked: "Đã thu hồi", expired: "Hết hiệu lực" }[value] || value || "—";
}
function tenTrangThaiTaiChinh(value: string): string {
  return { chua_thu: "Chưa thu", da_thu: "Đã thu", mien: "Miễn" }[value] || value || "—";
}

async function tai(): Promise<void> {
  if (!props.token || !props.dossier?.id) return;
  const lan = ++lanTai;
  loading.value = true;
  try {
    const data = await fetchDossier360(props.token, props.dossier.id);
    if (lan !== lanTai) return;
    duLieu.value = data;
    nguon.value = data ? "api" : "ho-so";
  } finally {
    if (lan === lanTai) loading.value = false;
  }
}

onMounted(tai);
watch(
  () => props.dossier?.id,
  (moi, cu) => {
    if (moi && moi !== cu) {
      duLieu.value = null;
      nguon.value = "ho-so";
      void tai();
    }
  },
);
</script>

<template>
  <section id="block-dossier-360" class="mt-5" aria-labelledby="tieu-de-360">
    <div class="mb-2 flex flex-wrap items-baseline justify-between gap-2">
      <div>
        <h3 id="tieu-de-360" class="text-[14px] font-semibold m-0">Tổng hợp 360 hồ sơ</h3>
        <p class="m-0 mt-1 text-[12.5px] text-phu">
          Chủ đầu tư, thửa đất, công trình, giấy phép, kiểm tra, tài chính và nhật ký trong một chỗ.
        </p>
      </div>
      <span class="tt" :class="nguon === 'api' ? 'tt-xanh' : 'tt-vang'">
        {{ nguon === "api" ? "Dữ liệu MDM" : "Từ hồ sơ hiện tại" }}
      </span>
    </div>

    <p v-if="loading" class="text-phu m-0" role="status">Đang tải dữ liệu 360…</p>

    <template v-else-if="duLieu">
      <div class="grid gap-3 lg:grid-cols-2">
        <section class="the p-3" aria-labelledby="360-chu-dau-tu">
          <h4 id="360-chu-dau-tu" class="text-[13px] font-semibold m-0">Chủ đầu tư</h4>
          <dl v-if="duLieu.chu_dau_tu" class="ds-thong-tin mt-2">
            <dt>Họ tên</dt><dd>{{ duLieu.chu_dau_tu.ho_ten }}</dd>
            <dt>CCCD</dt><dd>{{ duLieu.chu_dau_tu.cccd_mask }}</dd>
            <dt>Điện thoại</dt><dd>{{ duLieu.chu_dau_tu.dien_thoai_mask || "—" }}</dd>
            <dt>Hồ sơ khác</dt><dd>{{ duLieu.chu_dau_tu.so_ho_so_khac ?? 0 }}</dd>
          </dl>
          <p v-else class="mt-2 mb-0 text-[12.5px] text-phu">Chưa liên kết chủ đầu tư.</p>
        </section>

        <section class="the p-3" aria-labelledby="360-thua-dat">
          <h4 id="360-thua-dat" class="text-[13px] font-semibold m-0">Thửa đất</h4>
          <dl v-if="duLieu.thua_dat" class="ds-thong-tin mt-2">
            <dt>Số thửa / tờ</dt><dd>{{ duLieu.thua_dat.so_thua || "—" }} / {{ duLieu.thua_dat.to_ban_do || "—" }}</dd>
            <dt>Mã địa điểm</dt><dd>{{ duLieu.thua_dat.ma_dinh_danh_dia_diem || "Chưa có" }}</dd>
            <dt>Diện tích</dt><dd>{{ duLieu.thua_dat.dien_tich_m2 ? `${formatNumberVi(duLieu.thua_dat.dien_tich_m2)} m²` : "—" }}</dd>
          </dl>
          <p v-else class="mt-2 mb-0 text-[12.5px] text-phu">Chưa liên kết thửa đất.</p>
        </section>

        <section class="the p-3" aria-labelledby="360-cong-trinh">
          <h4 id="360-cong-trinh" class="text-[13px] font-semibold m-0">Công trình</h4>
          <dl v-if="duLieu.cong_trinh" class="ds-thong-tin mt-2">
            <dt>Mã công trình</dt><dd>{{ duLieu.cong_trinh.ma_cong_trinh }}</dd>
            <dt>Địa chỉ</dt><dd>{{ duLieu.cong_trinh.dia_chi || "—" }}</dd>
          </dl>
          <p v-else class="mt-2 mb-0 text-[12.5px] text-phu">Chưa liên kết công trình.</p>
        </section>

        <section class="the p-3" aria-labelledby="360-giay-phep">
          <h4 id="360-giay-phep" class="text-[13px] font-semibold m-0">Giấy phép</h4>
          <dl v-if="duLieu.giay_phep" class="ds-thong-tin mt-2">
            <dt>Số giấy phép</dt><dd>{{ duLieu.giay_phep.so_giay_phep }}</dd>
            <dt>Trạng thái</dt><dd>{{ tenTrangThaiGiayPhep(duLieu.giay_phep.trang_thai) }}</dd>
            <dt>Ngày cấp</dt><dd>{{ ngayNgan(duLieu.giay_phep.ngay_cap) }}</dd>
            <dt>Mã tra cứu</dt>
            <dd>
              <a
                v-if="duLieu.giay_phep.public_code"
                :href="'/kiem-tra/' + duLieu.giay_phep.public_code"
                target="_blank"
                rel="noopener"
                class="btn-lien-ket break-all"
              >{{ duLieu.giay_phep.public_code }}</a>
              <span v-else>—</span>
            </dd>
          </dl>
          <p v-else class="mt-2 mb-0 text-[12.5px] text-phu">Chưa có giấy phép.</p>
        </section>
      </div>

      <div v-if="duLieu.canh_bao?.length" class="mt-3 rounded-[14px] border border-vien-nhat bg-mat-2 p-3">
        <h4 class="m-0 text-[13px] font-semibold">Cảnh báo dữ liệu ({{ duLieu.canh_bao.length }})</h4>
        <ul class="m-0 mt-2 list-none space-y-1.5 p-0 text-[12.5px]">
          <li v-for="w in duLieu.canh_bao" :key="`${w.code}-${w.field || ''}`" class="flex flex-wrap items-baseline gap-2">
            <span :class="w.severity === 'error' ? 'tt tt-do' : 'tt tt-vang'">{{ tenNguonCanhBao(w.nguon) }}</span>
            <span>{{ w.message }}</span>
            <span v-if="w.field" class="text-phu">· {{ w.field }}</span>
          </li>
        </ul>
      </div>

      <div class="mt-3 grid gap-3 lg:grid-cols-2">
        <section class="the p-3" aria-labelledby="360-kiem-tra">
          <h4 id="360-kiem-tra" class="text-[13px] font-semibold m-0">Kiểm tra</h4>
          <ul v-if="duLieu.kiem_tra?.length" class="m-0 mt-2 list-none space-y-2 p-0 text-[12.5px]">
            <li v-for="(k, i) in duLieu.kiem_tra" :key="i" class="rounded-[12px] border border-vien-nhat p-2">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <b>{{ tenLoaiKiemTra(k.loai) }}</b>
                <span :class="lopKetQua(k.ket_qua)">{{ tenKetQua(k.ket_qua) }}</span>
              </div>
              <p class="m-0 mt-1 text-phu">{{ k.mo_ta || "—" }} · {{ ngayGio(k.thoi_diem) }}</p>
            </li>
          </ul>
          <p v-else class="mt-2 mb-0 text-[12.5px] text-phu">Chưa có kết quả kiểm tra.</p>
        </section>

        <section class="the p-3" aria-labelledby="360-tai-chinh">
          <h4 id="360-tai-chinh" class="text-[13px] font-semibold m-0">Tài chính</h4>
          <ul v-if="duLieu.tai_chinh?.length" class="m-0 mt-2 list-none space-y-2 p-0 text-[12.5px]">
            <li v-for="(t, i) in duLieu.tai_chinh" :key="i" class="flex flex-wrap items-center justify-between gap-2 border-b border-vien-nhat py-1 last:border-0">
              <span>{{ t.loai }}</span>
              <span class="whitespace-nowrap font-medium">{{ formatNumberVi(t.so_tien) }} đ</span>
              <span class="text-phu">{{ tenTrangThaiTaiChinh(t.trang_thai) }}</span>
            </li>
          </ul>
          <p v-else class="mt-2 mb-0 text-[12.5px] text-phu">Chưa có bản ghi tài chính.</p>
          <p class="mt-3 mb-0 text-[12.5px] text-phu">
            Nhật ký: {{ duLieu.audit?.so_su_kien ?? 0 }} sự kiện<template v-if="duLieu.audit?.gan_nhat">, gần nhất {{ ngayGio(duLieu.audit.gan_nhat) }}</template>.
          </p>
        </section>
      </div>
    </template>

    <template v-else>
      <div class="rounded-[14px] border border-vien-nhat bg-mat-2 p-3 text-[12.5px]">
        <p class="m-0 font-medium">API 360 chưa sẵn sàng — đang hiển thị từ hồ sơ hiện tại.</p>
        <p class="m-0 mt-1 text-phu">Khi Track D triển khai MDM, panel này tự chuyển sang dữ liệu 360 đầy đủ.</p>
      </div>

      <div class="mt-3 grid gap-3 lg:grid-cols-2">
        <section class="the p-3">
          <h4 class="text-[13px] font-semibold m-0">Chủ đầu tư</h4>
          <dl class="ds-thong-tin mt-2">
            <dt>Họ tên</dt><dd>{{ dossier.ho_ten || "—" }}</dd>
            <dt>CCCD</dt><dd>{{ cheCccd(dossier.cccd) || "—" }}</dd>
            <dt>Điện thoại</dt><dd>{{ dossier.dien_thoai || "—" }}</dd>
          </dl>
        </section>
        <section class="the p-3">
          <h4 class="text-[13px] font-semibold m-0">Hồ sơ</h4>
          <dl class="ds-thong-tin mt-2">
            <dt>Mã hồ sơ</dt><dd>{{ dossier.ma_ho_so || "—" }}</dd>
            <dt>Trạng thái</dt><dd>{{ formatStatus(dossier.trang_thai || "") || "—" }}</dd>
            <dt>Bước</dt><dd>{{ tenBuoc(dossier.buoc) || "—" }}</dd>
          </dl>
        </section>
        <section class="the p-3">
          <h4 class="text-[13px] font-semibold m-0">Thửa đất / công trình</h4>
          <dl class="ds-thong-tin mt-2">
            <dt>Thửa đất</dt><dd>{{ dossier.thua_dat || "—" }}</dd>
            <dt>Địa chỉ</dt><dd>{{ dossier.dia_chi_cong_trinh || "—" }}</dd>
            <dt>Quy mô</dt><dd>{{ dossier.so_tang || "—" }} tầng, {{ formatNumberVi(dossier.dien_tich_san_m2) }} m²</dd>
          </dl>
        </section>
        <section class="the p-3">
          <h4 class="text-[13px] font-semibold m-0">Liên kết dữ liệu</h4>
          <p class="mt-2 mb-0 text-[12.5px] text-phu">
            Chưa có MDM. Các liên kết chủ đầu tư, thửa đất, công trình, giấy phép sẽ xuất hiện khi API 360 hoạt động.
          </p>
        </section>
      </div>
    </template>
  </section>
</template>

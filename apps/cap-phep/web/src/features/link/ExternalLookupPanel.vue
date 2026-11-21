<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { fetchDossierLinks } from "../../api/mdm";
import { readRoles } from "../../auth";
import { notify } from "../../composables/useToast";
import { Badge, Button, Skeleton } from "../../design-system";
import { NGUON_OPTIONS, giaTriMacDinh, nguonMeta, traCuuMock } from "./adapter";
import type { KetQuaTraCuu, LienKetMDM, NguonLienNganh } from "./types";

const props = defineProps<{
  dossier: any;
  userToken?: string;
  vaiTro?: string[];
}>();

const VAI_XAC_NHAN = [
  "app:cap-phep:mot-cua",
  "app:cap-phep:tham-dinh",
  "app:cap-phep:lanh-dao",
  "app:cap-phep:trat-tu-xd",
];
const vaiTro = computed(() => props.vaiTro ?? readRoles(props.userToken));
const coTheXacNhan = computed(() => vaiTro.value.some((r) => VAI_XAC_NHAN.includes(r)));

const nguon = ref<NguonLienNganh>("dan_cu");
const truyVan = ref(giaTriMacDinh(props.dossier, nguon.value));
const dangTra = ref(false);
const loi = ref("");
const ketQua = ref<KetQuaTraCuu | null>(null);
const daXacNhan = ref<Partial<Record<NguonLienNganh, boolean>>>({});

const lienKet = ref<LienKetMDM | null>(null);
const nguonLienKet = ref<"api" | "khong_co">("khong_co");
const dangTaiLienKet = ref(false);

const soNguonDaXacNhan = computed(() => Object.values(daXacNhan.value).filter(Boolean).length);

interface ThucTheLienKet {
  type: string;
  id: string;
  nhan: string;
  confidence: number;
}

interface LienKetItem {
  nhan: string;
  giaTri: ThucTheLienKet;
}

const lienKetItems = computed<LienKetItem[]>(() => {
  const d = lienKet.value;
  if (!d) return [];
  const ds = [
    { nhan: "Chủ đầu tư", giaTri: d.subject },
    { nhan: "Thửa đất", giaTri: d.parcel },
    { nhan: "Công trình", giaTri: d.construction },
    { nhan: "Giấy phép", giaTri: d.permit },
  ];
  return ds.filter((x): x is LienKetItem => Boolean(x.giaTri));
});

function nhanTrangThai(value: string): string {
  return value === "khop" ? "Khớp hồ sơ" : value === "khong_khop" ? "Không khớp" : "Không tìm thấy";
}

function toneTrangThai(value: string): "success" | "danger" | "warning" {
  return value === "khop" ? "success" : value === "khong_khop" ? "danger" : "warning";
}

function phanTram(value: number): string {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

async function taiLienKet(): Promise<void> {
  if (!props.userToken || !props.dossier?.id) return;
  dangTaiLienKet.value = true;
  try {
    const kq = await fetchDossierLinks(props.userToken, props.dossier.id);
    lienKet.value = kq.data;
    nguonLienKet.value = kq.source;
  } finally {
    dangTaiLienKet.value = false;
  }
}

async function traCuu(): Promise<void> {
  const q = truyVan.value.trim();
  if (!q) {
    loi.value = "Nhập thông tin tra cứu trước khi tra cứu.";
    ketQua.value = null;
    return;
  }
  dangTra.value = true;
  loi.value = "";
  ketQua.value = null;
  try {
    // Mô phỏng độ trễ mạng; adapter là dữ liệu mẫu cục bộ.
    await new Promise((r) => setTimeout(r, 350));
    ketQua.value = traCuuMock(nguon.value, q, props.dossier);
  } finally {
    dangTra.value = false;
  }
}

function xacNhan(): void {
  if (!ketQua.value) return;
  if (ketQua.value.trang_thai === "khong_thay") {
    notify("Không có kết quả để xác nhận", "canh_bao");
    return;
  }
  daXacNhan.value = { ...daXacNhan.value, [nguon.value]: true };
  notify("Đã ghi nhận đối chiếu trên phiên này. Chưa ghi audit thật vì API D chưa sẵn sàng.", "ok");
}

watch(nguon, (moi) => {
  truyVan.value = giaTriMacDinh(props.dossier, moi);
  ketQua.value = null;
  loi.value = "";
});

watch(
  () => props.dossier?.id,
  () => {
    truyVan.value = giaTriMacDinh(props.dossier, nguon.value);
    ketQua.value = null;
    loi.value = "";
    daXacNhan.value = {};
    void taiLienKet();
  },
);

watch(truyVan, () => {
  ketQua.value = null;
  loi.value = "";
  if (daXacNhan.value[nguon.value]) {
    const next = { ...daXacNhan.value };
    delete next[nguon.value];
    daXacNhan.value = next;
  }
});

onMounted(taiLienKet);
</script>

<template>
  <section id="block-dossier-link" class="mt-5" aria-labelledby="tieu-de-lien-nganh">
    <div class="flex flex-wrap items-baseline justify-between gap-2 mb-2">
      <div>
        <h3 id="tieu-de-lien-nganh" class="text-[14px] font-semibold m-0">Đối chiếu liên ngành</h3>
        <p class="goi-y m-0 mt-1">Tra cứu dân cư, đất đai, thuế và PCCC cạnh hồ sơ; cán bộ xác nhận sau khi đối chiếu.</p>
      </div>
      <Badge tone="warning" size="sm">Dữ liệu mẫu</Badge>
    </div>

    <div class="thong-bao-vang mb-3 text-[12.5px]" role="note">
      API liên ngành chưa sẵn sàng. Kết quả dưới đây là dữ liệu mẫu; xác nhận chỉ có hiệu lực trên phiên này và
      <b>chưa ghi audit thật</b>.
    </div>

    <div class="grid gap-3 md:grid-cols-2">
      <div class="the p-3">
        <fieldset class="m-0 border-0 p-0">
          <legend class="nhan">Nguồn dữ liệu</legend>
          <div class="mt-1 grid grid-cols-2 gap-2">
            <label
              v-for="n in NGUON_OPTIONS"
              :key="n.value"
              class="flex cursor-pointer items-center gap-2 rounded-[12px] border border-vien-nhat px-2.5 py-2 text-[13px]"
              :class="nguon === n.value ? 'border-[rgb(var(--c-cham))] bg-mat-2' : ''"
            >
              <input v-model="nguon" type="radio" name="nguon-lien-nganh" :value="n.value" class="h-4 w-4 accent-[rgb(var(--c-cham))]" />
              {{ n.label }}
            </label>
          </div>
        </fieldset>

        <label class="block mt-3">
          <span class="nhan">Thông tin tra cứu</span>
          <input
            v-model="truyVan"
            class="o w-full"
            autocomplete="off"
            spellcheck="false"
            :placeholder="nguonMeta(nguon).goi_y"
            aria-describedby="goi-y-lien-nganh"
          />
        </label>
        <p id="goi-y-lien-nganh" class="goi-y mt-1 mb-0">{{ nguonMeta(nguon).goi_y }}. Không lưu vào trình duyệt.</p>
        <Button class="mt-2" :disabled="dangTra" @click="traCuu">
          {{ dangTra ? "Đang tra cứu…" : "Tra cứu" }}
        </Button>
      </div>

      <div class="the p-3" aria-live="polite" :aria-busy="dangTra">
        <p v-if="dangTra" class="m-0" role="status">
          <span class="sr-only">Đang tra cứu dữ liệu mẫu…</span>
          <Skeleton :lines="4" height="1.6rem" />
        </p>
        <p v-else-if="loi" class="canh-bao m-0">{{ loi }}</p>
        <p v-else-if="!ketQua" class="m-0 text-[13px] text-phu">
          Chọn nguồn, nhập thông tin và bấm <b>Tra cứu</b> để xem kết quả đối chiếu.
        </p>
        <template v-else>
          <div class="flex flex-wrap items-center justify-between gap-2">
            <Badge :tone="toneTrangThai(ketQua.trang_thai)" size="sm">{{ nhanTrangThai(ketQua.trang_thai) }}</Badge>
            <span class="goi-y">{{ ketQua.he_thong }} · tin cậy {{ phanTram(ketQua.do_tin_cay) }}</span>
          </div>
          <p class="mt-2 mb-0 text-[13px]">{{ ketQua.mo_ta }}</p>
          <dl v-if="ketQua.truong.length" class="ds-thong-tin mt-2">
            <template v-for="t in ketQua.truong" :key="t.nhan">
              <dt>{{ t.nhan }}</dt>
              <dd>{{ t.gia_tri }}</dd>
            </template>
          </dl>
          <div class="mt-2 flex flex-wrap items-center gap-2">
            <Button
              v-if="coTheXacNhan"
              size="sm"
              :disabled="ketQua.trang_thai === 'khong_thay' || daXacNhan[nguon]"
              @click="xacNhan"
            >
              {{ daXacNhan[nguon] ? "Đã xác nhận" : "Xác nhận đối chiếu" }}
            </Button>
            <span v-else class="goi-y">Chỉ cán bộ nghiệp vụ được xác nhận đối chiếu.</span>
          </div>
        </template>
      </div>
    </div>

    <div class="the p-3 mt-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h4 class="text-[13px] font-semibold m-0">Liên kết dữ liệu chủ (MDM)</h4>
        <span class="goi-y">{{ nguonLienKet === "api" ? "Từ API MDM" : "Chưa có API" }}</span>
      </div>
      <p v-if="dangTaiLienKet" class="goi-y mt-2 mb-0" role="status">Đang tải liên kết…</p>
      <p v-else-if="nguonLienKet === 'khong_co'" class="goi-y mt-2 mb-0">
        API <code>/api/v1/mdm/dossiers/{id}/links</code> chưa sẵn sàng. Tab này vẫn dùng dữ liệu mẫu ở trên.
      </p>
      <ul v-else-if="lienKetItems.length" class="list-none m-0 p-0 mt-2 text-[13px]">
        <li v-for="x in lienKetItems" :key="x.nhan" class="flex flex-wrap items-center justify-between gap-2 py-1 border-b border-vien-nhat last:border-0">
          <span><b>{{ x.nhan }}</b>: {{ x.giaTri.nhan || "—" }}</span>
          <span class="goi-y">{{ phanTram(x.giaTri.confidence) }}</span>
        </li>
      </ul>
      <p v-else class="text-[13px] text-phu mt-2 mb-0">Chưa có liên kết MDM cho hồ sơ này.</p>
    </div>

    <div class="mt-3 rounded-[14px] border border-vien-nhat bg-mat-2 p-3 text-[12.5px] text-phu">
      <p class="m-0"><b class="text-chu">Đã xác nhận {{ soNguonDaXacNhan }}/{{ NGUON_OPTIONS.length }} nguồn trên phiên này.</b></p>
      <p class="m-0 mt-1">Không lưu PII vào localStorage/sessionStorage. Khi D triển khai API liên kết/audit, tab này sẽ ghi nhận thật.</p>
    </div>
  </section>
</template>

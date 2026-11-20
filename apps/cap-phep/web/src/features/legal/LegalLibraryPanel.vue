<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { getValidToken } from "../../auth";
import {
  fetchLegalCitationList,
  fetchLegalDocument,
  fetchLegalDocuments,
  type LegalCitation,
  type LegalDocument,
} from "../../api/legal";
import { notify } from "../../composables/useToast";
import { Button, Skeleton } from "../../design-system";

const ds = ref<LegalDocument[]>([]);
const chiTiet = ref<(LegalDocument & { citations: LegalCitation[] }) | null>(null);
const triches = ref<LegalCitation[]>([]);
const dangTai = ref(false);
const dangTaiChiTiet = ref(false);
const dangTaiTrich = ref(false);
const loi = ref("");
const tuKhoa = ref("");
const nhom = ref("");
const trangThai = ref("");
const chuDe = ref("");
const cheDo = ref<"van-ban" | "trich-dan">("van-ban");

const dsLoc = computed(() => {
  const q = tuKhoa.value.trim().toLowerCase();
  return ds.value.filter((d) => {
    if (nhom.value && d.group_name !== nhom.value) return false;
    if (trangThai.value && d.status !== trangThai.value) return false;
    if (!q) return true;
    return `${d.code} ${d.title} ${d.issuer} ${d.doc_type}`.toLowerCase().includes(q);
  });
});
const dsNhom = computed(() =>
  Array.from(new Set(ds.value.map((d) => d.group_name).filter(Boolean) as string[])).sort(),
);
const trangThaiMap: Record<string, string> = {
  con_hieu_luc: "Còn hiệu lực",
  het_hieu_luc: "Hết hiệu lực",
  sua_doi: "Đang sửa đổi",
};
const chuDeMap: Record<string, string> = {
  cap_cong_trinh: "Cấp công trình",
  tham_quyen: "Thẩm quyền",
  ho_so: "Hồ sơ",
  quy_hoach: "Quy hoạch",
  nghiem_thu: "Nghiệm thu",
  chia_se_du_lieu: "Chia sẻ dữ liệu",
  phi_le_phi: "Phí, lệ phí",
  luu_tru: "Lưu trữ",
  an_toan: "An toàn",
  moi_truong: "Môi trường",
};

function nhanTrangThai(value: string): string {
  return trangThaiMap[value] || value || "—";
}
function nhanChuDe(value?: string | null): string {
  return (value && chuDeMap[value]) || value || "—";
}
function ngay(value?: string | null): string {
  return value ? new Date(value).toLocaleDateString("vi-VN") : "—";
}
function tagsOf(d: LegalDocument): string[] {
  if (Array.isArray(d.tags)) return d.tags;
  try {
    const parsed = JSON.parse(String(d.tags || "[]"));
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}
function trichDanText(c: LegalCitation): string {
  return [c.article, c.clause, c.point].filter(Boolean).join(", ") || "Toàn văn";
}

async function tai(): Promise<void> {
  dangTai.value = true;
  loi.value = "";
  try {
    const token = await getValidToken();
    if (!token) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    ds.value = await fetchLegalDocuments(token, tuKhoa.value);
  } catch (e) {
    loi.value = e instanceof Error ? e.message : "Không tải được danh mục văn bản";
  } finally {
    dangTai.value = false;
  }
}

async function moVanBan(d: LegalDocument): Promise<void> {
  dangTaiChiTiet.value = true;
  try {
    const token = await getValidToken();
    if (!token) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    chiTiet.value = await fetchLegalDocument(token, d.document_id);
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tải được chi tiết văn bản", "loi");
  } finally {
    dangTaiChiTiet.value = false;
  }
}

async function taiTrichDan(): Promise<void> {
  dangTaiTrich.value = true;
  try {
    const token = await getValidToken();
    if (!token) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    triches.value = await fetchLegalCitationList(token, chuDe.value);
  } catch (e) {
    notify(e instanceof Error ? e.message : "Không tải được trích dẫn", "loi");
  } finally {
    dangTaiTrich.value = false;
  }
}

async function doiCheDo(mode: "van-ban" | "trich-dan"): Promise<void> {
  cheDo.value = mode;
  if (mode === "trich-dan" && !triches.value.length) await taiTrichDan();
}

onMounted(tai);
</script>

<template>
  <section id="legal-library" class="space-y-4">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="tieu-de-trang">Văn bản pháp luật</h2>
        <p class="mt-1 text-phu">
          Tra cứu văn bản, điều khoản và trích dẫn pháp lý đang áp dụng cho cấp phép xây dựng.
        </p>
      </div>
      <div class="flex flex-wrap gap-2" role="tablist" aria-label="Cách tra cứu pháp luật">
        <button
          type="button"
          class="btn btn-sm"
          :class="cheDo === 'van-ban' && 'btn-chinh'"
          role="tab"
          :aria-selected="cheDo === 'van-ban'"
          @click="doiCheDo('van-ban')"
        >
          Văn bản ({{ ds.length }})
        </button>
        <button
          type="button"
          class="btn btn-sm"
          :class="cheDo === 'trich-dan' && 'btn-chinh'"
          role="tab"
          :aria-selected="cheDo === 'trich-dan'"
          @click="doiCheDo('trich-dan')"
        >
          Trích dẫn
        </button>
      </div>
    </div>

    <template v-if="cheDo === 'van-ban'">
      <form class="the flex flex-wrap items-end gap-2 p-3" @submit.prevent="tai">
        <label class="min-w-[240px] flex-1">
          <span class="nhan">Tìm theo số hiệu hoặc tên văn bản</span>
          <input v-model="tuKhoa" class="o w-full" placeholder="Ví dụ: 217/2025, cấp phép xây dựng" />
        </label>
        <label class="min-w-[180px]">
          <span class="nhan">Nhóm văn bản</span>
          <select v-model="nhom" class="o w-full">
            <option value="">Tất cả nhóm</option>
            <option v-for="g in dsNhom" :key="g" :value="g">{{ g }}</option>
          </select>
        </label>
        <label class="min-w-[170px]">
          <span class="nhan">Trạng thái</span>
          <select v-model="trangThai" class="o w-full">
            <option value="">Tất cả trạng thái</option>
            <option value="con_hieu_luc">Còn hiệu lực</option>
            <option value="het_hieu_luc">Hết hiệu lực</option>
            <option value="sua_doi">Đang sửa đổi</option>
          </select>
        </label>
        <Button type="submit" size="sm">Tìm</Button>
      </form>

      <p v-if="dangTai" class="the p-3" role="status"><Skeleton :lines="5" height="1.6rem" /></p>
      <p v-else-if="loi" class="canh-bao the p-3">{{ loi }}</p>

      <div v-else class="grid gap-3 lg:grid-cols-[1fr_1.1fr]">
        <div class="the max-h-[620px] overflow-y-auto p-2" tabindex="0" aria-label="Danh mục văn bản pháp luật">
          <p v-if="!dsLoc.length" class="p-3 text-phu">Không có văn bản phù hợp bộ lọc.</p>
          <ul v-else class="m-0 list-none space-y-1 p-0">
            <li v-for="d in dsLoc" :key="d.document_id">
              <button
                type="button"
                class="w-full rounded-[12px] border border-transparent p-3 text-left transition hover:border-vien-nhat hover:bg-mat-2"
                :class="chiTiet?.document_id === d.document_id && 'border-vien-nhat bg-mat-2'"
                @click="moVanBan(d)"
              >
                <span class="flex flex-wrap items-center justify-between gap-2">
                  <b class="text-[13.5px]">{{ d.code }}</b>
                  <span class="tt" :class="d.status === 'con_hieu_luc' ? 'tt-xanh' : 'tt-vang'">{{ nhanTrangThai(d.status) }}</span>
                </span>
                <span class="mt-1 block text-[13px]">{{ d.title }}</span>
                <span class="mt-1 block text-[12px] text-phu">{{ d.doc_type }} · {{ d.issuer }} · {{ ngay(d.effective_date) }}</span>
              </button>
            </li>
          </ul>
        </div>

        <div class="the min-h-[320px] p-4">
          <p v-if="dangTaiChiTiet" class="text-phu" role="status">Đang tải chi tiết văn bản…</p>
          <p v-else-if="!chiTiet" class="text-phu">Chọn một văn bản ở danh sách bên trái để xem chi tiết.</p>
          <template v-else>
            <div class="flex flex-wrap items-start justify-between gap-2 border-b border-vien-nhat pb-3">
              <div class="min-w-0">
                <p class="nhan-nho m-0">{{ chiTiet.doc_type }} · {{ chiTiet.issuer }}</p>
                <h3 class="m-0 mt-1 text-[18px] font-semibold">{{ chiTiet.code }}</h3>
                <p class="m-0 mt-1 text-[13.5px]">{{ chiTiet.title }}</p>
              </div>
              <span class="tt" :class="chiTiet.status === 'con_hieu_luc' ? 'tt-xanh' : 'tt-vang'">{{ nhanTrangThai(chiTiet.status) }}</span>
            </div>

            <dl class="ds-thong-tin mt-3">
              <dt>Ngày ban hành</dt><dd>{{ ngay(chiTiet.issued_date) }}</dd>
              <dt>Ngày hiệu lực</dt><dd>{{ ngay(chiTiet.effective_date) }}</dd>
              <dt>Nhóm</dt><dd>{{ chiTiet.group_name || "—" }}</dd>
              <dt>Tệp đính kèm</dt><dd>{{ chiTiet.file_name || "—" }}</dd>
              <dt>Mã băm SHA-256</dt><dd class="break-all text-[12px] text-phu">{{ chiTiet.sha256 || "—" }}</dd>
            </dl>

            <p v-if="chiTiet.status_detail" class="mt-3 text-[13px] text-phu">{{ chiTiet.status_detail }}</p>
            <p v-if="chiTiet.notes" class="mt-2 text-[13px]">{{ chiTiet.notes }}</p>
            <div v-if="tagsOf(chiTiet).length" class="mt-2 flex flex-wrap gap-1.5">
              <span v-for="t in tagsOf(chiTiet)" :key="t" class="tt tt-xam">{{ t }}</span>
            </div>

            <div class="mt-3 flex flex-wrap gap-2">
              <a v-if="chiTiet.source_url" :href="chiTiet.source_url" target="_blank" rel="noopener" class="btn btn-sm">
                Mở nguồn chính thức
              </a>
            </div>

            <div class="mt-4 border-t border-vien-nhat pt-3">
              <h4 class="m-0 text-[13px] font-semibold">Trích dẫn trong văn bản ({{ chiTiet.citations.length }})</h4>
              <p v-if="!chiTiet.citations.length" class="mt-2 text-[12.5px] text-phu">Chưa có trích dẫn được ánh xạ.</p>
              <ul v-else class="m-0 mt-2 list-none space-y-2 p-0">
                <li v-for="c in chiTiet.citations" :key="c.citation_key" class="rounded-[12px] border border-vien-nhat p-2 text-[12.5px]">
                  <b>{{ trichDanText(c) }}</b>
                  <span class="ml-1 text-phu">· {{ nhanChuDe(c.topic) }}</span>
                  <p class="m-0 mt-1">{{ c.summary || "—" }}</p>
                </li>
              </ul>
            </div>
          </template>
        </div>
      </div>
    </template>

    <template v-else>
      <form class="the flex flex-wrap items-end gap-2 p-3" @submit.prevent="taiTrichDan">
        <label class="min-w-[240px] flex-1">
          <span class="nhan">Chủ đề trích dẫn</span>
          <select v-model="chuDe" class="o w-full">
            <option value="">Tất cả chủ đề</option>
            <option v-for="(ten, ma) in chuDeMap" :key="ma" :value="ma">{{ ten }}</option>
          </select>
        </label>
        <Button type="submit" size="sm">Tra cứu</Button>
      </form>

      <p v-if="dangTaiTrich" class="the p-3 text-phu" role="status">Đang tải trích dẫn…</p>
      <div v-else class="the overflow-x-auto p-0">
        <table class="bang w-full text-[13px]">
          <thead>
            <tr>
              <th>Văn bản</th>
              <th>Điều, khoản</th>
              <th>Chủ đề</th>
              <th>Nội dung</th>
              <th>Hiệu lực</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in triches" :key="c.citation_key">
              <td class="max-w-[220px]">
                <b>{{ c.document_code }}</b>
                <span class="block text-[12px] text-phu">{{ c.document_title }}</span>
              </td>
              <td class="whitespace-nowrap">{{ trichDanText(c) }}</td>
              <td class="whitespace-nowrap">{{ nhanChuDe(c.topic) }}</td>
              <td class="max-w-[360px]">{{ c.summary || "—" }}</td>
              <td class="whitespace-nowrap">
                <span class="tt" :class="c.status === 'con_hieu_luc' ? 'tt-xanh' : 'tt-vang'">{{ nhanTrangThai(c.status || "") }}</span>
                <span class="mt-1 block text-[12px] text-phu">{{ ngay(c.effective_date) }}</span>
              </td>
            </tr>
            <tr v-if="!triches.length">
              <td colspan="5" class="py-6 text-center text-phu">Chưa có trích dẫn phù hợp.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { ref } from "vue";
import {
  Badge, Button, Card, Checkbox, Drawer, EmptyState, Input, Modal, Pagination, RoleBadge, Select,
  Skeleton, StatCard, StatusBadge, Table, Tabs, Textarea, Toast,
  BarChart, DatePicker, DonutChart, FileUpload, LineChart, PdfViewer, Sparkline, Stepper, Timeline,
  type TableColumn,
} from "./index";
import { useTheme } from "../composables/useTheme";

/* Dữ liệu minh họa của trang demo component; không dùng ở màn hình nghiệp vụ */
const ten = ref("");
const loai = ref("");
const ghiChu = ref("");
const dongY = ref(false);
const tab = ref("thong-tin");
const trang = ref(3);
const moModal = ref(false);
const moDrawer = ref(false);
const dangTai = ref(false);
const cot: TableColumn[] = [
  { key: "ma", label: "Mã" },
  { key: "trang_thai", label: "Trạng thái" },
  { key: "so_ngay", label: "Số ngày", align: "right" },
];
const dong = [
  { id: 1, ma: "MẪU-001", trang_thai: "DANG_THAM_DINH", so_ngay: 3 },
  { id: 2, ma: "MẪU-002", trang_thai: "CAN_BO_SUNG", so_ngay: 6 },
  { id: 3, ma: "MẪU-003", trang_thai: "DA_CAP", so_ngay: 12 },
  { id: 4, ma: "MẪU-004", trang_thai: "TU_CHOI", so_ngay: 9 },
];
const { theme, toggle: toggleTheme } = useTheme();
const ngay = ref("");
const tienDo = ref<number | null>(null);
const tepDaChon = ref<string[]>([]);
const moPdf = ref(false);
/* PDF một trang tạo tại chỗ để xem thử trình xem, không tải từ mạng */
const pdfMau = URL.createObjectURL(
  new Blob(
    [
      "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj " +
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj " +
        "4 0 obj<</Length 44>>stream\nBT /F1 18 Tf 40 100 Td (Ban ve mau) Tj ET\nendstream endobj " +
        "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF",
    ],
    { type: "application/pdf" },
  ),
);
function chonTep(files: File[]) {
  tepDaChon.value = files.map((f) => f.name);
  tienDo.value = 0;
  const t = window.setInterval(() => {
    tienDo.value = Math.min(100, (tienDo.value ?? 0) + 20);
    if (tienDo.value >= 100) window.clearInterval(t);
  }, 300);
}
function giaLapTai() {
  dangTai.value = true;
  window.setTimeout(() => (dangTai.value = false), 1500);
}
</script>

<template>
  <main class="mx-auto flex max-w-5xl flex-col gap-8 p-6 font-sans text-ds-text">
    <header class="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 class="m-0 text-ds-2xl font-semibold">Design system</h1>
        <p class="m-0 text-ds-sm text-ds-muted">Component dùng chung cho giao diện cấp phép. Dữ liệu trên trang này là ví dụ.</p>
      </div>
      <Button variant="secondary" @click="toggleTheme">Đổi sang nền {{ theme === "dark" ? "sáng" : "đêm" }}</Button>
    </header>

    <Card title="Màu nhấn và trạng thái">
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div v-for="m in ['primary', 'brand', 'gold', 'success', 'warning', 'danger', 'info']" :key="m" class="flex items-center gap-2">
          <span class="h-8 w-8 rounded-ds-sm border border-ds-border" :class="'bg-ds-' + m" />
          <code class="text-ds-sm">{{ m }}</code>
        </div>
      </div>
    </Card>

    <Card title="Nút">
      <div class="flex flex-wrap items-center gap-3">
        <Button>Lưu thay đổi</Button>
        <Button variant="secondary">Hủy</Button>
        <Button variant="ghost">Xem thêm</Button>
        <Button variant="danger">Từ chối hồ sơ</Button>
        <Button size="sm">Nhỏ</Button>
        <Button size="lg">Lớn</Button>
        <Button disabled>Không dùng được</Button>
        <Button :loading="dangTai" @click="giaLapTai">Đang xử lý</Button>
      </div>
    </Card>

    <Card title="Ô nhập">
      <div class="grid gap-4 sm:grid-cols-2">
        <Input v-model="ten" label="Họ và tên" placeholder="Nguyễn Văn A" hint="Đúng như trên căn cước" required />
        <Input model-value="12" label="Số tầng" type="number" error="Vượt số tầng cho phép của khu vực" />
        <Select
          v-model="loai"
          label="Loại công trình"
          placeholder="Chọn loại"
          :options="[{ value: 'nha-o', label: 'Nhà ở riêng lẻ' }, { value: 'sua-chua', label: 'Sửa chữa, cải tạo' }]"
        />
        <Textarea v-model="ghiChu" label="Ghi chú" :maxlength="200" />
        <Checkbox v-model="dongY" label="Tôi cam kết thông tin khai là đúng" hint="Bắt buộc trước khi nộp" />
      </div>
    </Card>

    <Card title="Nhãn">
      <div class="flex flex-wrap gap-2">
        <Badge>Trung tính</Badge>
        <Badge tone="brand">Thương hiệu</Badge>
        <Badge tone="gold">Ưu tiên</Badge>
        <StatusBadge status="DANG_THAM_DINH" label="Đang thẩm định" />
        <StatusBadge status="CAN_BO_SUNG" label="Cần bổ sung" />
        <StatusBadge status="DA_CAP" label="Đã cấp" />
        <StatusBadge status="TU_CHOI" label="Từ chối" />
        <RoleBadge role="app:cap-phep:tham-dinh" />
        <RoleBadge role="dx:auditor" />
      </div>
    </Card>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="Hồ sơ mới" :value="128" :previous="110" />
      <StatCard label="Quá hạn" :value="7" :previous="4" tone="danger" increase-is-bad />
      <StatCard label="Thời gian trung bình" :value="9.5" unit="ngày" tone="info" hint="Tính trên hồ sơ đã có kết quả" />
      <StatCard label="Chưa có dữ liệu" :value="null" tone="neutral" hint="Nguồn chưa sẵn sàng" clickable />
    </div>

    <Card title="Bảng và phân trang" :padded="false">
      <div class="flex flex-col gap-4 p-5">
        <Table :columns="cot" :rows="dong" caption="Ví dụ bảng hồ sơ">
          <template #cell-trang_thai="{ value }"><StatusBadge :status="value" size="sm" /></template>
        </Table>
        <Table :columns="cot" :rows="[]" empty-title="Chưa có hồ sơ" empty-description="Hồ sơ mới sẽ hiện ở đây." />
        <Table :columns="cot" :rows="[]" loading />
        <Pagination v-model="trang" :total="243" :page-size="20" />
      </div>
    </Card>

    <Card title="Tab">
      <Tabs
        v-model="tab"
        label="Ví dụ tab"
        :tabs="[{ key: 'thong-tin', label: 'Thông tin' }, { key: 'giay-to', label: 'Giấy tờ', count: 5 }, { key: 'lich-su', label: 'Lịch sử' }]"
      >
        <template #thong-tin><p class="m-0">Nội dung tab thông tin.</p></template>
        <template #giay-to><p class="m-0">Nội dung tab giấy tờ.</p></template>
        <template #lich-su><Skeleton :lines="3" /></template>
      </Tabs>
    </Card>

    <Card title="Hộp thoại, ngăn kéo, thông báo">
      <div class="flex flex-wrap gap-3">
        <Button variant="secondary" @click="moModal = true">Mở hộp thoại</Button>
        <Button variant="secondary" @click="moDrawer = true">Mở ngăn kéo</Button>
      </div>
      <div class="mt-4 flex flex-wrap gap-3">
        <Toast kind="ok" text="Đã lưu hồ sơ." />
        <Toast kind="loi" text="Không kết nối được máy chủ." />
      </div>
      <EmptyState title="Chưa có bản vẽ" description="Thêm bản vẽ để bắt đầu thẩm định.">
        <Button size="sm">Thêm bản vẽ</Button>
      </EmptyState>
    </Card>

    <div class="grid gap-4 lg:grid-cols-3">
      <DonutChart
        title="Hồ sơ theo trạng thái"
        :items="[
          { label: 'Đang xử lý', value: 42 },
          { label: 'Chờ bổ sung', value: 11 },
          { label: 'Đã cấp', value: 63 },
          { label: 'Từ chối', value: 6 },
        ]"
      />
      <LineChart
        class="lg:col-span-2"
        title="Hồ sơ theo tháng"
        :labels="['T6', 'T7', 'T8', 'T9', 'T10', 'T11']"
        :series="[
          { name: 'Tiếp nhận', values: [30, 42, 38, 51, 47, 55] },
          { name: 'Hoàn thành', values: [22, 35, null, 44, 40, 49] },
        ]"
      />
      <BarChart
        class="lg:col-span-2"
        title="Tải việc theo cán bộ"
        unit="việc"
        :items="[
          { label: 'Cán bộ A', value: 12 },
          { label: 'Cán bộ B', value: 7 },
          { label: 'Cán bộ C', value: 15 },
          { label: 'Cán bộ D', value: 4 },
        ]"
      />
      <LineChart title="Biểu đồ chưa có dữ liệu" :labels="[]" :series="[]" />
    </div>

    <Card title="Tiến trình và mốc thời gian">
      <div class="flex flex-col gap-6">
        <Stepper
          current="ket-cau"
          :steps="[
            { key: 'mong', label: 'Móng' },
            { key: 'ket-cau', label: 'Kết cấu' },
            { key: 'hoan-thien', label: 'Hoàn thiện' },
            { key: 'hoan-cong', label: 'Hoàn công' },
          ]"
        />
        <Timeline
          :items="[
            { title: 'Nộp hồ sơ', time: '02/11/2026 09:15', tone: 'info' },
            { title: 'Yêu cầu bổ sung', time: '05/11/2026 14:00', description: 'Thiếu bản vẽ kết cấu.', tone: 'warning' },
            { title: 'Cấp giấy phép', time: '18/11/2026 10:30', tone: 'success' },
          ]"
        />
        <div class="flex items-center gap-3 text-ds-brand">
          <Sparkline :values="[3, 5, 4, 8, 6, 9, 11]" />
          <span class="text-ds-sm text-ds-muted">Sparkline trong thẻ chỉ số</span>
        </div>
      </div>
    </Card>

    <Card title="Tệp và ngày">
      <div class="grid gap-4 sm:grid-cols-2">
        <FileUpload label="Thêm bản vẽ" :accept="['.pdf']" :max-bytes="20 * 1024 * 1024" :progress="tienDo" @select="chonTep" />
        <div class="flex flex-col gap-3">
          <DatePicker v-model="ngay" label="Ngày nghiệm thu" hint="Chọn ngày dự kiến" />
          <p class="m-0 text-ds-sm text-ds-muted">Tệp đã chọn: {{ tepDaChon.join(", ") || "chưa có" }}</p>
          <Button variant="secondary" @click="moPdf = true">Xem bản vẽ PDF mẫu</Button>
        </div>
      </div>
    </Card>
    <Drawer v-model:open="moPdf" title="Bản vẽ mẫu" width="min(900px, 100vw)">
      <PdfViewer :src="pdfMau" title="Bản vẽ mẫu" filename="ban-ve-mau.pdf" />
    </Drawer>

    <Modal v-model:open="moModal" title="Xác nhận từ chối">
      <p class="m-0">Hộp thoại giữ focus bên trong, Esc để đóng.</p>
      <template #footer>
        <Button variant="secondary" @click="moModal = false">Hủy</Button>
        <Button variant="danger" @click="moModal = false">Từ chối</Button>
      </template>
    </Modal>
    <Drawer v-model:open="moDrawer" title="Xem bản vẽ">
      <Skeleton :lines="6" />
    </Drawer>
  </main>
</template>

<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start" id="workspace-3-cols">
    <section
      v-if="pendingBreakGlassList && pendingBreakGlassList.length > 0"
      id="section-pending-break-glass"
      class="lg:col-span-12 the overflow-hidden"
      aria-labelledby="tieu-de-truy-cap-khan"
    >
      <div class="px-5 py-3.5 border-b border-vien-nhat flex flex-wrap items-baseline gap-x-3">
        <h2 id="tieu-de-truy-cap-khan" class="text-[15px] font-semibold m-0">Yêu cầu truy cập khẩn chờ duyệt</h2>
        <span class="mo">Cán bộ xin mở hồ sơ ngoài phân công. Mỗi lần duyệt đều được ghi vào nhật ký hồ sơ.</span>
      </div>
      <div class="overflow-x-auto">
        <table class="bang" id="table-pending-break-glass">
          <thead>
            <tr>
              <th>Mã hồ sơ</th>
              <th>Cán bộ yêu cầu</th>
              <th>Lý do</th>
              <th>Thời điểm</th>
              <th><span class="sr-only">Thao tác</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="bg in pendingBreakGlassList" :key="bg.id">
              <td class="ma whitespace-nowrap">{{ bg.ma_ho_so || bg.object_id?.slice(0, 8) }}</td>
              <td class="whitespace-nowrap">{{ bg.requester_name || bg.requester_sub }}</td>
              <td class="min-w-[220px] max-w-[420px]">{{ bg.reason }}</td>
              <td class="whitespace-nowrap text-phu">{{ ngayGio(bg.created_at) }}</td>
              <td class="text-right whitespace-nowrap">
                <button type="button" id="btn-deny-break-glass" class="btn btn-sm btn-nguy mr-1.5" @click="$emit('deny-break-glass', bg)">Từ chối</button>
                <button type="button" id="btn-approve-break-glass" class="btn btn-sm" @click="$emit('approve-break-glass', bg)">Duyệt</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Danh sách việc -->
    <section class="lg:col-span-4 the overflow-hidden" aria-labelledby="tieu-de-viec">
      <div class="px-4 py-3.5 border-b border-vien-nhat flex justify-between items-baseline">
        <h2 id="tieu-de-viec" class="text-[15px] font-semibold m-0">Việc cần xử lý</h2>
        <span class="mo">{{ tasks.length }} việc</span>
      </div>
      <div v-if="tasks.length === 0" class="px-4 py-10 text-center text-phu">Không có việc nào đang chờ bạn.</div>
      <div v-else class="lg:max-h-[640px] overflow-y-auto">
        <button
          v-for="t in tasks"
          :key="t.id"
          :id="'task-card-' + t.id"
          type="button"
          :aria-pressed="selectedTask?.id === t.id"
          :class="['viec', selectedTask?.id === t.id && 'viec-chon']"
          @click="selectTask(t)"
        >
          <span class="font-semibold block">{{ tenNhiemVu(t) }}</span>
          <span class="flex justify-between gap-3 mt-0.5 text-[12.5px] text-phu">
            <span>{{ dossierOfTask(t)?.ma_ho_so || ngayGio(t.createTime) }}</span>
            <span :class="taskDue(t).gap && 'text-son font-semibold'">{{ taskDue(t).text }}</span>
          </span>
        </button>
      </div>
    </section>

    <!-- Chi tiết -->
    <section class="lg:col-span-8 the" aria-live="polite">
      <div v-if="!selectedTask" class="px-6 py-16 text-center text-phu">Chọn một việc ở danh sách bên trái để xem hồ sơ và xử lý.</div>

      <template v-else>
        <div class="px-6 pt-5 pb-4 border-b border-vien-nhat">
          <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 class="text-[18px] font-semibold m-0">{{ tenNhiemVu(selectedTask) }}</h2>
            <span v-if="currentDossier" class="ma">{{ currentDossier.ma_ho_so }}</span>
            <span v-if="currentDossier" :class="getStatusBadgeClass(currentDossier.trang_thai)">{{ formatStatus(currentDossier.trang_thai) }}</span>
            <span v-if="currentDossier && (currentDossier.qua_han || isOverdue)" class="tt tt-do">Quá hạn</span>
          </div>

          <!-- Đường hạn giải quyết theo ngày làm việc -->
          <div v-if="currentDossier" class="mt-4" :aria-label="`Ngày làm việc thứ ${deadline.used} trên ${deadline.total}`">
            <div class="grid gap-[3px]" :style="{ gridTemplateColumns: `repeat(${deadline.total}, 1fr)` }">
              <i
                v-for="n in deadline.total"
                :key="n"
                :class="['h-1.5 rounded-full', n < deadline.used ? 'bg-muc-2' : n === deadline.used ? 'bg-cham' : 'bg-mat-noi']"
              ></i>
            </div>
            <div class="grid mt-2 text-[12.5px] text-phu" :style="{ gridTemplateColumns: deadline.cols }">
              <span
                v-for="m in deadline.steps"
                :key="m.key"
                :class="['moc', m.state === 'xong' && 'text-chu', m.state === 'dang' && 'moc-dang']"
              >{{ m.label }}</span>
            </div>
            <div class="flex flex-wrap justify-between gap-2 mt-2.5 text-[13px]">
              <span>Ngày làm việc thứ <b class="font-semibold">{{ deadline.used }}</b> trên {{ deadline.total }} theo quy định</span>
              <span>{{ countdownText }}</span>
            </div>
          </div>
        </div>

        <div class="px-6 py-5 grid gap-7 xl:grid-cols-[1fr_280px]">
          <div class="min-w-0">
            <div v-if="currentDossier" id="dossier-info-block" data-testid="block-workspace-dossier-info">
              <h3 class="muc-con">Chủ đầu tư</h3>
              <dl class="ds-thong-tin">
                <dt>Họ tên</dt><dd id="info-chu-dau-tu">{{ currentDossier.ho_ten }}</dd>
                <dt>CCCD</dt><dd>{{ cheCccd(currentDossier.cccd) }}</dd>
                <dt>Điện thoại</dt><dd>{{ currentDossier.dien_thoai }}</dd>
              </dl>

              <h3 class="muc-con">Công trình</h3>
              <dl class="ds-thong-tin">
                <dt>Địa chỉ</dt><dd id="info-dia-chi">{{ currentDossier.dia_chi_cong_trinh }}</dd>
                <dt>Thửa đất</dt><dd>{{ currentDossier.thua_dat }}</dd>
                <dt>Quy mô</dt><dd>{{ currentDossier.so_tang }} tầng, diện tích sàn {{ formatNumberVi(currentDossier.dien_tich_san_m2) }} m²</dd>
                <dt>Ngày nộp</dt><dd>{{ ngayGio(currentDossier.created_at) }}</dd>
              </dl>

              <div v-if="currentDossier.ly_do_bo_sung" class="thong-bao-vang mt-4">
                <b class="font-semibold">Đã yêu cầu bổ sung:</b> {{ currentDossier.ly_do_bo_sung }}
              </div>

              <h3 class="muc-con">Hồ sơ đính kèm</h3>
              <p v-if="loadingFiles" class="text-phu m-0">Đang tải danh sách tệp…</p>
              <p v-else-if="dossierFiles.length === 0" class="text-phu m-0">Hồ sơ chưa có tệp đính kèm.</p>
              <div v-else>
                <div v-for="f in dossierFiles" :key="f.id" class="the-tep flex-col !items-stretch">
                  <div class="flex items-center gap-3">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" class="text-phu flex-shrink-0" aria-hidden="true"><path d="M14 3H6v18h12V7z" /><path d="M14 3v4h4" /></svg>
                    <span class="flex-1 min-w-0">
                      <span class="block truncate font-medium">{{ f.ten_loai || f.loai || getFileName(f) }}<span v-if="f.version > 1" class="text-phu font-normal">, lần nộp {{ f.version }}</span></span>
                      <span class="mo block truncate" :title="getFileName(f)">{{ getFileName(f) }}, {{ formatFileSize(f.size) }}</span>
                    </span>
                    <span class="text-xanh text-[12.5px] hidden sm:inline">Đã quét virus, an toàn</span>
                    <button type="button" :id="`btn-view-file-${f.file_id || f.id}`" class="btn btn-sm" @click="viewFile(f)">Xem</button>
                  </div>
                  <!-- Cán bộ đánh giá từng giấy tờ: đạt, hoặc không đạt kèm lý do để chủ đầu tư biết cần sửa gì -->
                  <div class="flex flex-wrap items-center gap-2 mt-2 pl-[30px]">
                    <span :id="`file-status-${f.id}`" :class="['tt', reviewTone(f)]">{{ reviewLabel(f) }}</span>
                    <span class="flex-1"></span>
                    <template v-if="dangDanhGia !== f.id">
                      <button v-if="f.trang_thai_kiem_tra !== 'dat'" type="button" :id="`btn-file-dat-${f.id}`" class="btn btn-sm" :disabled="dangLuu" @click="reviewFile(f, 'dat')">Đạt</button>
                      <button v-if="f.trang_thai_kiem_tra !== 'khong_dat'" type="button" :id="`btn-file-khong-dat-${f.id}`" class="btn btn-sm" :disabled="dangLuu" @click="moDanhGiaKhongDat(f)">Không đạt</button>
                    </template>
                  </div>
                  <p v-if="f.trang_thai_kiem_tra === 'khong_dat' && f.ly_do && dangDanhGia !== f.id" class="text-son text-[13px] mt-1 mb-0 pl-[30px]">Lý do: {{ f.ly_do }}</p>
                  <form v-if="dangDanhGia === f.id" class="flex flex-wrap gap-2 mt-2 pl-[30px]" @submit.prevent="reviewFile(f, 'khong_dat')">
                    <label :for="`ly-do-tep-${f.id}`" class="sr-only">Lý do không đạt</label>
                    <input :id="`ly-do-tep-${f.id}`" v-model="lyDoTep" required class="o flex-1 min-w-[200px] !h-9" placeholder="Lý do không đạt, ví dụ: bản vẽ thiếu chữ ký" />
                    <button type="submit" class="btn btn-sm" :disabled="dangLuu || !lyDoTep.trim()">Lưu</button>
                    <button type="button" class="btn btn-sm" @click="dangDanhGia = ''">Hủy</button>
                  </form>
                </div>
              </div>
            </div>
            <p v-else class="text-phu m-0">Không tìm thấy hồ sơ gắn với việc này trong danh sách của bạn.</p>

            <div v-if="forbiddenError" class="thong-bao-loi mt-4">
              Bạn chưa được phân công hồ sơ này.
              <button v-if="currentHoSoId" type="button" class="btn btn-sm btn-nguy ml-2" @click="$emit('request-break-glass', currentHoSoId)">Xin truy cập khẩn</button>
            </div>

            <div v-if="currentDossier && currentDossier.trang_thai === 'CHO_KY'" class="thong-bao-vang mt-4">
              <p class="m-0">Hồ sơ đã được duyệt nhưng chưa ký số xong.</p>
              <button type="button" id="btn-retry-signing" class="btn btn-sm mt-2" :disabled="isRetrying" @click="retrySigning(currentDossier)">
                {{ isRetrying ? "Đang ký…" : "Ký lại" }}
              </button>
              <p v-if="retryMsg" :class="['m-0 mt-2', retrySuccess ? 'text-xanh' : 'text-son']">{{ retryMsg }}</p>
            </div>
          </div>

          <aside class="min-w-0">
            <h3 class="muc-con">Lịch sử xử lý</h3>
            <p v-if="auditLogs.length === 0" class="text-phu m-0 text-[13px]">Chưa có ghi nhận nào.</p>
            <ol v-else class="list-none m-0 p-0 text-[13px] lg:max-h-[420px] overflow-y-auto">
              <li
                v-for="(log, idx) in auditLogs"
                :key="idx"
                :class="['grid grid-cols-[46px_1fr] gap-2 py-2 border-b border-vien-nhat last:border-b-0', isBreakGlass(log) && 'text-son']"
              >
                <time class="text-phu">{{ ngayThang(log.at || log.timestamp) }}</time>
                <span>
                  {{ tenHanhDong(log.action) }}<template v-if="lyDo(log)">, lý do: {{ lyDo(log) }}</template>
                  <span class="block text-phu">{{ log.actor_name || log.actor_sub || "Hệ thống" }}</span>
                </span>
              </li>
            </ol>
          </aside>
        </div>

        <!-- Quyết định -->
        <div class="px-6 py-5 border-t border-vien-nhat">
          <div v-if="selectedTask.taskDefinitionKey === 'taskKiemTraHopLe'">
            <fieldset class="border-0 p-0 m-0">
              <legend class="nhan">Kết quả kiểm tra hồ sơ</legend>
              <div class="flex flex-wrap gap-x-6 gap-y-2">
                <label class="lua-chon"><input type="radio" :value="true" v-model="taskForm.hoSoHopLe" id="radio-hop-le" /> Hồ sơ hợp lệ, tiếp nhận</label>
                <label class="lua-chon"><input type="radio" :value="false" v-model="taskForm.hoSoHopLe" id="radio-can-bo-sung" /> Cần bổ sung giấy tờ</label>
              </div>
            </fieldset>
            <div v-if="!taskForm.hoSoHopLe" class="mt-3">
              <label for="txt-ly-do-bo-sung" class="nhan">Giấy tờ cần bổ sung <span class="text-son">*</span></label>
              <textarea v-model="taskForm.lyDoBoSung" id="txt-ly-do-bo-sung" required rows="3" class="o" placeholder="Ví dụ: bản vẽ mặt bằng tầng 2, bản sao giấy chứng nhận quyền sử dụng đất"></textarea>
              <p class="goi-y mt-1 mb-0">Chủ đầu tư sẽ thấy nội dung này khi bổ sung.</p>
            </div>
            <div class="flex justify-end mt-4">
              <button type="button" id="btn-complete-task" class="btn btn-chinh" @click="submitTiepNhan">
                {{ taskForm.hoSoHopLe ? "Tiếp nhận hồ sơ" : "Gửi yêu cầu bổ sung" }}
              </button>
            </div>
          </div>

          <div v-else-if="selectedTask.taskDefinitionKey === 'taskPhanCong'">
            <label for="chon-tham-dinh" class="nhan">Thẩm định viên</label>
            <select id="chon-tham-dinh" v-model="taskForm.nguoiThamDinh" class="o sm:max-w-[360px]">
              <option value="" disabled>Chọn thẩm định viên</option>
              <option v-for="off in availableOfficers" :key="off.value" :value="off.value">{{ off.label }}</option>
            </select>
            <div class="flex justify-end mt-4">
              <button
                type="button"
                id="btn-submit-phan-cong"
                class="btn btn-chinh"
                :disabled="!taskForm.nguoiThamDinh"
                @click="submitComplete({ nguoiThamDinh: taskForm.nguoiThamDinh, lanhDaoPhanCong: userSub })"
              >Phân công</button>
            </div>
          </div>

          <div v-else-if="selectedTask.taskDefinitionKey?.includes('ThamDinh')">
            <fieldset class="border-0 p-0 m-0">
              <legend class="nhan">Kết quả thẩm định</legend>
              <div class="flex flex-wrap gap-x-6 gap-y-2">
                <label class="lua-chon"><input type="radio" value="DAT" v-model="taskForm.ketQuaThamDinh" /> Đạt</label>
                <label class="lua-chon"><input type="radio" value="KHONG_DAT" v-model="taskForm.ketQuaThamDinh" /> Không đạt</label>
              </div>
            </fieldset>
            <label for="txt-noi-dung-tham-dinh" class="nhan mt-3">Nhận xét thẩm định</label>
            <textarea id="txt-noi-dung-tham-dinh" v-model="taskForm.noiDungThamDinh" rows="3" class="o" placeholder="Đối chiếu quy hoạch, chỉ giới xây dựng, kết cấu"></textarea>
            <div class="flex justify-end mt-4">
              <button
                type="button"
                id="btn-submit-tham-dinh"
                class="btn btn-chinh"
                @click="submitComplete({ ketQuaThamDinh: taskForm.ketQuaThamDinh, noiDungThamDinh: taskForm.noiDungThamDinh })"
              >Gửi kết quả thẩm định</button>
            </div>
          </div>

          <div v-else-if="selectedTask.taskDefinitionKey?.includes('Duyet')">
            <fieldset class="border-0 p-0 m-0">
              <legend class="nhan">Quyết định</legend>
              <div class="flex flex-wrap gap-x-6 gap-y-2">
                <label class="lua-chon"><input type="radio" :value="true" v-model="taskForm.dongYCapPhep" /> Đồng ý cấp phép</label>
                <label class="lua-chon"><input type="radio" :value="false" v-model="taskForm.dongYCapPhep" /> Từ chối cấp phép</label>
              </div>
            </fieldset>
            <label for="txt-y-kien" class="nhan mt-3">Ý kiến phê duyệt<span v-if="!taskForm.dongYCapPhep" class="text-son"> *</span></label>
            <textarea id="txt-y-kien" v-model="taskForm.yKienPheDuyet" rows="2" class="o" :placeholder="taskForm.dongYCapPhep ? 'Không bắt buộc' : 'Nêu lý do từ chối'"></textarea>
            <div class="flex justify-end mt-4">
              <button
                type="button"
                id="btn-submit-phe-duyet"
                class="btn btn-chinh"
                :disabled="!taskForm.dongYCapPhep && !taskForm.yKienPheDuyet.trim()"
                @click="submitComplete({ pheDuyet: taskForm.dongYCapPhep, dongYCapPhep: taskForm.dongYCapPhep, yKienPheDuyet: taskForm.yKienPheDuyet })"
              >{{ taskForm.dongYCapPhep ? "Phê duyệt và ký số" : "Từ chối cấp phép" }}</button>
            </div>
          </div>

          <div v-else-if="selectedTask.taskDefinitionKey === 'taskKiemTraHienTruong'">
            <fieldset class="border-0 p-0 m-0">
              <legend class="nhan">Kết quả kiểm tra hiện trường</legend>
              <div class="flex flex-wrap gap-x-6 gap-y-2">
                <label class="lua-chon"><input type="radio" value="dat" v-model="taskForm.ketLuanHauKiem" id="radio-hk-dat" /> Đạt</label>
                <label class="lua-chon"><input type="radio" value="vi_pham" v-model="taskForm.ketLuanHauKiem" id="radio-hk-vipham" /> Có vi phạm</label>
              </div>
            </fieldset>
            <div class="grid sm:grid-cols-2 gap-3 mt-3">
              <div>
                <label for="input-chi-so-do" class="nhan">Chỉ số đo tại hiện trường</label>
                <input v-model="taskForm.chiSoDo" id="input-chi-so-do" type="text" class="o" placeholder="Ví dụ: tiếng ồn 65 dBA" />
              </div>
              <div>
                <label for="file-bien-ban-kiem-tra" class="nhan">Biên bản kiểm tra (PDF hoặc ảnh)</label>
                <input type="file" id="file-bien-ban-kiem-tra" class="chon-tep" accept=".pdf,.png,.jpg,.jpeg" @change="handleBienBanFileUpload" />
                <span v-if="taskForm.bienBanFileId" class="text-[12.5px] text-xanh">Đã đính kèm biên bản</span>
              </div>
            </div>
            <label for="input-ghi-chu-hau-kiem" class="nhan mt-3">Ghi chú</label>
            <textarea v-model="taskForm.ghiChuHauKiem" id="input-ghi-chu-hau-kiem" rows="2" class="o" placeholder="Tình trạng thi công, kiến nghị"></textarea>
            <div class="flex justify-end mt-4">
              <button
                type="button"
                id="btn-submit-kiem-tra-hien-truong"
                class="btn btn-chinh"
                @click="submitComplete({ ketLuan: taskForm.ketLuanHauKiem, chiSoDo: taskForm.chiSoDo, ghiChu: taskForm.ghiChuHauKiem, bien_ban_file_id: taskForm.bienBanFileId })"
              >Lưu kết quả kiểm tra</button>
            </div>
          </div>

          <div v-else-if="selectedTask.taskDefinitionKey === 'taskXuLyViPham'">
            <label for="input-xu-ly-vi-pham" class="nhan">Biện pháp xử lý và yêu cầu khắc phục</label>
            <textarea v-model="taskForm.ghiChuHauKiem" id="input-xu-ly-vi-pham" rows="3" class="o" placeholder="Ví dụ: tạm dừng máy khoan sau 22 giờ"></textarea>
            <label for="file-bien-ban-xu-phat" class="nhan mt-3">Quyết định hoặc biên bản xử phạt</label>
            <input type="file" id="file-bien-ban-xu-phat" class="chon-tep" accept=".pdf,.png,.jpg,.jpeg" @change="handleBienBanFileUpload" />
            <span v-if="taskForm.bienBanFileId" class="text-[12.5px] text-xanh">Đã đính kèm biên bản</span>
            <div class="flex justify-end mt-4">
              <button
                type="button"
                id="btn-submit-xu-ly-vi-pham"
                class="btn btn-chinh"
                @click="submitComplete({ ghiChu: taskForm.ghiChuHauKiem, bien_ban_file_id: taskForm.bienBanFileId })"
              >Hoàn tất xử lý</button>
            </div>
          </div>

          <div v-else class="flex justify-end">
            <button type="button" class="btn btn-chinh" @click="submitComplete({})">Hoàn thành</button>
          </div>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { formatStatus, getStatusBadgeClass, formatNumberVi } from "../utils/formatters";
import { tenNhiemVu, tenHanhDong, cheCccd, ngayGio, ngayLamViecDaQua } from "../utils/labels";
import { notify } from "../composables/useToast";
import { reviewDossierFile } from "../api";

const props = defineProps<{
  tasks: any[];
  dossiers?: any[];
  userSub?: string;
  userTenant?: string;
  userToken?: string;
  forbiddenError?: boolean;
  pendingBreakGlassList?: any[];
}>();

const emit = defineEmits<{
  (e: "select-task", task: any): void;
  (e: "complete-task", payload: { taskId: string; variables: Record<string, any> }): void;
  (e: "request-break-glass", hoSoId: string): void;
  (e: "approve-break-glass", request: any): void;
  (e: "deny-break-glass", request: any): void;
}>();

const selectedTask = ref<any>(null);

interface OfficerItem {
  sub: string;
  username: string;
  ho_ten: string;
}

const officersList = ref<OfficerItem[]>([]);

const availableOfficers = computed(() => {
  return officersList.value.map((o) => ({
    value: o.username,
    label: o.ho_ten ? `${o.ho_ten} (${o.username})` : o.username,
    sub: o.sub,
    username: o.username,
    ho_ten: o.ho_ten,
  }));
});

const loadOfficers = async () => {
  try {
    const token = props.userToken || localStorage.getItem("token") || localStorage.getItem("access_token");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch("/api/v1/rest/rpc/ds_can_bo", {
      method: "POST",
      headers,
      body: JSON.stringify({ p_vai: "tham-dinh" }),
    });
    if (res.ok) {
      officersList.value = await res.json();
    }
  } catch (err) {
    console.warn("Không thể tải danh sách cán bộ thẩm định:", err);
  }
};

onMounted(() => {
  loadOfficers();
});

watch(selectedTask, (newTask) => {
  if (newTask && newTask.taskDefinitionKey === "taskPhanCong") {
    loadOfficers();
  }
});

const taskForm = ref({
  hoSoHopLe: true,
  lyDoBoSung: "",
  nguoiThamDinh: "",
  ketQuaThamDinh: "DAT",
  noiDungThamDinh: "",
  dongYCapPhep: true,
  yKienPheDuyet: "",
  ketLuanHauKiem: "dat",
  chiSoDo: "",
  ghiChuHauKiem: "",
  bienBanFileId: "",
});

async function handleBienBanFileUpload(event: Event) {
  const target = event.target as HTMLInputElement;
  if (!target.files || target.files.length === 0) return;
  const file = target.files[0];
  const token = props.userToken || localStorage.getItem("token") || localStorage.getItem("access_token") || "";
  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("object_type", "generic");
    formData.append("object_id", "bien_ban_kiem_tra");
    const resp = await fetch("/api/v1/files", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.message || `Lỗi tải tệp: HTTP ${resp.status}`);
    }
    const data = await resp.json();
    taskForm.value.bienBanFileId = data.file_id || data.id;
  } catch (err: any) {
    notify("Không tải được biên bản: " + (err.message || err), "loi");
  }
}

function submitTiepNhan() {
  if (!taskForm.value.hoSoHopLe) {
    if (!taskForm.value.lyDoBoSung || !taskForm.value.lyDoBoSung.trim()) {
      notify("Nhập giấy tờ cần bổ sung trước khi gửi.", "loi");
      return;
    }
    submitComplete({
      hoSoHopLe: false,
      lyDoBoSung: taskForm.value.lyDoBoSung.trim(),
      lyDoTra: taskForm.value.lyDoBoSung.trim(),
    });
  } else {
    submitComplete({ hoSoHopLe: true });
  }
}


function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return "0 B";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function getFileName(f: any): string {
  if (!f) return "Tài liệu đính kèm";
  if (f.object_key) {
    const parts = f.object_key.split("/");
    const last = parts[parts.length - 1];
    const match = last.match(/^[0-9a-fA-F-]{36}-(.+)$/);
    if (match) return match[1];
    return last;
  }
  if (f.loai) {
    const map: Record<string, string> = {
      ban_ve: "Bản vẽ thiết kế thi công.pdf",
      don: "Đơn đề nghị cấp phép.pdf",
      giay_to_dat: "Giấy tờ chứng minh quyền sử dụng đất.pdf",
    };
    return map[f.loai] || `${f.loai}.pdf`;
  }
  return "Bản vẽ thiết kế thi công.pdf";
}

async function viewFile(f: any) {
  if (!props.userToken) return;
  const fileId = f.file_id || f.id;
  try {
    const resp = await fetch(`/api/v1/files/${fileId}/download`, {
      headers: {
        Authorization: `Bearer ${props.userToken}`,
      },
    });
    if (!resp.ok) {
      notify(`Không mở được tệp (mã lỗi ${resp.status}).`, "loi");
      return;
    }
    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    window.open(url, "_blank");
  } catch (err: any) {
    notify(`Không mở được tệp: ${err.message}`, "loi");
  }
}

// Z-08 & T-01: Lấy ho_so_id từ task variables, ho_so_id hoặc dossiers
const currentHoSoId = computed(() => {
  if (!selectedTask.value) return "";
  const vars = selectedTask.value.variables;
  if (Array.isArray(vars)) {
    const v = vars.find((item: any) => item.name === "ho_so_id" || item.name === "object_id" || item.name === "p_object_id");
    if (v && v.value) return String(v.value);
  }
  if (selectedTask.value.ho_so_id) return String(selectedTask.value.ho_so_id);
  if (props.dossiers && Array.isArray(props.dossiers)) {
    const found = props.dossiers.find(
      (d: any) => (d.process_instance_id && d.process_instance_id === selectedTask.value.processInstanceId) ||
                  d.id === selectedTask.value.processInstanceId || 
                  (selectedTask.value.businessKey && d.ma_ho_so === selectedTask.value.businessKey)
    );
    if (found) return found.id;
  }
  return "";
});

// Z-09: Đồng hồ đếm ngược tính từ han_buoc_at và han_tong_at thật của hồ sơ
const currentDossier = computed(() => {
  if (!currentHoSoId.value || !props.dossiers) return null;
  return props.dossiers.find((d: any) => d.id === currentHoSoId.value) || null;
});

const countdownText = computed(() => {
  const dossier = currentDossier.value;
  const deadlineStr = dossier?.han_tong_at || dossier?.han_buoc_at;
  if (!deadlineStr) return "";
  const t = new Date(deadlineStr);
  if (isNaN(t.getTime())) return "";
  const left = Math.ceil((t.getTime() - Date.now()) / 86400000);
  const ngay = t.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
  if (left < 0) return `Đã quá hạn từ ${ngay}`;
  return `Hạn cuối ${ngay}`;
});

// Đường hạn: 15 ngày làm việc, chia theo thời hạn từng bước trong app.yaml (sla)
const STEPS = [
  { key: "tiep_nhan", label: "Tiếp nhận", days: 3 },
  { key: "phan_cong", label: "Phân công", days: 2 },
  { key: "tham_dinh", label: "Thẩm định", days: 7 },
  { key: "phe_duyet", label: "Phê duyệt", days: 2 },
  { key: "hoan_thanh", label: "Cấp phép", days: 1 },
];
const deadline = computed(() => {
  const total = STEPS.reduce((n, s) => n + s.days, 0);
  const d = currentDossier.value;
  const done = d?.trang_thai === "DA_CAP" || d?.trang_thai === "TU_CHOI";
  const used = Math.min(total, Math.max(1, ngayLamViecDaQua(d?.created_at)));
  const idx = done ? STEPS.length : Math.max(0, STEPS.findIndex((s) => s.key === d?.buoc));
  return {
    total,
    used,
    cols: STEPS.map((s, i) => (i === STEPS.length - 1 ? "minmax(max-content, 1fr)" : `${s.days}fr`)).join(" "),
    steps: STEPS.map((s, i) => ({ ...s, state: i < idx ? "xong" : i === idx ? "dang" : "chua" })),
  };
});

const isOverdue = computed(() => {
  const dossier = currentDossier.value;
  if (!dossier) return false;
  if (dossier.qua_han) return true;
  const deadlineStr = dossier.han_buoc_at || dossier.han_tong_at;
  if (!deadlineStr) return false;
  return new Date(deadlineStr).getTime() < Date.now();
});

function dossierOfTask(t: any): any {
  if (!props.dossiers || !Array.isArray(props.dossiers)) return null;
  const vars = Array.isArray(t.variables) ? t.variables : [];
  const idVar = vars.find((v: any) => v.name === "ho_so_id");
  return (
    props.dossiers.find(
      (d: any) =>
        (idVar && d.id === String(idVar.value)) ||
        (d.process_instance_id && d.process_instance_id === t.processInstanceId)
    ) || null
  );
}

function taskDue(t: any): { text: string; gap: boolean } {
  const d = dossierOfTask(t);
  const v = d?.han_buoc_at || d?.han_tong_at;
  if (!v) return { text: "", gap: false };
  const left = Math.ceil((new Date(v).getTime() - Date.now()) / 86400000);
  if (isNaN(left)) return { text: "", gap: false };
  if (left < 0) return { text: `Quá ${-left} ngày`, gap: true };
  if (left === 0) return { text: "Hết hạn hôm nay", gap: true };
  return { text: `Còn ${left} ngày`, gap: left <= 1 };
}

function isBreakGlass(item: any): boolean {
  return String(item?.action || "").toLowerCase().includes("break_glass");
}

function lyDo(item: any): string {
  const d = item?.detail || {};
  return d.ly_do || d.reason || "";
}

function ngayThang(val: any): string {
  if (!val) return "";
  const d = new Date(val);
  if (isNaN(d.getTime())) return "";
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function isTaskOverdue(t: any): boolean {
  if (!props.dossiers || !Array.isArray(props.dossiers)) return false;
  const d = props.dossiers.find(
    (item: any) =>
      item.process_instance_id === t.processInstanceId ||
      (t.businessKey && item.ma_ho_so === t.businessKey)
  );
  if (!d) return false;
  if (d.qua_han) return true;
  const deadlineStr = d.han_buoc_at || d.han_tong_at;
  if (!deadlineStr) return false;
  return new Date(deadlineStr).getTime() < Date.now();
}

// Z-09 & T-01: Nhật ký kiểm toán thật lấy từ API theo ho_so_id & Danh sách tệp đính kèm
const auditLogs = ref<any[]>([]);
const dossierFiles = ref<any[]>([]);
const loadingFiles = ref(false);

// Đánh giá từng giấy tờ (P1/P3)
const dangDanhGia = ref("");
const lyDoTep = ref("");
const dangLuu = ref(false);
function reviewLabel(f: any): string {
  const st = f.trang_thai_kiem_tra || "cho_kiem_tra";
  if (st === "dat") return "Đạt";
  if (st === "khong_dat") return "Không đạt";
  if (st === "cach_ly") return "Cách ly";
  return "Chờ kiểm tra";
}
function reviewTone(f: any): string {
  const st = f.trang_thai_kiem_tra || "cho_kiem_tra";
  if (st === "dat") return "tt-xanh";
  if (st === "khong_dat") return "tt-do";
  if (st === "cach_ly") return "tt-xam";
  return "tt-vang";
}
function moDanhGiaKhongDat(f: any) {
  dangDanhGia.value = f.id;
  lyDoTep.value = f.ly_do || "";
}
async function reloadDossierFiles() {
  if (!props.userToken || !currentDossier.value) return;
  const resp = await fetch(`/api/v1/rest/v_ho_so_tep?ho_so_id=eq.${currentDossier.value.id}&order=created_at.desc`, {
    headers: { Authorization: `Bearer ${props.userToken}` },
  });
  if (resp.ok) dossierFiles.value = await resp.json();
}
async function reviewFile(f: any, trangThai: "dat" | "khong_dat") {
  if (!props.userToken) return;
  const lyDo = trangThai === "khong_dat" ? lyDoTep.value.trim() : "";
  if (trangThai === "khong_dat" && !lyDo) return;
  dangLuu.value = true;
  try {
    await reviewDossierFile(props.userToken, f.id, trangThai, lyDo);
    dangDanhGia.value = "";
    lyDoTep.value = "";
    await reloadDossierFiles();
    notify(`Đã đánh giá ${f.ten_loai || f.loai || "tệp"}: ${trangThai === "dat" ? "đạt" : "không đạt"}.`);
  } catch (err: any) {
    notify("Không lưu được đánh giá: " + (err?.message || err), "loi");
  } finally {
    dangLuu.value = false;
  }
}

watch(currentHoSoId, async (newId) => {
  if (!newId || !props.userToken) {
    auditLogs.value = [];
    dossierFiles.value = [];
    return;
  }
  // 1. Tải nhật ký kiểm toán
  try {
    const resp = await fetch("/api/v1/rest/rpc/lay_nhat_ky_ho_so", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${props.userToken}`,
      },
      body: JSON.stringify({ p_ho_so_id: newId, p_limit: 50 }),
    });
    if (resp.ok) {
      const data = await resp.json();
      auditLogs.value = Array.isArray(data) ? data : [];
    } else {
      auditLogs.value = [];
    }
  } catch {
    auditLogs.value = [];
  }

  // 2. Tải danh sách tệp đính kèm
  loadingFiles.value = true;
  try {
    const resp = await fetch(`/api/v1/rest/v_ho_so_tep?ho_so_id=eq.${newId}&order=created_at.desc`, {
      headers: {
        Authorization: `Bearer ${props.userToken}`,
      },
    });
    if (resp.ok) {
      dossierFiles.value = await resp.json();
    } else {
      dossierFiles.value = [];
    }
  } catch {
    dossierFiles.value = [];
  } finally {
    loadingFiles.value = false;
  }
}, { immediate: true });

function selectTask(task: any) {
  selectedTask.value = task;
  emit("select-task", task);
}

// Z-07: Gửi kèm taskId của selectedTask, sau khi hoàn thành bỏ chọn nhiệm vụ
function submitComplete(variables: Record<string, any>) {
  if (!selectedTask.value) return;
  const taskId = selectedTask.value.id;
  emit("complete-task", { taskId, variables });
  selectedTask.value = null;
}

// N-03: Ký lại hồ sơ kẹt trạng thái CHO_KY
const isRetrying = ref(false);
const retryMsg = ref("");
const retrySuccess = ref(false);

async function retrySigning(dossier: any) {
  if (!dossier?.process_instance_id || !props.userToken) return;
  isRetrying.value = true;
  retryMsg.value = "";
  try {
    const res = await fetch("/api/v1/flow/hooks/retry", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${props.userToken}`,
      },
      body: JSON.stringify({
        process_instance_id: dossier.process_instance_id,
        task_def: "taskDuyetCapPhep",
      }),
    });
    if (res.ok) {
      retrySuccess.value = true;
      retryMsg.value = "Ký số và cấp giấy phép thành công!";
    } else {
      retrySuccess.value = false;
      const err = await res.json().catch(() => ({}));
      retryMsg.value = err.detail?.loi || "Ký lại thất bại!";
    }
  } catch (e: any) {
    retrySuccess.value = false;
    retryMsg.value = e.message || "Lỗi kết nối khi ký lại";
  } finally {
    isRetrying.value = false;
  }
}
</script>

<style scoped>
.viec {
  display: block;
  width: 100%;
  text-align: left;
  padding: 14px 20px;
  border: 0;
  border-bottom: 1px solid var(--vien-nhat);
  border-left: 3px solid transparent;
  background: transparent;
  color: inherit;
}
.viec:last-child {
  border-bottom: 0;
}
.viec:hover {
  background: var(--mat-2);
  border-left-color: rgb(var(--c-lam) / 0.7);
  padding-left: 24px;
}
.viec {
  transition: background 500ms var(--em), border-color 500ms var(--em), padding 500ms var(--em);
}
.viec-chon,
.viec-chon:hover {
  background: var(--mat-noi);
  border-left-color: rgb(var(--c-cham));
}
.moc {
  border-left: 1px solid var(--vien);
  padding-left: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.moc-dang {
  color: rgb(var(--c-cham));
  font-weight: 600;
  border-left-color: rgb(var(--c-cham));
}

.lua-chon {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.lua-chon input {
  accent-color: rgb(var(--c-cham));
  width: 16px;
  height: 16px;
}
</style>

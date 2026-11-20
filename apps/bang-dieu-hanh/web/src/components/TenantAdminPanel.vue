<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { apiGet, apiPost } from "../api";

interface Tenant {
  tenant: string;
  ten: string;
  ma_dvhc: string | null;
  active: boolean;
  created_at: string;
  so_nguoi_dung: number;
  so_ho_so: number;
}
interface TenantUser {
  sub: string;
  username: string;
  full_name: string;
  email: string | null;
  roles: string[];
  active: boolean;
  created_at: string;
}
interface Vai {
  role: string;
  description: string;
}
interface Isolation {
  tenant: string;
  vai_db: string;
  rls: Record<string, boolean>;
  visible_tenants: string[];
  so_dia_ban_thay_duoc: number;
  so_ho_so_theo_dia_ban: Record<string, number>;
}

const props = defineProps<{ vaiTro: string[] }>();

const laPlatform = computed(() => props.vaiTro.includes("dx:platform-admin"));
const nhanVai = computed(() => (laPlatform.value ? "Quản trị nền tảng" : "Quản trị địa bàn"));

const tenants = ref<Tenant[]>([]);
const users = ref<TenantUser[]>([]);
const vaiList = ref<Vai[]>([]);
const isolation = ref<Isolation | null>(null);
const selected = ref("");
const loading = ref(false);
const loadingUsers = ref(false);
const error = ref("");
const thongBao = ref("");
const dangTao = ref(false);
const dangDoiVai = ref("");
const form = reactive({ tenant: "", ten: "", ma_dvhc: "" });
const vaiChon = reactive<Record<string, string>>({});

const tenantDangChon = computed(() => tenants.value.find((t) => t.tenant === selected.value) || null);
const maTenantHopLe = computed(() => /^[a-z0-9][a-z0-9-]{1,62}$/.test(form.tenant));
const coTheTao = computed(
  () => laPlatform.value && maTenantHopLe.value && form.ten.trim().length > 0 && !dangTao.value,
);

const VAI_HE_THONG = new Set(["default-roles-dxos", "offline_access", "uma_authorization"]);

function vaiHienThi(user: TenantUser): string[] {
  return (user.roles || []).filter((r) => !VAI_HE_THONG.has(r)).sort();
}
function vaiConLai(user: TenantUser): Vai[] {
  const daCo = new Set(user.roles || []);
  return vaiList.value.filter((v) => !daCo.has(v.role));
}
function thongBaoLoi(e: unknown, macDinh: string): void {
  error.value = e instanceof Error ? e.message : macDinh;
}
function xoaThongBao(): void {
  error.value = "";
  thongBao.value = "";
}

async function taiTenants(giuChon = true): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const res = await apiGet<{ items: Tenant[] }>("/admin/tenants");
    tenants.value = res.items;
    if (!giuChon || !tenants.value.some((t) => t.tenant === selected.value)) {
      selected.value = tenants.value[0]?.tenant || "";
    }
    if (selected.value) await taiNguoiDung(selected.value);
  } catch (e) {
    thongBaoLoi(e, "Không tải được danh mục địa bàn");
  } finally {
    loading.value = false;
  }
}

async function taiNguoiDung(tenant: string): Promise<void> {
  loadingUsers.value = true;
  error.value = "";
  try {
    const res = await apiGet<{ tenant: string; items: TenantUser[] }>(
      `/admin/tenants/${encodeURIComponent(tenant)}/users`,
    );
    users.value = res.items;
    for (const u of users.value) {
      const conLai = vaiConLai(u);
      if (!conLai.some((v) => v.role === vaiChon[u.username])) {
        vaiChon[u.username] = conLai[0]?.role || "";
      }
    }
  } catch (e) {
    users.value = [];
    thongBaoLoi(e, "Không tải được người dùng của địa bàn");
  } finally {
    loadingUsers.value = false;
  }
}

async function taiVai(): Promise<void> {
  try {
    vaiList.value = (await apiGet<{ items: Vai[] }>("/admin/roles")).items;
  } catch (e) {
    thongBaoLoi(e, "Không tải được danh sách vai");
  }
}

async function taiCachLy(): Promise<void> {
  try {
    isolation.value = await apiGet<Isolation>("/admin/isolation");
  } catch (e) {
    isolation.value = null;
    thongBaoLoi(e, "Không kiểm tra được cách ly dữ liệu");
  }
}

async function chonTenant(tenant: string): Promise<void> {
  selected.value = tenant;
  xoaThongBao();
  await taiNguoiDung(tenant);
}

async function taoTenant(): Promise<void> {
  if (!coTheTao.value) return;
  dangTao.value = true;
  xoaThongBao();
  try {
    const moi = await apiPost<Tenant>("/admin/tenants", {
      tenant: form.tenant.trim(),
      ten: form.ten.trim(),
      ma_dvhc: form.ma_dvhc.trim() || null,
    });
    thongBao.value = `Đã tạo địa bàn ${moi.ten} (${moi.tenant}).`;
    form.tenant = "";
    form.ten = "";
    form.ma_dvhc = "";
    await taiTenants(false);
    selected.value = moi.tenant;
    await taiNguoiDung(moi.tenant);
    await taiCachLy();
  } catch (e) {
    thongBaoLoi(e, "Không tạo được địa bàn");
  } finally {
    dangTao.value = false;
  }
}

async function doiVai(user: TenantUser, role: string, action: "add" | "remove"): Promise<void> {
  const khoa = `${user.username}:${role}:${action}`;
  dangDoiVai.value = khoa;
  xoaThongBao();
  try {
    const res = await apiPost<{ roles: string[] }>(
      `/admin/tenants/${encodeURIComponent(selected.value)}/users/${encodeURIComponent(user.username)}/roles`,
      { role, action },
    );
    user.roles = res.roles;
    vaiChon[user.username] = vaiConLai(user)[0]?.role || "";
    thongBao.value =
      action === "add"
        ? `Đã gán vai ${role} cho ${user.username}.`
        : `Đã thu hồi vai ${role} của ${user.username}.`;
    await taiCachLy();
  } catch (e) {
    thongBaoLoi(e, "Không đổi được vai");
  } finally {
    dangDoiVai.value = "";
  }
}

function ganVai(user: TenantUser): void {
  const role = vaiChon[user.username];
  if (role) void doiVai(user, role, "add");
}

onMounted(async () => {
  await Promise.all([taiVai(), taiCachLy()]);
  await taiTenants();
});
</script>

<template>
  <section class="space-y-4" aria-labelledby="tieu-de-quan-tri">
    <div class="flex flex-wrap items-start justify-between gap-3 rounded-lg kinh p-4 shadow">
      <div>
        <h1 id="tieu-de-quan-tri" class="text-lg font-semibold">Quản trị địa bàn</h1>
        <p class="mt-1 text-sm chu-phu">
          Quản lý phường, người dùng và vai trò. Vai thật lưu ở Keycloak; danh mục chỉ đồng bộ để tra cứu.
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span class="rounded-full border px-3 py-1 text-xs font-medium">{{ nhanVai }}</span>
        <button class="min-h-[44px] rounded border px-3 py-1 text-sm" :disabled="loading" @click="taiTenants()">
          Tải lại
        </button>
      </div>
    </div>

    <p v-if="error" class="rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-200" role="alert">
      {{ error }}
    </p>
    <p v-if="thongBao" class="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200" role="status">
      {{ thongBao }}
    </p>

    <div class="grid gap-4 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
      <section class="rounded-lg kinh p-4 shadow" aria-labelledby="tieu-de-danh-sach-dia-ban">
        <div class="flex items-center justify-between gap-2">
          <h2 id="tieu-de-danh-sach-dia-ban" class="text-base font-semibold">Địa bàn</h2>
          <span class="text-xs chu-phu">{{ tenants.length }} địa bàn</span>
        </div>

        <p v-if="loading" class="mt-3 text-sm chu-phu" role="status">Đang tải địa bàn…</p>
        <p v-else-if="!tenants.length" class="mt-3 text-sm chu-phu">Chưa có địa bàn nào.</p>
        <ul v-else class="mt-3 space-y-2">
          <li v-for="t in tenants" :key="t.tenant">
            <button
              type="button"
              class="w-full rounded-lg border p-3 text-left transition-colors"
              :class="selected === t.tenant ? 'border-slate-800 bg-slate-50 dark:border-slate-200 dark:bg-slate-800' : 'hover:bg-slate-50 dark:hover:bg-slate-800'"
              :aria-pressed="selected === t.tenant"
              @click="chonTenant(t.tenant)"
            >
              <span class="flex flex-wrap items-center justify-between gap-1">
                <span class="font-medium">{{ t.ten }}</span>
                <span v-if="!t.active" class="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">Tạm dừng</span>
              </span>
              <code class="text-xs chu-phu">{{ t.tenant }}</code>
              <span class="mt-1 block text-xs chu-phu">
                {{ t.so_nguoi_dung }} người dùng · {{ t.so_ho_so }} hồ sơ
                <template v-if="t.ma_dvhc"> · ĐVHC {{ t.ma_dvhc }}</template>
              </span>
            </button>
          </li>
        </ul>

        <form v-if="laPlatform" class="mt-5 border-t pt-4" @submit.prevent="taoTenant">
          <h2 class="text-base font-semibold">Tạo địa bàn mới</h2>
          <div class="mt-2 space-y-2">
            <label class="block text-sm" for="tenant-ma">
              Mã địa bàn
              <input id="tenant-ma" v-model.trim="form.tenant" class="mt-1 w-full rounded border px-2 py-2" placeholder="vd: phuong-c" autocomplete="off" />
            </label>
            <p class="text-xs chu-phu">Chữ thường, số và dấu gạch ngang; bắt đầu bằng chữ hoặc số.</p>
            <label class="block text-sm" for="tenant-ten">
              Tên hiển thị
              <input id="tenant-ten" v-model.trim="form.ten" class="mt-1 w-full rounded border px-2 py-2" placeholder="vd: Phường C" autocomplete="off" />
            </label>
            <label class="block text-sm" for="tenant-dvhc">
              Mã ĐVHC (không bắt buộc)
              <input id="tenant-dvhc" v-model.trim="form.ma_dvhc" class="mt-1 w-full rounded border px-2 py-2" placeholder="vd: 790103" inputmode="numeric" autocomplete="off" />
            </label>
            <button type="submit" class="min-h-[44px] w-full rounded bg-slate-800 px-3 py-2 text-sm text-white disabled:opacity-50" :disabled="!coTheTao">
              {{ dangTao ? "Đang tạo…" : "Tạo địa bàn" }}
            </button>
            <p v-if="form.tenant && !maTenantHopLe" class="text-xs text-rose-700 dark:text-rose-300" role="alert">
              Mã địa bàn chưa đúng định dạng.
            </p>
          </div>
        </form>
        <p v-else class="mt-5 border-t pt-3 text-xs chu-phu">
          Chỉ quản trị nền tảng được tạo địa bàn mới.
        </p>
      </section>

      <section class="rounded-lg kinh p-4 shadow" aria-labelledby="tieu-de-nguoi-dung">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 id="tieu-de-nguoi-dung" class="text-base font-semibold">
              Người dùng{{ tenantDangChon ? ` — ${tenantDangChon.ten}` : "" }}
            </h2>
            <p class="mt-0.5 text-xs chu-phu">
              Gán hoặc thu hồi vai nghiệp vụ; thay đổi có hiệu lực ở lần đăng nhập tiếp theo.
            </p>
          </div>
          <button class="min-h-[44px] rounded border px-3 py-1 text-sm" :disabled="loadingUsers || !selected" @click="taiNguoiDung(selected)">
            Tải người dùng
          </button>
        </div>

        <p v-if="loadingUsers" class="mt-3 text-sm chu-phu" role="status">Đang tải người dùng…</p>
        <p v-else-if="!users.length" class="mt-3 text-sm chu-phu">Địa bàn chưa có người dùng trong danh mục.</p>
        <ul v-else class="mt-3 space-y-3">
          <li v-for="u in users" :key="u.sub" class="rounded-lg border p-3">
            <div class="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p class="m-0 font-medium">{{ u.full_name }}</p>
                <p class="m-0 text-xs chu-phu">{{ u.username }}<template v-if="u.email"> · {{ u.email }}</template></p>
              </div>
              <span class="rounded-full px-2 py-0.5 text-xs" :class="u.active ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200' : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-200'">
                {{ u.active ? "Đang hoạt động" : "Đã khóa" }}
              </span>
            </div>

            <div class="mt-2 flex flex-wrap items-center gap-1" aria-label="Vai hiện có">
              <span v-for="r in vaiHienThi(u)" :key="r" class="inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs">
                {{ r }}
                <button
                  type="button"
                  class="inline-flex h-6 w-6 items-center justify-center rounded-full text-base leading-none hover:bg-rose-100 dark:hover:bg-rose-950"
                  :aria-label="`Thu hồi vai ${r} của ${u.username}`"
                  :disabled="dangDoiVai === `${u.username}:${r}:remove`"
                  @click="doiVai(u, r, 'remove')"
                >×</button>
              </span>
              <span v-if="!vaiHienThi(u).length" class="text-xs chu-phu">Chưa có vai nghiệp vụ.</span>
            </div>

            <div class="mt-2 flex flex-wrap items-end gap-2">
              <label class="text-xs" :for="`vai-${u.username}`">Gán vai
                <select :id="`vai-${u.username}`" v-model="vaiChon[u.username]" class="mt-1 block min-h-[44px] rounded border px-2 py-1 text-sm">
                  <option value="">— Chọn vai —</option>
                  <option v-for="v in vaiConLai(u)" :key="v.role" :value="v.role">{{ v.role }}</option>
                </select>
              </label>
              <button
                type="button"
                class="min-h-[44px] rounded border px-3 py-1 text-sm disabled:opacity-50"
                :disabled="!vaiChon[u.username] || dangDoiVai === `${u.username}:${vaiChon[u.username]}:add`"
                @click="ganVai(u)"
              >Gán</button>
            </div>
          </li>
        </ul>
      </section>
    </div>

    <section class="rounded-lg kinh p-4 shadow" aria-labelledby="tieu-de-cach-ly">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="tieu-de-cach-ly" class="text-base font-semibold">Minh họa cách ly dữ liệu</h2>
          <p class="mt-0.5 text-sm chu-phu">
            Mỗi truy vấn chỉ thấy địa bàn trong token; gọi chéo địa bàn bị API trả 403.
          </p>
        </div>
        <button class="min-h-[44px] rounded border px-3 py-1 text-sm" @click="taiCachLy">Kiểm tra lại</button>
      </div>

      <p v-if="!isolation" class="mt-3 text-sm chu-phu">Chưa có kết quả kiểm tra cách ly.</p>
      <div v-else class="mt-3 grid gap-3 md:grid-cols-3">
        <div class="rounded-lg border p-3">
          <p class="m-0 text-xs chu-phu">Ngữ cảnh token</p>
          <p class="m-0 mt-1 font-medium">{{ isolation.tenant }}</p>
          <p class="m-0 text-xs chu-phu">Vai cơ sở dữ liệu: {{ isolation.vai_db }}</p>
        </div>
        <div class="rounded-lg border p-3">
          <p class="m-0 text-xs chu-phu">RLS</p>
          <p class="m-0 mt-1 text-sm">
            <span class="mr-2 rounded-full px-2 py-0.5 text-xs" :class="isolation.rls.tenants_rls ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200' : 'bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200'">
              tenants: {{ isolation.rls.tenants_rls ? "bật" : "tắt" }}
            </span>
            <span class="rounded-full px-2 py-0.5 text-xs" :class="isolation.rls.tenants_force ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200' : 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200'">
              force: {{ isolation.rls.tenants_force ? "có" : "không" }}
            </span>
          </p>
          <p class="m-0 mt-1 text-xs chu-phu">users_directory: {{ isolation.rls.users_rls ? "bật" : "tắt" }}<template v-if="isolation.rls.users_force"> · force</template></p>
        </div>
        <div class="rounded-lg border p-3">
          <p class="m-0 text-xs chu-phu">Địa bàn truy vấn được</p>
          <p class="m-0 mt-1 font-medium">{{ isolation.so_dia_ban_thay_duoc }}</p>
          <p class="m-0 mt-1 flex flex-wrap gap-1">
            <span v-for="t in isolation.visible_tenants" :key="t" class="rounded-full border px-2 py-0.5 text-xs">{{ t }}</span>
          </p>
        </div>
      </div>
      <p v-if="isolation" class="mt-3 mb-0 text-xs chu-phu">
        Số hồ sơ theo địa bàn nhìn thấy:
        <span v-for="(so, t) in isolation.so_ho_so_theo_dia_ban" :key="t" class="ml-2">{{ t }}: {{ so }}</span>
        <span v-if="!Object.keys(isolation.so_ho_so_theo_dia_ban).length">—</span>
      </p>
    </section>
  </section>
</template>

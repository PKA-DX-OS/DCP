// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Tên đơn vị hiển thị từ mã địa bàn, ví dụ "phuong-a" -> "UBND Phường A". */
export function tenDonVi(tenant: string | undefined | null): string {
  if (!tenant) return "Hệ thống cấp phép";
  const m = /^(phuong|xa|thi-tran)-(.+)$/.exec(tenant);
  if (!m) return tenant;
  const loai = { phuong: "Phường", xa: "Xã", "thi-tran": "Thị trấn" }[m[1] as "phuong" | "xa" | "thi-tran"];
  const ten = m[2]
    .split("-")
    .map((p) => (p.length <= 2 ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1)))
    .join(" ");
  return `UBND ${loai} ${ten}`;
}

const VAI: Record<string, string> = {
  "app:cap-phep:mot-cua": "Cán bộ một cửa",
  "app:cap-phep:tham-dinh": "Thẩm định viên",
  "app:cap-phep:lanh-dao": "Lãnh đạo phường",
  "app:cap-phep:trat-tu-xd": "Cán bộ trật tự xây dựng",
  "app:cap-phep:chu-dau-tu": "Chủ đầu tư",
  "dx:auditor": "Kiểm toán viên",
  "dx:tenant-admin": "Quản trị phường",
  "dx:platform-admin": "Quản trị hệ thống",
};

export function tenVai(role: string): string {
  return VAI[role] || role;
}

/** Vai nghiệp vụ chính để hiện dưới tên người dùng (bỏ các vai kỹ thuật của Keycloak). */
export function vaiChinh(roles: string[] | undefined): string {
  const r = (roles || []).find((x) => VAI[x]);
  return r ? VAI[r] : "Người dùng";
}

const HANH_DONG: Record<string, string> = {
  "ho_so.nop": "Nộp hồ sơ",
  "ho_so.insert": "Tạo hồ sơ",
  "ho_so.update": "Cập nhật hồ sơ",
  "ho_so.tiep_nhan": "Tiếp nhận hồ sơ",
  "ho_so.phan_cong": "Phân công thẩm định",
  "ho_so.bo_sung": "Bổ sung hồ sơ",
  "flow.task_completed": "Hoàn thành bước xử lý",
  "flow.process_started": "Bắt đầu quy trình",
  "break_glass.requested": "Truy cập khẩn",
  "break_glass.request": "Truy cập khẩn",
  "break_glass.approved": "Duyệt truy cập khẩn",
  "break_glass.denied": "Từ chối truy cập khẩn",
  "doc.signed": "Ký số giấy phép",
  "doc.download": "Tải bản gốc giấy phép",
  "giay_phep.issued": "Cấp phép",
  "file.read": "Xem tệp đính kèm",
  "access.denied": "Bị từ chối truy cập",
  "access.granted": "Xem hồ sơ",
  "sla.qua_han": "Quá hạn xử lý",
};

export function tenHanhDong(action: string): string {
  return HANH_DONG[action] || action;
}

const NHIEM_VU: Record<string, string> = {
  taskKiemTraHopLe: "Kiểm tra hồ sơ",
  taskPhanCong: "Phân công thẩm định",
  taskThamDinh: "Thẩm định hồ sơ",
  taskThamDinhNhanh: "Thẩm định nhanh",
  taskThamDinhChuyenSau: "Thẩm định chuyên sâu",
  taskThamDinhDonGian: "Thẩm định đơn giản",
  taskPheDuyet: "Phê duyệt cấp phép",
  taskDuyetCapPhep: "Phê duyệt cấp phép",
  taskPheDuyetTruyCapKhan: "Duyệt truy cập khẩn",
  taskChoBoSung: "Bổ sung hồ sơ",
  taskKiemTraHienTruong: "Kiểm tra hiện trường",
  taskXuLyViPham: "Xử lý vi phạm",
};

export function tenNhiemVu(task: { taskDefinitionKey?: string; name?: string } | null | undefined): string {
  if (!task) return "";
  return (task.taskDefinitionKey && NHIEM_VU[task.taskDefinitionKey]) || task.name || "Nhiệm vụ";
}

const DSAR: Record<string, string> = {
  access: "Cung cấp dữ liệu",
  rectification: "Chỉnh sửa dữ liệu",
  erasure: "Xóa dữ liệu",
  withdraw: "Rút đồng thuận",
};
export function tenYeuCauDuLieu(t: string): string {
  return DSAR[t] || t;
}

/** Che giữa số CCCD: 001099123456 -> 0010****3456 */
export function cheCccd(cccd: string | undefined | null): string {
  if (!cccd) return "";
  const s = String(cccd);
  if (s.includes("*") || s.length < 8) return s;
  return s.slice(0, 4) + "****" + s.slice(-4);
}

/** Số ngày làm việc (thứ Hai - thứ Sáu) đã qua từ ngày nộp, tính cả ngày hiện tại. */
export function ngayLamViecDaQua(from: string | Date | undefined | null, to: Date = new Date()): number {
  if (!from) return 0;
  const d = new Date(from);
  if (isNaN(d.getTime())) return 0;
  d.setHours(0, 0, 0, 0);
  const end = new Date(to);
  end.setHours(0, 0, 0, 0);
  let n = 0;
  while (d <= end) {
    const w = d.getDay();
    if (w !== 0 && w !== 6) n++;
    d.setDate(d.getDate() + 1);
  }
  return n;
}

export function ngayNgan(val: any): string {
  if (!val) return "";
  const d = new Date(val);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function ngayGio(val: any): string {
  if (!val) return "";
  const d = new Date(val);
  if (isNaN(d.getTime())) return "";
  return (
    d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }) +
    " " +
    d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })
  );
}

const BUOC: Record<string, string> = {
  tiep_nhan: "Tiếp nhận",
  phan_cong: "Phân công",
  tham_dinh: "Thẩm định",
  phe_duyet: "Phê duyệt",
  hoan_thanh: "Hoàn thành",
  da_cap: "Đã cấp phép",
};
export function tenBuoc(b: string | undefined | null): string {
  return (b && BUOC[b]) || b || "";
}

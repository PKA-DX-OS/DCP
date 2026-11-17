// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

const MUI_GIO = "Asia/Ho_Chi_Minh";

/** Nhãn tiếng Việt cho mã chỉ số (khớp apps/cap-phep/app.yaml). */
export const NHAN_CHI_SO = {
  ho_so_moi: "Hồ sơ mới trong kỳ",
  ho_so_dang_xu_ly: "Hồ sơ đang xử lý",
  ho_so_qua_han: "Hồ sơ quá hạn",
  thoi_gian_xu_ly_tb: "Thời gian xử lý trung bình",
  truy_cap_tu_choi: "Lượt truy cập bị từ chối",
  phieu_kiem_tra: "Phiếu kiểm tra hiện trường",
  canh_bao_cong_truong: "Cảnh báo vượt ngưỡng công trường",
  vi_pham: "Vụ vi phạm đã kết luận",
};

export function nhanChiSo(code) {
  return NHAN_CHI_SO[code] || code;
}

/** Số nguyên có dấu phân cách hàng nghìn kiểu Việt Nam. */
export function formatSo(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 0 });
}

/** Phần trăm, ví dụ 0.25 -> "25%". */
export function formatPhanTram(value) {
  if (value === null || value === undefined) return "—";
  return Number(value).toLocaleString("vi-VN", { style: "percent", maximumFractionDigits: 1 });
}

/** Số ngày, một chữ số thập phân. */
export function formatNgay(value) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} ngày`;
}

/** Hiển thị giá trị theo đơn vị của chỉ số. */
export function dinhDangGiaTri(metric) {
  if (!metric || metric.value === null || metric.value === undefined) return "—";
  if (metric.unit === "ngày") return formatNgay(metric.value);
  return formatSo(metric.value);
}

/** Thời điểm tính, theo giờ Việt Nam. */
export function formatThoiDiem(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("vi-VN", { timeZone: MUI_GIO });
}
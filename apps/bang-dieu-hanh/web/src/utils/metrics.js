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
  ho_so_fail_quy_hoach: "Hồ sơ không đạt quy hoạch",
  ho_so_dang_nghiem_thu: "Hồ sơ đang nghiệm thu",
  ty_le_dung_han: "Tỷ lệ cấp phép đúng hạn",
};

/** Thứ tự thẻ chỉ số: 8 chỉ số điều hành trước, chỉ số quy hoạch/nghiệm thu sau. */
export const THU_TU_CHI_SO = Object.keys(NHAN_CHI_SO);

export function nhanChiSo(code, ten) {
  return NHAN_CHI_SO[code] || ten || code;
}

/** Sắp chỉ số theo THU_TU_CHI_SO; mã chưa biết xếp cuối theo thứ tự API trả về. */
export function sapXepChiSo(metrics) {
  const vi = (m) => {
    const i = THU_TU_CHI_SO.indexOf(m.code);
    return i < 0 ? THU_TU_CHI_SO.length : i;
  };
  return [...(metrics || [])].map((m, i) => ({ m, i })).sort((a, b) => vi(a.m) - vi(b.m) || a.i - b.i).map((x) => x.m);
}

/** Đơn vị hiển thị gọn: "phần trăm" thành "%". */
export function donViHienThi(unit) {
  return unit === "phần trăm" ? "%" : unit || "";
}

/**
 * Chỉ số thời gian xử lý trung bình: API làm tròn 0.0 khi trung bình dưới một ngày.
 * Hiển thị "< 1" thay vì "0" để không gây hiểu nhầm là chưa có dữ liệu.
 */
export function hienThiGiaTriChiSo(metric) {
  if (!metric) return null;
  if (metric.code === "thoi_gian_xu_ly_tb" && metric.value !== null && metric.value !== undefined && Number(metric.value) === 0) {
    return "< 1";
  }
  return metric.value;
}

/** Có chỉ số thời gian xử lý trung bình đang dưới một ngày hay không. */
export function laThoiGianDuoiNgay(metrics) {
  return (metrics || []).some(
    (m) => m.code === "thoi_gian_xu_ly_tb" && m.value !== null && m.value !== undefined && Number(m.value) === 0,
  );
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
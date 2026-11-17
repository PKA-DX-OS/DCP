// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Dinh dang so theo chuan vi-VN (dau phay la thap phan, dau cham la phan ngan)
 */
export function formatNumberVi(val: any, maximumFractionDigits: number = 2): string {
  if (val === null || val === undefined || isNaN(val)) return "0";
  return new Intl.NumberFormat("vi-VN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: maximumFractionDigits
  }).format(Number(val));
}

/**
 * Dinh dang tien te dong Viet Nam
 */
export function formatCurrency(amount: any): string {
  if (amount === null || amount === undefined || isNaN(amount)) return "0 đ";
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND"
  }).format(Number(amount));
}

/**
 * Dinh dang dien tich m2
 */
export function formatArea(sqm: any): string {
  if (sqm === null || sqm === undefined || isNaN(sqm)) return "0 m²";
  return `${formatNumberVi(sqm, 2)} m²`;
}

/**
 * Che so CCCD de bao ve du lieu ca nhan (Nghi dinh 13/2023/ND-CP)
 * Vi du: 001099123456 -> 001099******
 */
export function maskCccd(cccd: any): string {
  if (!cccd || typeof cccd !== "string") return "";
  const clean = cccd.trim();
  if (clean.length <= 6) return clean;
  return clean.substring(0, 6) + "*".repeat(clean.length - 6);
}

/**
 * Dinh dang thoi gian theo mui gio Asia/Ho_Chi_Minh
 */
export function formatDateVn(dateInput: any): string {
  if (!dateInput) return "";
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(d);
}

/**
 * Tinh so ngay con lai den han xu ly
 */
export function calculateDaysRemaining(deadlineInput: any): { daysRemaining: number; isOverdue: boolean; text: string } {
  if (!deadlineInput) return { daysRemaining: 0, isOverdue: false, text: "Không xác định" };
  const deadline = new Date(deadlineInput);
  const now = new Date();
  const diffMs = deadline.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) {
    return {
      daysRemaining: Math.abs(diffDays),
      isOverdue: true,
      text: `Quá hạn ${Math.abs(diffDays)} ngày`
    };
  } else if (diffDays === 0) {
    return {
      daysRemaining: 0,
      isOverdue: false,
      text: "Đến hạn hôm nay"
    };
  } else {
    return {
      daysRemaining: diffDays,
      isOverdue: false,
      text: `Còn ${diffDays} ngày làm việc`
    };
  }
}

export function formatStatus(status: any): string {
  const map: Record<string, string> = {
    DA_NOP: "Đã nộp",
    CHO_TIEP_NHAN: "Chờ tiếp nhận",
    TIEP_NHAN: "Đã tiếp nhận",
    CAN_BO_SUNG: "Cần bổ sung",
    DUOC_PHAN_CONG: "Đã phân công",
    DANG_THAM_DINH: "Đang thẩm định",
    CHO_DUYET: "Chờ phê duyệt",
    DA_CAP: "Đã cấp phép",
    TU_CHOI: "Từ chối cấp phép",
    CHO_KY: "Chờ ký số",
  };
  return map[String(status)] || String(status || "");
}

export function getStatusBadgeClass(status: any): string {
  const map: Record<string, string> = {
    DA_NOP: "tt tt-lam",
    CHO_TIEP_NHAN: "tt tt-lam",
    TIEP_NHAN: "tt tt-lam",
    DUOC_PHAN_CONG: "tt tt-lam",
    DANG_THAM_DINH: "tt tt-lam",
    CHO_DUYET: "tt tt-lam",
    CAN_BO_SUNG: "tt tt-vang",
    CHO_KY: "tt tt-vang",
    DA_CAP: "tt tt-xanh",
    TU_CHOI: "tt tt-do",
  };
  return map[String(status)] || "tt tt-xam";
}

export function formatDate(val: any): string {
  if (!val) return "—";
  try {
    return new Date(val).toLocaleString("vi-VN");
  } catch {
    return String(val);
  }
}

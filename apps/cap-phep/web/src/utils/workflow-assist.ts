// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { FlowTask, HoSo } from "../types";
import type { WorkloadItem } from "../api/flow";

export type VaiGoiY = "mot-cua" | "tham-dinh" | "lanh-dao" | "trat-tu-xd";
export type LoaiNhap = "nhac_bo_sung" | "tiep_nhan" | "da_cap" | "nhac_viec";

export interface CanBoGoiY {
  sub: string;
  username?: string;
  ho_ten?: string;
  dangXuLy: number;
  tongHoSo: number;
}

export const NHAN_VAI: Record<VaiGoiY, string> = {
  "mot-cua": "Một cửa",
  "tham-dinh": "Thẩm định",
  "lanh-dao": "Lãnh đạo",
  "trat-tu-xd": "Trật tự xây dựng",
};

export const NHAN_NHAP: Record<LoaiNhap, string> = {
  nhac_bo_sung: "Nhắc bổ sung hồ sơ",
  tiep_nhan: "Thông báo tiếp nhận",
  da_cap: "Thông báo đã cấp giấy phép",
  nhac_viec: "Nhắc việc nội bộ",
};

/** Chọn nhóm cán bộ phù hợp với loại việc. */
export function vaiGoiY(taskDefinitionKey?: string | null): VaiGoiY {
  const key = String(taskDefinitionKey || "");
  if (/Duyet|PheDuyet/i.test(key)) return "lanh-dao";
  if (/KiemTraHopLe|ChoBoSung|PhanCong/i.test(key)) return "mot-cua";
  if (/KiemTraHienTruong|HienTruong/i.test(key)) return "trat-tu-xd";
  if (/NghiemThu|HoanCong|KhacPhucMong/i.test(key)) return "tham-dinh";
  if (/ThamDinh|KiemTraQuyHoach/i.test(key)) return "tham-dinh";
  return "tham-dinh";
}

/** Xếp cán bộ ít việc đang xử lý trước; khớp cả sub và username. */
export function xepHangCanBo(canBo: any[], workload: WorkloadItem[]): CanBoGoiY[] {
  return (canBo || [])
    .map((c) => {
      const sub = String(c.sub || c.id || "");
      const username = c.username ? String(c.username) : undefined;
      const w = (workload || []).find((x) => x.user_sub === sub || (username && x.user_sub === username));
      return {
        sub,
        username,
        ho_ten: c.ho_ten || c.full_name || undefined,
        dangXuLy: Number(w?.dang_xu_ly || 0),
        tongHoSo: Number(w?.so_ho_so_duoc_giao || 0),
      };
    })
    .filter((c) => c.sub)
    .sort(
      (a, b) =>
        a.dangXuLy - b.dangXuLy ||
        a.tongHoSo - b.tongHoSo ||
        (a.ho_ten || a.username || "").localeCompare(b.ho_ten || b.username || "", "vi"),
    );
}

export function loaiNhapMacDinh(d: HoSo | null | undefined): LoaiNhap {
  if (d?.trang_thai === "CAN_BO_SUNG") return "nhac_bo_sung";
  if (d?.trang_thai === "DA_CAP") return "da_cap";
  return "tiep_nhan";
}

function ngay(value: string | null | undefined): string {
  if (!value) return "chưa có";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "chưa có";
  return d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/** Sinh văn bản nháp từ dữ liệu hồ sơ; cán bộ sửa và gửi qua kênh chính thức. */
export function taoNhapThongBao(
  loai: LoaiNhap,
  d: HoSo | null | undefined,
  task?: FlowTask | null,
): string {
  const hoTen = d?.ho_ten || "Ông/Bà";
  const ma = d?.ma_ho_so || "…";
  const diaChi = d?.dia_chi_cong_trinh || "…";
  const han = ngay(d?.han_tong_at || d?.han_buoc_at);

  if (loai === "nhac_bo_sung") {
    const lyDo = d?.ly_do_bo_sung?.trim() || "bổ sung giấy tờ theo yêu cầu của cán bộ tiếp nhận";
    return [
      `Kính gửi ${hoTen},`,
      "",
      `Hồ sơ ${ma} tại ${diaChi} đang cần bổ sung: ${lyDo}.`,
      `Đề nghị Ông/Bà bổ sung trước ngày ${han}.`,
      "",
      "Nội dung nháp, cán bộ kiểm tra trước khi gửi.",
    ].join("\n");
  }

  if (loai === "da_cap") {
    return [
      `Kính gửi ${hoTen},`,
      "",
      `Hồ sơ ${ma} tại ${diaChi} đã được cấp giấy phép.`,
      "Ông/Bà có thể tra cứu trên Cổng dịch vụ công hoặc liên hệ Bộ phận Một cửa để nhận kết quả.",
      "",
      "Nội dung nháp, cán bộ kiểm tra trước khi gửi.",
    ].join("\n");
  }

  if (loai === "nhac_viec") {
    const tenViec = task?.name || task?.taskDefinitionKey || "xử lý hồ sơ";
    const hanViec = ngay(task?.dueDate);
    return [
      `Đề nghị cán bộ xử lý việc “${tenViec}” của hồ sơ ${ma} tại ${diaChi}.`,
      `Hạn xử lý: ${hanViec}.`,
      "Vui lòng kiểm tra, cập nhật kết quả và ghi chú nếu có vướng mắc.",
      "",
      "Nội dung nháp, cán bộ kiểm tra trước khi gửi.",
    ].join("\n");
  }

  return [
    `Kính gửi ${hoTen},`,
    "",
    `Hồ sơ ${ma} tại ${diaChi} đã được tiếp nhận và đang được thẩm định.`,
    `Hạn giải quyết dự kiến: ${han}.`,
    "Ông/Bà có thể theo dõi tiến độ tại mục Tự phục vụ.",
    "",
    "Nội dung nháp, cán bộ kiểm tra trước khi gửi.",
  ].join("\n");
}

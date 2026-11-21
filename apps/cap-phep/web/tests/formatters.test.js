// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import {
  formatNumberVi,
  formatCurrency,
  formatArea,
  maskCccd,
  formatDateVn,
  calculateDaysRemaining,
  formatStatus,
  getStatusBadgeClass,
} from "../src/utils/formatters";
import {
  tenDonVi,
  tenVai,
  vaiChinh,
  tenHanhDong,
  tenNhiemVu,
  tenYeuCauDuLieu,
  cheCccd,
  ngayLamViecDaQua,
  ngayNgan,
  tenBuoc,
  tenChiSo,
} from "../src/utils/labels";

const NGAY = 24 * 60 * 60 * 1000;

describe("định dạng số và tiền", () => {
  test("formatNumberVi dùng dấu chấm phân nghìn, dấu phẩy thập phân", () => {
    expect(formatNumberVi(1234567.89)).toBe("1.234.567,89");
    expect(formatNumberVi(0)).toBe("0");
    expect(formatNumberVi(null)).toBe("0");
    expect(formatNumberVi("abc")).toBe("0");
  });

  test("formatCurrency ra tiền VND", () => {
    const s = formatCurrency(500000);
    expect(s).toContain("500.000");
    expect(s).toContain("₫");
    expect(formatCurrency(undefined)).toBe("0 đ");
  });

  test("formatArea thêm đơn vị m²", () => {
    expect(formatArea(120.5)).toBe("120,5 m²");
    expect(formatArea(null)).toBe("0 m²");
  });
});

describe("định dạng ngày và hạn xử lý", () => {
  test("formatDateVn đổi sang giờ Việt Nam (UTC+7)", () => {
    const s = formatDateVn(new Date("2026-11-04T20:30:00Z"));
    expect(s).toContain("05/11/2026");
    expect(s).toContain("03:30");
    expect(formatDateVn("")).toBe("");
    expect(formatDateVn("không phải ngày")).toBe("");
  });

  test("ngayNgan chỉ lấy ngày/tháng/năm", () => {
    expect(ngayNgan("2026-01-09T12:00:00")).toMatch(/09\/01\/2026/);
    expect(ngayNgan(null)).toBe("");
  });

  test("calculateDaysRemaining báo còn hạn, đến hạn và quá hạn", () => {
    const con = calculateDaysRemaining(new Date(Date.now() + 5 * NGAY).toISOString());
    expect(con.isOverdue).toBe(false);
    expect(con.daysRemaining).toBe(5);
    expect(con.text).toBe("Còn 5 ngày làm việc");

    const qua = calculateDaysRemaining(new Date(Date.now() - 2 * NGAY - 1000).toISOString());
    expect(qua.isOverdue).toBe(true);
    expect(qua.text).toBe("Quá hạn 2 ngày");

    expect(calculateDaysRemaining(null).text).toBe("Không xác định");
  });

  test("ngayLamViecDaQua bỏ thứ Bảy, Chủ nhật", () => {
    // Thứ Sáu 06/11/2026 đến thứ Hai 09/11/2026: tính thứ Sáu và thứ Hai
    expect(ngayLamViecDaQua("2026-11-06T09:00:00", new Date("2026-11-09T09:00:00"))).toBe(2);
    expect(ngayLamViecDaQua("2026-11-07T09:00:00", new Date("2026-11-08T09:00:00"))).toBe(0);
    expect(ngayLamViecDaQua(null)).toBe(0);
  });
});

describe("trạng thái hồ sơ", () => {
  test("formatStatus ra nhãn tiếng Việt, mã lạ giữ nguyên", () => {
    expect(formatStatus("DA_NOP")).toBe("Đã nộp");
    expect(formatStatus("CAN_BO_SUNG")).toBe("Cần bổ sung");
    expect(formatStatus("DA_CAP")).toBe("Đã cấp phép");
    expect(formatStatus("TU_CHOI")).toBe("Từ chối cấp phép");
    expect(formatStatus("KHONG_CO")).toBe("KHONG_CO");
    expect(formatStatus(null)).toBe("");
  });

  test("getStatusBadgeClass tô màu theo nhóm trạng thái", () => {
    expect(getStatusBadgeClass("DANG_THAM_DINH")).toBe("tt tt-lam");
    expect(getStatusBadgeClass("CAN_BO_SUNG")).toBe("tt tt-vang");
    expect(getStatusBadgeClass("DA_CAP")).toBe("tt tt-xanh");
    expect(getStatusBadgeClass("TU_CHOI")).toBe("tt tt-do");
    expect(getStatusBadgeClass("KHONG_CO")).toBe("tt tt-xam");
  });
});

describe("nhãn tiếng Việt", () => {
  test("tenDonVi dựng tên UBND từ mã địa bàn", () => {
    expect(tenDonVi("phuong-a")).toBe("UBND Phường A");
    expect(tenDonVi("xa-tan-lap")).toBe("UBND Xã Tan Lap");
    expect(tenDonVi("thi-tran-b")).toBe("UBND Thị trấn B");
    expect(tenDonVi(undefined)).toBe("Hệ thống cấp phép");
    expect(tenDonVi("khac")).toBe("khac");
  });

  test("tenVai và vaiChinh bỏ vai kỹ thuật", () => {
    expect(tenVai("app:cap-phep:tham-dinh")).toBe("Thẩm định viên");
    expect(tenVai("dx:auditor")).toBe("Kiểm toán viên");
    expect(tenVai("offline_access")).toBe("offline_access");
    expect(vaiChinh(["offline_access", "app:cap-phep:mot-cua"])).toBe("Cán bộ một cửa");
    expect(vaiChinh([])).toBe("Người dùng");
  });

  test("tenHanhDong, tenNhiemVu, tenBuoc, tenYeuCauDuLieu", () => {
    expect(tenHanhDong("ho_so.bo_sung")).toBe("Bổ sung hồ sơ");
    expect(tenHanhDong("break_glass.approved")).toBe("Duyệt truy cập khẩn");
    expect(tenHanhDong("x.y")).toBe("x.y");
    expect(tenNhiemVu({ taskDefinitionKey: "taskKiemTraHienTruong" })).toBe("Kiểm tra hiện trường");
    expect(tenNhiemVu({ taskDefinitionKey: "taskLa", name: "Bước lạ" })).toBe("Bước lạ");
    expect(tenNhiemVu(null)).toBe("");
    expect(tenBuoc("tham_dinh")).toBe("Thẩm định");
    expect(tenBuoc(null)).toBe("");
    expect(tenYeuCauDuLieu("erase")).toBe("Xóa dữ liệu");
    expect(tenYeuCauDuLieu("rectify")).toBe("Chỉnh sửa dữ liệu");
  });
});

describe("che số CCCD", () => {
  test("maskCccd giữ 6 số đầu", () => {
    expect(maskCccd("001099123456")).toBe("001099******");
    expect(maskCccd("12345")).toBe("12345");
    expect(maskCccd("")).toBe("");
    expect(maskCccd(1234567)).toBe("");
  });

  test("cheCccd giữ 4 số đầu và 4 số cuối, không che lại", () => {
    expect(cheCccd("001099123456")).toBe("0010****3456");
    expect(cheCccd("0010****3456")).toBe("0010****3456");
    expect(cheCccd("1234567")).toBe("1234567");
    expect(cheCccd(null)).toBe("");
  });
});

describe("tên chỉ số phiếu hậu kiểm", () => {
  test("chỉ số cảm biến và kiểm tra chủ động có tên tiếng Việt", () => {
    expect(tenChiSo("laeq_dba")).toBe("Độ ồn LAeq");
    expect(tenChiSo("kiem_tra_dinh_ky")).toBe("Kiểm tra chủ động");
  });
  test("mã lạ giữ nguyên, thiếu thì ghi Chỉ số", () => {
    expect(tenChiSo("pm10")).toBe("pm10");
    expect(tenChiSo(null)).toBe("Chỉ số");
  });
});

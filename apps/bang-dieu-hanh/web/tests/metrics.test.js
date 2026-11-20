// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import {
  NHAN_CHI_SO,
  nhanChiSo,
  formatSo,
  formatPhanTram,
  formatNgay,
  dinhDangGiaTri,
  formatThoiDiem,
} from "../src/utils/metrics.js";

describe("nhãn chỉ số", () => {
  test("có đúng 8 chỉ số với nhãn tiếng Việt", () => {
    expect(Object.keys(NHAN_CHI_SO)).toHaveLength(8);
    expect(nhanChiSo("ho_so_moi")).toBe("Hồ sơ mới trong kỳ");
    expect(nhanChiSo("vi_pham")).toBe("Vụ vi phạm đã kết luận");
  });

  test("mã chỉ số lạ trả về chính mã", () => {
    expect(nhanChiSo("khong_co")).toBe("khong_co");
  });
});

describe("định dạng số", () => {
  test("formatSo dùng dấu phân cách hàng nghìn và xử lý thiếu giá trị", () => {
    expect(formatSo(1234)).toBe("1.234");
    expect(formatSo(null)).toBe("—");
    expect(formatSo(undefined)).toBe("—");
    expect(formatSo("abc")).toBe("—");
  });

  test("formatPhanTram đổi 0.25 thành 25%", () => {
    expect(formatPhanTram(0.25).replace(/\s/g, "")).toBe("25%");
    expect(formatPhanTram(null)).toBe("—");
  });

  test("formatNgay thêm đơn vị ngày", () => {
    expect(formatNgay(3.5)).toBe("3,5 ngày");
    expect(formatNgay(null)).toBe("—");
  });
});

describe("định dạng theo đơn vị", () => {
  test("dinhDangGiaTri chọn đúng cách hiển thị theo đơn vị", () => {
    expect(dinhDangGiaTri({ unit: "ngày", value: 2 })).toBe("2 ngày");
    expect(dinhDangGiaTri({ unit: "hồ sơ", value: 1500 })).toBe("1.500");
    expect(dinhDangGiaTri({ unit: "hồ sơ", value: null })).toBe("—");
    expect(dinhDangGiaTri(null)).toBe("—");
  });

  test("formatThoiDiem trả thời điểm theo giờ Việt Nam và xử lý lỗi", () => {
    expect(formatThoiDiem(null)).toBe("—");
    expect(formatThoiDiem("không phải ngày")).toBe("—");
    expect(formatThoiDiem("2026-11-16T00:00:00Z")).not.toBe("—");
  });
});

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import {
  NHAN_CHI_SO,
  THU_TU_CHI_SO,
  donViHienThi,
  nhanChiSo,
  sapXepChiSo,
  formatSo,
  formatPhanTram,
  formatNgay,
  dinhDangGiaTri,
  formatThoiDiem,
  hienThiGiaTriChiSo,
  laThoiGianDuoiNgay,
  duongDanChiSo,
  nhanPhamViChiSo,
} from "../src/utils/metrics.js";

test("mọi chỉ số khai báo trong app.yaml đều có nhãn tiếng Việt", () => {
  const yaml = readFileSync(new URL("../../../cap-phep/app.yaml", import.meta.url), "utf-8");
  const phan = yaml.slice(yaml.indexOf("\nmetrics:"));
  const ma = [...phan.matchAll(/^  - code: (\w+)$/gm)].map((x) => x[1]);
  expect(ma.length).toBeGreaterThanOrEqual(11);
  for (const m of ma) expect(NHAN_CHI_SO[m], m).toBeTruthy();
  expect(nhanChiSo("ho_so_moi")).toBe("Hồ sơ mới trong kỳ");
  expect(nhanChiSo("vi_pham")).toBe("Vụ vi phạm đã kết luận");
});

test("mã chỉ số lạ dùng tên từ API, không có thì trả về chính mã", () => {
  expect(nhanChiSo("khong_co", "Tên từ API")).toBe("Tên từ API");
  expect(nhanChiSo("khong_co")).toBe("khong_co");
});

test("thẻ chỉ số xếp theo thứ tự điều hành, mã lạ xếp cuối", () => {
  const api = [{ code: "ty_le_dung_han" }, { code: "la" }, { code: "vi_pham" }, { code: "ho_so_moi" }];
  expect(sapXepChiSo(api).map((m) => m.code)).toEqual(["ho_so_moi", "vi_pham", "ty_le_dung_han", "la"]);
  expect(THU_TU_CHI_SO.slice(0, 2)).toEqual(["ho_so_moi", "ho_so_dang_xu_ly"]);
  expect(donViHienThi("phần trăm")).toBe("%");
  expect(donViHienThi("hồ sơ")).toBe("hồ sơ");
});

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

test("đường dẫn chỉ số điều hành truyền đúng tháng", () => {
  expect(duongDanChiSo("2025-01")).toBe("/metrics?thang=2025-01");
  expect(duongDanChiSo("2026-11")).toBe("/metrics?thang=2026-11");
  expect(duongDanChiSo("")).toBe("/metrics");
  expect(duongDanChiSo(null)).toBe("/metrics");
});

test("chỉ số toàn kỳ được ghi rõ trong nhãn", () => {
  expect(nhanPhamViChiSo({ theo_ky: false }, true)).toBe(" (toàn kỳ)");
  expect(nhanPhamViChiSo({ theo_ky: true }, true)).toBe("");
  expect(nhanPhamViChiSo({ theo_ky: true }, false)).toBe(" (toàn kỳ)");
  expect(nhanPhamViChiSo({}, false)).toBe(" (toàn kỳ)");
});

test("thời gian xử lý trung bình 0 ngày hiển thị là dưới 1 ngày", () => {
  const chiSo = { code: "thoi_gian_xu_ly_tb", value: 0 };
  expect(hienThiGiaTriChiSo(chiSo)).toBe("< 1");
  expect(laThoiGianDuoiNgay([chiSo])).toBe(true);
  expect(hienThiGiaTriChiSo({ code: "thoi_gian_xu_ly_tb", value: 2.5 })).toBe(2.5);
  expect(hienThiGiaTriChiSo({ code: "ho_so_moi", value: 0 })).toBe(0);
  expect(laThoiGianDuoiNgay([{ code: "ho_so_moi", value: 0 }])).toBe(false);
  expect(laThoiGianDuoiNgay(null)).toBe(false);
});
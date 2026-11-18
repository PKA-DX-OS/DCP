// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  NHAN_CHI_SO,
  nhanChiSo,
  formatSo,
  formatPhanTram,
  formatNgay,
  dinhDangGiaTri,
  formatThoiDiem,
} from "../src/utils/metrics.js";

test("có đúng 8 chỉ số với nhãn tiếng Việt", () => {
  assert.equal(Object.keys(NHAN_CHI_SO).length, 8);
  assert.equal(nhanChiSo("ho_so_moi"), "Hồ sơ mới trong kỳ");
  assert.equal(nhanChiSo("vi_pham"), "Vụ vi phạm đã kết luận");
});

test("mã chỉ số lạ trả về chính mã", () => {
  assert.equal(nhanChiSo("khong_co"), "khong_co");
});

test("formatSo dùng dấu phân cách hàng nghìn và xử lý thiếu giá trị", () => {
  assert.equal(formatSo(1234), "1.234");
  assert.equal(formatSo(null), "—");
  assert.equal(formatSo(undefined), "—");
  assert.equal(formatSo("abc"), "—");
});

test("formatPhanTram đổi 0.25 thành 25%", () => {
  assert.equal(formatPhanTram(0.25).replace(/\s/g, ""), "25%");
  assert.equal(formatPhanTram(null), "—");
});

test("formatNgay thêm đơn vị ngày", () => {
  assert.equal(formatNgay(3.5), "3,5 ngày");
  assert.equal(formatNgay(null), "—");
});

test("dinhDangGiaTri chọn đúng cách hiển thị theo đơn vị", () => {
  assert.equal(dinhDangGiaTri({ unit: "ngày", value: 2 }), "2 ngày");
  assert.equal(dinhDangGiaTri({ unit: "hồ sơ", value: 1500 }), "1.500");
  assert.equal(dinhDangGiaTri({ unit: "hồ sơ", value: null }), "—");
  assert.equal(dinhDangGiaTri(null), "—");
});

test("formatThoiDiem trả thời điểm theo giờ Việt Nam và xử lý lỗi", () => {
  assert.equal(formatThoiDiem(null), "—");
  assert.equal(formatThoiDiem("không phải ngày"), "—");
  assert.notEqual(formatThoiDiem("2026-11-16T00:00:00Z"), "—");
});
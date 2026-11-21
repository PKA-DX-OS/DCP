// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import {
  chuanHoaCccd,
  chuanHoaDienThoai,
  loiCccd,
  loiDiaChi,
  loiDienThoai,
  loiDienTich,
  loiHoTen,
  loiSoTang,
  loiThuaDat,
} from "../src/utils/validation";

describe("chuẩn hóa CCCD", () => {
  test("bỏ khoảng trắng", () => {
    expect(chuanHoaCccd(" 0010 9912 3456 ")).toBe("001099123456");
  });
  test("chấp nhận CCCD 12 số", () => {
    expect(loiCccd("001099123456")).toBe("");
  });
  test("chặn CCCD sai độ dài, sai mã tỉnh hoặc toàn số giống nhau", () => {
    expect(loiCccd("123")).toContain("12 chữ số");
    expect(loiCccd("000099123456")).toContain("Mã tỉnh");
    expect(loiCccd("111111111111")).toContain("không hợp lệ");
    expect(loiCccd("")).toContain("Nhập số CCCD");
  });
});

describe("chuẩn hóa và kiểm tra điện thoại", () => {
  test("bỏ khoảng trắng, dấu chấm, gạch nối và đổi +84 thành 0", () => {
    expect(chuanHoaDienThoai("090 123-45.67")).toBe("0901234567");
    expect(chuanHoaDienThoai("+84 90 123 4567")).toBe("0901234567");
  });
  test("chấp nhận di động 10 số và cố định 11 số", () => {
    expect(loiDienThoai("0901234567")).toBe("");
    expect(loiDienThoai("02412345678")).toBe("");
  });
  test("chặn số quá ngắn hoặc sai đầu số", () => {
    expect(loiDienThoai("12345")).toContain("10–11 chữ số");
    expect(loiDienThoai("0112345678")).toContain("10–11 chữ số");
    expect(loiDienThoai("")).toContain("Nhập số điện thoại");
  });
});

describe("kiểm tra các trường còn lại", () => {
  test("họ tên", () => {
    expect(loiHoTen("Nguyễn Văn A")).toBe("");
    expect(loiHoTen("A")).toContain("ít nhất 3");
    expect(loiHoTen("Nguyễn 2")).toContain("chữ số");
  });
  test("địa chỉ", () => {
    expect(loiDiaChi("12 Lê Lợi, Phường Mẫu")).toBe("");
    expect(loiDiaChi("abc")).toContain("ít nhất 5");
  });
  test("thửa đất", () => {
    expect(loiThuaDat("Thửa 12, Tờ 34")).toBe("");
    expect(loiThuaDat("Thửa ABC")).toContain("cần có số");
    expect(loiThuaDat("12")).toContain("quá ngắn");
  });
  test("số tầng", () => {
    expect(loiSoTang(3)).toBe("");
    expect(loiSoTang("5")).toBe("");
    expect(loiSoTang(0)).toContain("1 đến 5");
    expect(loiSoTang(2.5)).toContain("số nguyên");
    expect(loiSoTang(6)).toContain("1 đến 5");
  });
  test("diện tích sàn", () => {
    expect(loiDienTich(120)).toBe("");
    expect(loiDienTich(0)).toContain("lớn hơn 0");
    expect(loiDienTich(100001)).toContain("100.000");
    expect(loiDienTich("abc")).toContain("phải là số");
  });
});

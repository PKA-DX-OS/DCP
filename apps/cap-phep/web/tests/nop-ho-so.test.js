// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test } from "vitest";
import {
  dienTuHoSo,
  docBanNhap,
  formNopCoDuLieu,
  formNopTrong,
  hopNhatFormNop,
  khoaBanNhap,
  luuBanNhap,
  xoaBanNhap,
} from "../src/utils/nop-ho-so";

const HO_SO = {
  id: "00000000-0000-4000-8000-000000000101",
  ma_ho_so: "CP-MAU-000001",
  tenant: "phuong-mau",
  ho_ten: "Nguyễn Văn Mẫu",
  cccd: "001099123456",
  dien_thoai: "0901234567",
  dia_chi_cong_trinh: "12 Đường Mẫu, Phường Mẫu",
  thua_dat: "Thửa 125, Tờ 18",
  so_tang: 3,
  dien_tich_san_m2: 150,
  khu_quan_ly_kien_truc: true,
  trang_thai: "DA_CAP",
  created_at: "2026-11-01T08:00:00+07:00",
  updated_at: "2026-11-01T08:00:00+07:00",
};

const KHOA = khoaBanNhap("u-1");

beforeEach(() => sessionStorage.clear());
afterEach(() => sessionStorage.clear());

describe("bản nháp form nộp hồ sơ", () => {
  test("form mặc định không bị coi là có dữ liệu", () => {
    expect(formNopCoDuLieu(formNopTrong())).toBe(false);
    expect(formNopCoDuLieu(null)).toBe(false);
  });

  test("đổi số tầng hoặc diện tích cũng là có dữ liệu", () => {
    expect(formNopCoDuLieu({ ...formNopTrong(), so_tang: 3 })).toBe(true);
    expect(formNopCoDuLieu({ ...formNopTrong(), dien_tich_san_m2: 150 })).toBe(true);
  });

  test("ghép bản nháp cũ, chuẩn hóa CCCD/điện thoại và bỏ giá trị sai kiểu", () => {
    const f = hopNhatFormNop({
      ho_ten: "  Nguyễn Văn A  ",
      cccd: "0010 9912 3456",
      dien_thoai: "+84 90 123 4567",
      so_tang: "4",
      dien_tich_san_m2: "abc",
      doi_tuong: "to_chuc",
      trong_kcn: true,
      cap_hanh_chinh: "tinh",
    });
    expect(f.ho_ten).toBe("Nguyễn Văn A");
    expect(f.cccd).toBe("001099123456");
    expect(f.dien_thoai).toBe("0901234567");
    expect(f.so_tang).toBe(4);
    expect(f.dien_tich_san_m2).toBe(100);
    expect(f.doi_tuong).toBe("to_chuc");
    expect(f.trong_kcn).toBe(true);
    expect(f.cap_hanh_chinh).toBe("tinh");
  });

  test("lưu, đọc và xóa bản nháp", () => {
    const form = { ...formNopTrong(), ho_ten: "Nguyễn Văn A", cccd: "001099123456" };
    expect(luuBanNhap(sessionStorage, KHOA, form, 1_000)).toBe(true);
    const ban = docBanNhap(sessionStorage, KHOA, 1_500);
    expect(ban?.form.ho_ten).toBe("Nguyễn Văn A");
    expect(ban?.at).toBe(1_000);
    xoaBanNhap(sessionStorage, KHOA);
    expect(docBanNhap(sessionStorage, KHOA, 1_500)).toBeNull();
  });

  test("form trống thì xóa bản nháp cũ", () => {
    sessionStorage.setItem(KHOA, JSON.stringify({ at: Date.now(), form: formNopTrong() }));
    expect(luuBanNhap(sessionStorage, KHOA, formNopTrong())).toBe(false);
    expect(sessionStorage.getItem(KHOA)).toBeNull();
  });

  test("bản nháp quá 24 giờ bị xóa", () => {
    const form = { ...formNopTrong(), ho_ten: "Nguyễn Văn A" };
    luuBanNhap(sessionStorage, KHOA, form, 1_000);
    expect(docBanNhap(sessionStorage, KHOA, 1_000 + 24 * 60 * 60 * 1000 + 1)).toBeNull();
    expect(sessionStorage.getItem(KHOA)).toBeNull();
  });
});

describe("điền lại từ hồ sơ cũ", () => {
  test("điền các ô đang trống và thay giá trị mặc định của số tầng/diện tích", () => {
    const kq = dienTuHoSo(formNopTrong(), HO_SO);
    expect(kq.soO).toBeGreaterThan(0);
    expect(kq.form.ho_ten).toBe(HO_SO.ho_ten);
    expect(kq.form.cccd).toBe(HO_SO.cccd);
    expect(kq.form.dien_thoai).toBe(HO_SO.dien_thoai);
    expect(kq.form.dia_chi_cong_trinh).toBe(HO_SO.dia_chi_cong_trinh);
    expect(kq.form.thua_dat).toBe(HO_SO.thua_dat);
    expect(kq.form.so_tang).toBe(3);
    expect(kq.form.dien_tich_san_m2).toBe(150);
  });

  test("không ghi đè dữ liệu người dùng đã nhập", () => {
    const form = { ...formNopTrong(), ho_ten: "Tên Đã Nhập", dien_thoai: "0912345678" };
    const kq = dienTuHoSo(form, HO_SO);
    expect(kq.form.ho_ten).toBe("Tên Đã Nhập");
    expect(kq.form.dien_thoai).toBe("0912345678");
    expect(kq.form.cccd).toBe(HO_SO.cccd);
  });

  test("bỏ qua CCCD/điện thoại đã bị che", () => {
    const kq = dienTuHoSo(formNopTrong(), { ...HO_SO, cccd: "0010****3456", dien_thoai: "0901***567" });
    expect(kq.form.cccd).toBe("");
    expect(kq.form.dien_thoai).toBe("");
  });
});

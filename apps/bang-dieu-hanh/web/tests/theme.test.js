// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** B-TEST-01: chế độ sáng/tối của bảng điều hành (utils/anhSang.ts). */
import { beforeEach, describe, expect, test, vi } from "vitest";
import { apDungTheme, khoiTaoSomTheme, layCheDoLuu, luuCheDo } from "../src/utils/anhSang";

const heThongToi = (toi) => (window.matchMedia = vi.fn(() => ({ matches: toi })));

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("anhSang", () => {
  test("chưa lưu hoặc lưu sai thì theo hệ thống", () => {
    expect(layCheDoLuu()).toBe("he-thong");
    localStorage.setItem("dxos-bdh-theme", "tim");
    expect(layCheDoLuu()).toBe("he-thong");
  });
  test("lưu rồi đọc lại đúng lựa chọn", () => {
    luuCheDo("toi");
    expect(layCheDoLuu()).toBe("toi");
  });
  test("theo hệ thống: hệ thống tối thì nền tối, sáng thì nền sáng", () => {
    heThongToi(true);
    apDungTheme("he-thong");
    expect(document.documentElement.dataset.theme).toBe("dark");
    heThongToi(false);
    apDungTheme("he-thong");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
  });
  test("chọn cố định thì bỏ qua hệ thống", () => {
    heThongToi(true);
    apDungTheme("sang");
    expect(document.documentElement.dataset.theme).toBe("light");
  });
  test("khởi tạo sớm dùng lựa chọn đã lưu", () => {
    heThongToi(false);
    luuCheDo("toi");
    khoiTaoSomTheme();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});

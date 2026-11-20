// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** B-TEST-01: chế độ sáng/tối (useTheme) theo lựa chọn đã lưu và cài đặt hệ thống. */
import { beforeEach, describe, expect, test, vi } from "vitest";

const KEY = "dxos-giao-dien";

function heThong(sang) {
  const nghe = [];
  const mm = { matches: sang, addEventListener: (_t, fn) => nghe.push(fn) };
  window.matchMedia = vi.fn(() => mm);
  return { mm, doi: (v) => { mm.matches = v; nghe.forEach((fn) => fn()); } };
}

async function napLai() {
  vi.resetModules();
  return import("../src/composables/useTheme");
}

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("useTheme", () => {
  test("chưa chọn: theo hệ thống; hệ thống không sáng thì nền tối", async () => {
    heThong(false);
    const { initTheme, useTheme } = await napLai();
    initTheme();
    expect(useTheme().theme.value).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });

  test("hệ thống đổi sang sáng thì giao diện đổi theo khi người dùng chưa tự chọn", async () => {
    const ht = heThong(false);
    const { initTheme, useTheme } = await napLai();
    initTheme();
    ht.doi(true);
    expect(useTheme().theme.value).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  test("bấm đổi thì lưu lựa chọn và không còn đổi theo hệ thống", async () => {
    const ht = heThong(false);
    const { initTheme, useTheme } = await napLai();
    initTheme();
    const { theme, toggle } = useTheme();
    toggle();
    expect(theme.value).toBe("light");
    expect(localStorage.getItem(KEY)).toBe("light");
    ht.doi(false);
    expect(theme.value).toBe("light");
  });

  test("lựa chọn đã lưu được ưu tiên hơn hệ thống", async () => {
    localStorage.setItem(KEY, "light");
    heThong(false);
    const { initTheme, useTheme } = await napLai();
    initTheme();
    expect(useTheme().theme.value).toBe("light");
  });

  test("giá trị lưu không hợp lệ thì bỏ qua", async () => {
    localStorage.setItem(KEY, "tim");
    heThong(true);
    const { useTheme } = await napLai();
    expect(useTheme().theme.value).toBe("light");
  });
});

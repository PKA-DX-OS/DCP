// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, describe, expect, test, vi } from "vitest";
import { nextTick } from "vue";
import {
  apDungTheme,
  heThongDangToi,
  khoiTaoSomTheme,
  layCheDoLuu,
  luuCheDo,
} from "../src/utils/anhSang";

vi.mock("vue", async (goc) => {
  const that = await goc();
  return { ...that, onMounted: () => {}, onBeforeUnmount: () => {} };
});

const KHOA = "dxos-bdh-theme";

function stubMoiTruong({ luu = null, toi = false } = {}) {
  const store = new Map();
  if (luu !== null) store.set(KHOA, luu);
  const mq = {
    matches: toi,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal("window", {
    localStorage: {
      getItem: (k) => store.get(k) ?? null,
      setItem: (k, v) => store.set(k, v),
    },
    matchMedia: vi.fn(() => mq),
  });
  vi.stubGlobal("document", { documentElement: { dataset: {}, style: {} } });
  return { store, mq };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("lưu và đọc chế độ giao diện", () => {
  test("mặc định theo hệ thống khi chưa có lưu trữ", () => {
    stubMoiTruong();
    expect(layCheDoLuu()).toBe("he-thong");
  });

  test("đọc đúng giá trị hợp lệ và bỏ giá trị lạ", () => {
    stubMoiTruong({ luu: "toi" });
    expect(layCheDoLuu()).toBe("toi");
    stubMoiTruong({ luu: "xanh" });
    expect(layCheDoLuu()).toBe("he-thong");
  });

  test("lỗi localStorage không làm hỏng giao diện", () => {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: () => {
          throw new Error("bị chặn");
        },
        setItem: () => {
          throw new Error("bị chặn");
        },
      },
      matchMedia: () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
    });
    expect(layCheDoLuu()).toBe("he-thong");
    expect(() => luuCheDo("toi")).not.toThrow();
  });
});

describe("áp dụng data-theme", () => {
  test("chế độ tối và sáng gắn đúng data-theme", () => {
    stubMoiTruong();
    apDungTheme("toi");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
    apDungTheme("sang");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
  });

  test("chế độ hệ thống theo prefers-color-scheme", () => {
    stubMoiTruong({ toi: true });
    expect(heThongDangToi()).toBe(true);
    apDungTheme("he-thong");
    expect(document.documentElement.dataset.theme).toBe("dark");
    stubMoiTruong({ toi: false });
    expect(heThongDangToi()).toBe(false);
    apDungTheme("he-thong");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  test("khởi tạo sớm đọc lưu trữ và áp dụng", () => {
    stubMoiTruong({ luu: "toi" });
    khoiTaoSomTheme();
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});

describe("useTheme", () => {
  test("trả ref theo lưu trữ và cập nhật khi đổi", async () => {
    const { store } = stubMoiTruong({ luu: "toi" });
    const { useTheme } = await import("../src/composables/useTheme");
    const { cheDo } = useTheme();
    expect(cheDo.value).toBe("toi");
    cheDo.value = "sang";
    await nextTick();
    expect(store.get(KHOA)).toBe("sang");
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});

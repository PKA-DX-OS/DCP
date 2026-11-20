// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** B-TEST-01: useNotifications nối lại có backoff, xin vé mới, đồng bộ danh sách và đánh dấu đã đọc. */
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

let ve = 0;
const goi = [];
const apiJson = vi.fn(async (path, opts) => {
  goi.push([path, opts?.method || "GET"]);
  if (path === "/events/ticket") return { ticket: `ve-${++ve}` };
  if (path.startsWith("/flow/notifications?")) {
    return {
      items: [
        { id: "a", title: "Hồ sơ mới", body: "", link: null, read_at: null, created_at: null },
        { id: "b", title: "Đã duyệt", body: "", link: null, read_at: "2026-11-20T00:00:00Z", created_at: null },
      ],
      unread: 1,
    };
  }
  return {};
});
const notify = vi.fn();
vi.mock("../src/auth", () => ({ getValidToken: async () => "tok" }));
vi.mock("../src/api/client", () => ({ apiJson: (...a) => apiJson(...a) }));
vi.mock("../src/composables/useToast", () => ({ notify: (...a) => notify(...a) }));
vi.mock("vue", async (goc) => ({ ...(await goc()), onBeforeUnmount: () => {} }));

class FakeES {
  static all = [];
  constructor(url) {
    this.url = url;
    this.listeners = {};
    this.closed = false;
    FakeES.all.push(this);
  }
  addEventListener(ten, fn) {
    (this.listeners[ten] ||= []).push(fn);
  }
  phat(ten, data) {
    for (const fn of this.listeners[ten] || []) fn({ data: JSON.stringify(data) });
  }
  close() {
    this.closed = true;
  }
}
const mo = () => FakeES.all.filter((e) => !e.closed);

beforeEach(() => {
  FakeES.all = [];
  ve = 0;
  goi.length = 0;
  notify.mockClear();
  vi.stubGlobal("EventSource", FakeES);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function khoiDong() {
  const { useNotifications } = await import("../src/composables/useNotifications");
  const tb = useNotifications(() => "sub-mc");
  tb.batDau();
  await vi.advanceTimersByTimeAsync(0);
  return tb;
}

describe("kết nối SSE", () => {
  test("mất kết nối thì thử lại sau 1, 2, 4 giây, mỗi lần một vé mới; mở được thì đặt lại backoff", async () => {
    vi.useFakeTimers();
    const tb = await khoiDong();
    expect(FakeES.all).toHaveLength(1);
    expect(FakeES.all[0].url).toBe("/api/v1/events?ticket=ve-1");
    FakeES.all[0].onopen();
    expect(tb.trangThai.value).toBe("da_ket_noi");

    FakeES.all[0].onerror();
    expect(tb.trangThai.value).toBe("mat_ket_noi");
    expect(mo()).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(999);
    expect(FakeES.all).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(FakeES.all).toHaveLength(2);
    expect(FakeES.all[1].url).toBe("/api/v1/events?ticket=ve-2");

    FakeES.all[1].onerror();
    await vi.advanceTimersByTimeAsync(1999);
    expect(FakeES.all).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(FakeES.all).toHaveLength(3);

    FakeES.all[2].onopen();
    FakeES.all[2].onerror();
    await vi.advanceTimersByTimeAsync(1000);
    expect(FakeES.all).toHaveLength(4);
    expect(mo()).toHaveLength(1);
    tb.dungLai();
  });

  test("backoff tối đa 30 giây", async () => {
    vi.useFakeTimers();
    const tb = await khoiDong();
    for (let i = 0; i < 7; i++) {
      FakeES.all.at(-1).onerror();
      await vi.advanceTimersByTimeAsync(30_000);
    }
    const truoc = FakeES.all.length;
    FakeES.all.at(-1).onerror();
    await vi.advanceTimersByTimeAsync(29_999);
    expect(FakeES.all).toHaveLength(truoc);
    await vi.advanceTimersByTimeAsync(1);
    expect(FakeES.all).toHaveLength(truoc + 1);
    tb.dungLai();
  });

  test("dừng thì đóng kết nối và không nối lại nữa", async () => {
    vi.useFakeTimers();
    const tb = await khoiDong();
    FakeES.all[0].onerror();
    tb.dungLai();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(FakeES.all).toHaveLength(1);
    expect(mo()).toHaveLength(0);
  });
});

describe("danh sách và đã đọc", () => {
  test("bắt đầu thì tải danh sách và số chưa đọc từ máy chủ", async () => {
    vi.useFakeTimers();
    const tb = await khoiDong();
    expect(tb.danhSach.value).toHaveLength(2);
    expect(tb.chuaDoc.value).toBe(1);
    tb.dungLai();
  });

  test("sự kiện của mình thì toast, tải lại danh sách, báo bàn làm việc; của người khác thì bỏ qua", async () => {
    vi.useFakeTimers();
    const tb = await khoiDong();
    const nghe = vi.fn();
    window.addEventListener("dxos:tasks-changed", nghe);
    goi.length = 0;
    FakeES.all[0].phat("notification", { sub: "nguoi-khac", message: "Không phải của tôi" });
    expect(notify).not.toHaveBeenCalled();
    FakeES.all[0].phat("notification", { sub: "sub-mc", message: "Hồ sơ CP-1 cần bổ sung" });
    expect(notify).toHaveBeenCalledWith("Hồ sơ CP-1 cần bổ sung", "tin");
    expect(nghe).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(0);
    expect(goi.some(([p]) => p.startsWith("/flow/notifications?"))).toBe(true);
    window.removeEventListener("dxos:tasks-changed", nghe);
    tb.dungLai();
  });

  test("đánh dấu một thông báo và tất cả", async () => {
    vi.useFakeTimers();
    const tb = await khoiDong();
    await tb.danhDauMot("a");
    expect(tb.chuaDoc.value).toBe(0);
    expect(tb.danhSach.value.find((x) => x.id === "a").read_at).toBeTruthy();
    expect(goi).toContainEqual(["/flow/notifications/a/read", "POST"]);
    await tb.danhDauMot("a");
    expect(tb.chuaDoc.value).toBe(0);
    await tb.danhDauDaDoc();
    expect(goi).toContainEqual(["/flow/notifications/read-all", "POST"]);
    expect(tb.danhSach.value.every((x) => x.read_at)).toBe(true);
    tb.dungLai();
  });
});

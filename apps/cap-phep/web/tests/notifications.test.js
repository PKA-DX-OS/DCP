// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, describe, expect, test, vi } from "vitest";

vi.mock("../src/auth", () => ({ getValidToken: async () => "tok" }));
vi.mock("../src/api/client", () => ({ apiJson: async () => ({ ticket: "ve-1" }) }));
vi.mock("../src/composables/useToast", () => ({ notify: () => {} }));
vi.mock("vue", async (goc) => ({ ...(await goc()), onBeforeUnmount: () => {} }));

// EventSource giả: ghi lại listener theo tên sự kiện để test phát sự kiện như server
class FakeEventSource {
  static last = null;
  constructor(url) {
    this.url = url;
    this.listeners = {};
    this.onmessage = null;
    FakeEventSource.last = this;
  }
  addEventListener(ten, fn) {
    (this.listeners[ten] ||= []).push(fn);
  }
  phat(ten, data) {
    const ev = { data: JSON.stringify(data) };
    if (ten === "message" && this.onmessage) this.onmessage(ev);
    for (const fn of this.listeners[ten] || []) fn(ev);
  }
  close() {}
}

afterEach(() => vi.unstubAllGlobals());

describe("useNotifications", () => {
  test("đếm sự kiện có tên notification từ /api/v1/events", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.stubGlobal("window", { setTimeout, clearTimeout });
    const { useNotifications } = await import("../src/composables/useNotifications");
    const tb = useNotifications(() => "sub-mc");
    tb.batDau();
    await vi.waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    expect(FakeEventSource.last.url).toBe("/api/v1/events?ticket=ve-1");

    FakeEventSource.last.phat("ping", "heartbeat");
    expect(tb.chuaDoc.value).toBe(0);
    FakeEventSource.last.phat("notification", { event: "process_started", business_key: "CP-2026-000001" });
    expect(tb.chuaDoc.value).toBe(1);
    FakeEventSource.last.phat("notification", { event: "task_completed", sub: "nguoi-khac" });
    expect(tb.chuaDoc.value).toBe(1);

    tb.danhDauDaDoc();
    expect(tb.chuaDoc.value).toBe(0);
    tb.dungLai();
  });
});

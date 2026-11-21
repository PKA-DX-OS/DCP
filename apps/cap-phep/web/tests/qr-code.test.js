// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import QRCode from "qrcode";
import QrCodeModal from "../src/components/QrCodeModal.vue";

vi.mock("qrcode", () => ({
  default: { toDataURL: vi.fn(async () => "data:image/png;base64,QRMAU") },
}));

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(QRCode.toDataURL).mockClear();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("QrCodeModal", () => {
  test("tạo QR từ URL và cho tải ảnh", async () => {
    const w = mount(QrCodeModal, {
      props: { url: "https://example.test/kiem-tra/GP-001", ma: "GP-001", tieuDe: "QR tra cứu GP-001" },
      attachTo: document.body,
    });
    await flushPromises();

    expect(QRCode.toDataURL).toHaveBeenCalledWith(
      "https://example.test/kiem-tra/GP-001",
      expect.objectContaining({ width: 280, margin: 1 }),
    );
    expect(w.text()).toContain("GP-001");
    const img = w.get("img");
    expect(img.attributes("src")).toContain("data:image/png;base64,QRMAU");
    expect(w.get('a[download="qr-GP-001.png"]').exists()).toBe(true);
  });
});

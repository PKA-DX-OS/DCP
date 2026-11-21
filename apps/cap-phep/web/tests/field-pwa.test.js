// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import FieldPwaTab from "../src/features/hien-truong/FieldPwaTab.vue";
import { createInspection, fetchCongTrinhNhanh, fetchPhieuKiemTraNhanh } from "../src/api/construction";
import { CHECKLIST_HIEN_TRUONG, taoNhapMoi } from "../src/utils/field-inspection";
import { luuNhap, xoaCacheCongTrinh, xoaTatCaNhap } from "../src/utils/field-drafts";

vi.mock("../src/auth", () => ({
  getUser: vi.fn(async () => ({ profile: { sub: "u-1" }, access_token: "token" })),
  getValidToken: vi.fn(async () => "token"),
  readRoles: vi.fn(() => ["app:cap-phep:trat-tu-xd"]),
}));

vi.mock("../src/api/construction", () => ({
  fetchCongTrinhNhanh: vi.fn(),
  fetchPhieuKiemTraNhanh: vi.fn(),
  createInspection: vi.fn(),
  triggerDemoSensor: vi.fn(),
}));

const CONG_TRINH = { id: "ct-1", ma_cong_trinh: "CT-001", dia_chi: "12 Lê Lợi, Phường Mẫu" };

enableAutoUnmount(afterEach);

async function taoNhapSanSang() {
  const d = taoNhapMoi(CONG_TRINH, Date.now() - 100_000);
  for (const item of CHECKLIST_HIEN_TRUONG) d.checklist[item.key] = "dat";
  d.signature = "data:image/png;base64,abc";
  d.gps = { lat: 10.123456, lng: 106.654321, accuracy: 8 };
  d.ghiChu = "Hiện trường bình thường";
  d.updatedAt = Date.now();
  await luuNhap(d);
  return d;
}

beforeEach(async () => {
  await xoaTatCaNhap();
  await xoaCacheCongTrinh();
  vi.mocked(fetchCongTrinhNhanh).mockResolvedValue([CONG_TRINH]);
  vi.mocked(fetchPhieuKiemTraNhanh).mockResolvedValue([]);
  vi.mocked(createInspection).mockResolvedValue({ id: "p1", ma_phieu: "PK-001" });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("FieldPwaTab", () => {
  test("mở nháp đã lưu trên thiết bị và gửi phiếu khi trực tuyến", async () => {
    await taoNhapSanSang();
    const w = mount(FieldPwaTab, { attachTo: document.body });
    await flushPromises();

    expect(w.text()).toContain("CT-001");
    expect(w.text()).toContain("Checklist hiện trường");

    const nut = w.findAll("button").find((b) => b.text() === "Gửi phiếu");
    expect(nut).toBeTruthy();
    await nut.trigger("click");
    await flushPromises();

    expect(fetchPhieuKiemTraNhanh).toHaveBeenCalledWith("token");
    expect(createInspection).toHaveBeenCalledTimes(1);
    const [, congTrinhId, ghiChu] = vi.mocked(createInspection).mock.calls[0];
    expect(congTrinhId).toBe("ct-1");
    expect(ghiChu).toContain("[PWA hiện trường]");
    expect(ghiChu).toContain("Checklist:");
    expect(w.text()).toContain("Đã gửi");
    expect(w.text()).toContain("PK-001");
  });

  test("cảnh báo xung đột và chỉ gửi khi xác nhận vẫn gửi", async () => {
    await taoNhapSanSang();
    vi.mocked(fetchPhieuKiemTraNhanh).mockResolvedValue([
      {
        id: "p2",
        ma_phieu: "PK-002",
        cong_trinh_id: "ct-1",
        created_at: new Date(Date.now() + 60_000).toISOString(),
      },
    ]);

    const w = mount(FieldPwaTab, { attachTo: document.body });
    await flushPromises();

    await w.findAll("button").find((b) => b.text() === "Gửi phiếu").trigger("click");
    await flushPromises();
    expect(createInspection).not.toHaveBeenCalled();
    expect(w.text()).toContain("Có xung đột dữ liệu");
    expect(w.text()).toContain("PK-002");

    await w.findAll("button").find((b) => b.text() === "Vẫn gửi").trigger("click");
    await flushPromises();
    expect(createInspection).toHaveBeenCalledTimes(1);
  });

  test("ngoại tuyến thì chặn gửi và vẫn giữ nháp", async () => {
    await taoNhapSanSang();
    const cu = window.navigator.onLine;
    Object.defineProperty(window.navigator, "onLine", { value: false, configurable: true });
    try {
      const w = mount(FieldPwaTab, { attachTo: document.body });
      await flushPromises();

      expect(w.text()).toContain("Đang ngoại tuyến");
      const nut = w.findAll("button").find((b) => b.text() === "Gửi phiếu");
      expect(nut.attributes("disabled")).toBeDefined();
      expect(createInspection).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(window.navigator, "onLine", { value: cu, configurable: true });
    }
  });
});

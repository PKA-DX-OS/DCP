// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import DossierWarnings from "../src/components/DossierWarnings.vue";
import { fetchDossierWarnings } from "../src/api/planning";

vi.mock("../src/auth", () => ({
  readRoles: vi.fn(() => []),
}));

vi.mock("../src/api/planning", () => ({
  fetchDossierWarnings: vi.fn(),
  confirmDossierWarnings: vi.fn(),
}));

const DU_LIEU = {
  items: [
    {
      ma: "so_tang_nguong",
      severity: "warning",
      reason: "Số tầng lớn hơn ngưỡng cấu hình 5; cần kiểm tra thêm.",
      legal_citation_key: "LXD135-TOANVAN",
    },
  ],
  xac_nhan_at: null,
  ghi_chu: null,
};

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(fetchDossierWarnings).mockResolvedValue(structuredClone(DU_LIEU));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("DossierWarnings — quyền xác nhận", () => {
  test("trật tự xây dựng chỉ xem, không thấy nút xác nhận", async () => {
    const w = mount(DossierWarnings, {
      props: {
        dossier: { id: "11111111-1111-4111-8111-111111111111" },
        token: "token",
        vaiTro: ["app:cap-phep:trat-tu-xd"],
      },
    });
    await flushPromises();

    expect(w.find("#btn-confirm-warnings").exists()).toBe(false);
    expect(w.text()).toContain("Chỉ cán bộ một cửa, thẩm định hoặc lãnh đạo được xác nhận cảnh báo");
  });

  test("thẩm định viên thấy nút xác nhận và ghi chú", async () => {
    const w = mount(DossierWarnings, {
      props: {
        dossier: { id: "11111111-1111-4111-8111-111111111111" },
        token: "token",
        vaiTro: ["app:cap-phep:tham-dinh"],
      },
    });
    await flushPromises();

    expect(w.find("#btn-confirm-warnings").exists()).toBe(true);
    expect(w.find("#btn-confirm-warnings").text()).toBe("Xác nhận cảnh báo");
  });
});

// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import CatalogPanel from "../src/components/data/CatalogPanel.vue";
import {
  fetchCatalogAsset,
  fetchCatalogAssets,
  fetchCatalogContracts,
} from "../src/api/catalog";

vi.mock("../src/api/catalog", () => ({
  fetchCatalogAssets: vi.fn(),
  fetchCatalogAsset: vi.fn(),
  fetchCatalogContracts: vi.fn(),
}));

const ASSETS = [
  {
    asset: "app_cap_phep.ho_so",
    domain: "ho_so",
    description: "Hồ sơ đề nghị cấp giấy phép xây dựng",
    owner: "Sở Xây dựng",
    steward: "dx:data-steward",
    classification: "pii",
    retention: "10_nam",
    freshness_sla: "5m",
    last_updated: "2026-11-21T13:44:39Z",
    version: "1",
    dq_score: 88.2,
  },
  {
    asset: "core.audit_log",
    domain: "audit",
    description: "Nhật ký kiểm toán chuỗi băm",
    owner: "Quản trị nền tảng",
    steward: "dx:auditor",
    classification: "sensitive",
    retention: "vinh_vien",
    freshness_sla: "realtime",
    last_updated: "2026-11-21T13:44:39Z",
    version: "1",
    dq_score: 30.9,
  },
  {
    asset: "core.lineage_events",
    domain: "audit",
    description: "Sự kiện phả hệ dữ liệu",
    owner: "Quản trị nền tảng",
    steward: null,
    classification: "internal",
    retention: "5_nam",
    freshness_sla: "realtime",
    last_updated: "2026-11-21T13:44:39Z",
    version: "1",
    dq_score: null,
  },
];

const DETAIL = {
  ...ASSETS[0],
  columns: [
    { name: "id", type: "uuid", classification: "pii", description: null, masked_in_api: false },
    { name: "ma_ho_so", type: "text", classification: "internal", description: "Mã hồ sơ", masked_in_api: false },
  ],
};

const CONTRACTS = [
  {
    asset: "app_cap_phep.ho_so",
    version: "1",
    json_schema: { type: "object" },
    sla: { freshness: "realtime", availability_pct: 99.5 },
    consumers: ["cap-phep web", "metrics-api"],
    effective_from: "2026-11-21T13:44:45Z",
  },
];

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(fetchCatalogAssets).mockResolvedValue(structuredClone(ASSETS));
  vi.mocked(fetchCatalogAsset).mockResolvedValue(structuredClone(DETAIL));
  vi.mocked(fetchCatalogContracts).mockResolvedValue(structuredClone(CONTRACTS));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("CatalogPanel", () => {
  test("hiện tài sản thật, chủ quản, phân loại và điểm DQ", async () => {
    const w = mount(CatalogPanel);
    await flushPromises();

    expect(w.text()).toContain("app_cap_phep.ho_so");
    expect(w.text()).toContain("Sở Xây dựng");
    expect(w.text()).toContain("Dữ liệu cá nhân");
    expect(w.text()).toContain("88,2");
    expect(w.text()).toContain("core.audit_log");
    expect(w.text()).toContain("vinh_vien");
    expect(fetchCatalogAssets).toHaveBeenCalledWith({ domain: undefined, classification: undefined });
  });

  test("chọn tài sản xem cột và hợp đồng dữ liệu", async () => {
    const w = mount(CatalogPanel);
    await flushPromises();

    const nutTaiSan = w.findAll("button").find((b) => b.text() === "app_cap_phep.ho_so");
    expect(nutTaiSan).toBeTruthy();
    await nutTaiSan.trigger("click");
    await flushPromises();

    expect(fetchCatalogAsset).toHaveBeenCalledWith("app_cap_phep.ho_so");
    expect(fetchCatalogContracts).toHaveBeenCalledWith("app_cap_phep.ho_so");
    expect(w.text()).toContain("Cột dữ liệu");
    expect(w.text()).toContain("ma_ho_so");
    expect(w.text()).toContain("Hợp đồng dữ liệu");
    expect(w.text()).toContain("Phiên bản 1");
    expect(w.text()).toContain("cap-phep web");
    expect(w.text()).toContain("99.5%");
  });

  test("lọc phân loại gọi API và vẫn giữ đủ lựa chọn miền", async () => {
    const w = mount(CatalogPanel);
    await flushPromises();

    const chonPhanLoai = w.findAll("select")[1];
    await chonPhanLoai.setValue("sensitive");
    await flushPromises();

    expect(fetchCatalogAssets).toHaveBeenLastCalledWith({
      domain: undefined,
      classification: "sensitive",
    });
    const options = w.findAll("select")[0].findAll("option").map((o) => o.text());
    expect(options).toContain("Hồ sơ");
    expect(options).toContain("Nhật ký");
  });

  test("lỗi API hiện thông báo và nút thử lại", async () => {
    vi.mocked(fetchCatalogAssets).mockRejectedValue(new Error("403 Không có quyền"));
    const w = mount(CatalogPanel);
    await flushPromises();

    expect(w.text()).toContain("Không tải được danh mục");
    expect(w.text()).toContain("403 Không có quyền");
    expect(w.findAll("button").some((b) => b.text() === "Thử lại")).toBe(true);
  });
});

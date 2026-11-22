// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import DataQualityPanel from "../src/components/data/DataQualityPanel.vue";
import {
  fetchDqIssues,
  fetchDqRules,
  fetchDqSummary,
  resolveDqIssue,
} from "../src/api/data-quality";

vi.mock("../src/api/data-quality", () => ({
  fetchDqSummary: vi.fn(),
  fetchDqRules: vi.fn(),
  fetchDqIssues: vi.fn(),
  resolveDqIssue: vi.fn(),
}));

const SUMMARY = {
  run_id: "11111111-1111-4111-8111-111111111111",
  computed_at: "2026-11-22T12:18:54Z",
  overall_score: 45.8,
  domains: [
    { domain: "ho_so", score: 88.2, rules: 6, failed_rules: 2, open_issues: 325 },
    { domain: "audit", score: 30.9, rules: 1, failed_rules: 1, open_issues: 17636 },
  ],
};

const RULES = [
  {
    code: "DQ-GP-02",
    domain: "giay_phep",
    dimension: "consistency",
    severity: "critical",
    description: "Hồ sơ đã cấp phải có giấy phép",
    owner: "Lãnh đạo phường",
    enabled: true,
    last_result: { total: 135, failed: 26, score: 80.7 },
  },
];

const ISSUES = {
  items: [
    {
      id: "i1",
      rule_code: "DQ-GP-02",
      domain: "giay_phep",
      entity_type: "ho_so",
      entity_id: "h1",
      field: "trang_thai",
      severity: "critical",
      status: "open",
      assigned_to: null,
      note: null,
      created_at: "2026-11-21T13:44:55Z",
      resolved_at: null,
      dossier_id: "h1",
    },
  ],
  page: 1,
  page_size: 20,
  total: 1,
};

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(fetchDqSummary).mockResolvedValue(structuredClone(SUMMARY));
  vi.mocked(fetchDqRules).mockResolvedValue(structuredClone(RULES));
  vi.mocked(fetchDqIssues).mockResolvedValue(structuredClone(ISSUES));
  vi.mocked(resolveDqIssue).mockResolvedValue({ ...structuredClone(ISSUES.items[0]), status: "resolved" });
});

afterEach(() => {
  vi.clearAllMocks();
});

function moManHinh(vaiTro = ["dx:tenant-admin"]) {
  return mount(DataQualityPanel, { props: { vaiTro }, attachTo: document.body });
}

describe("DataQualityPanel", () => {
  test("hiện điểm tổng, điểm miền và vấn đề thật", async () => {
    const w = moManHinh();
    await flushPromises();

    expect(w.text()).toContain("45,8");
    expect(w.text()).toContain("Hồ sơ");
    expect(w.text()).toContain("DQ-GP-02");
    expect(w.text()).toContain("Nghiêm trọng");
    expect(fetchDqIssues).toHaveBeenCalledWith(
      expect.objectContaining({ status: "open", page: 1, page_size: 20 }),
    );
  });

  test("quản trị dữ liệu đóng được vấn đề và ghi audit", async () => {
    const w = moManHinh();
    await flushPromises();

    await w.findAll("button").find((b) => b.text() === "Xử lý").trigger("click");
    await w.get('input[placeholder^="Ví dụ"]').setValue("Đã bổ sung giấy phép");
    await w.findAll("button").find((b) => b.text() === "Đóng vấn đề").trigger("click");
    await flushPromises();

    expect(resolveDqIssue).toHaveBeenCalledWith("i1", "resolved", "Đã bổ sung giấy phép");
    expect(w.text()).toContain("Đã đóng vấn đề và ghi audit");
  });

  test("cán bộ nghiệp vụ chỉ xem, không có nút xử lý", async () => {
    const w = moManHinh(["app:cap-phep:tham-dinh"]);
    await flushPromises();

    expect(w.text()).toContain("Vấn đề dữ liệu");
    expect(w.findAll("button").some((b) => b.text() === "Xử lý")).toBe(false);
  });
});

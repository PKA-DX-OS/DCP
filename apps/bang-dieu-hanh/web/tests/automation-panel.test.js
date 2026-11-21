// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import AutomationMetricsPanel from "../src/components/automation/AutomationMetricsPanel.vue";
import { taiHieuQua } from "../src/api/automation";

vi.mock("../src/api/automation", () => ({
  taiHieuQua: vi.fn(),
}));

const MOCK_V11 = {
  computed_at: "2026-11-21T00:00:00+07:00",
  period: { from: null, to: null },
  baseline_label: "v1.1",
  so_ho_so: 0,
  metrics: [
    {
      key: "thao_tac_thu_cong_tb",
      label: "Thao tác thủ công / hồ sơ",
      unit: "",
      better: "lower",
      baseline: 8.14,
      current: null,
      delta_pct: null,
      source: "core.audit_log",
    },
    {
      key: "ty_le_tu_phuc_vu_pct",
      label: "Thao tác do chủ đầu tư tự làm",
      unit: "%",
      better: "higher",
      baseline: 29.6,
      current: null,
      delta_pct: null,
      source: "core.audit_log",
    },
  ],
  ghi_chu: ["Chưa có API /api/v1/automation/metrics. Đang hiển thị mốc đo v1.1; không phải số hiện tại."],
};

const CO_SO = {
  computed_at: "2026-11-21T09:00:00+07:00",
  period: { from: "2026-11-01", to: "2026-11-30" },
  baseline_label: "v1.1",
  so_ho_so: 12,
  metrics: [
    {
      key: "thao_tac_thu_cong_tb",
      label: "Thao tác thủ công / hồ sơ",
      unit: "",
      better: "lower",
      baseline: 8.14,
      current: 6.5,
      delta_pct: -20.1,
      source: "core.audit_log",
    },
  ],
};

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(taiHieuQua).mockResolvedValue({ data: MOCK_V11, source: "mock" });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AutomationMetricsPanel", () => {
  test("chưa có API thì ghi rõ là mốc v1.1, không hiện số hiện tại", async () => {
    const w = mount(AutomationMetricsPanel);
    await flushPromises();

    expect(w.text()).toContain("Chưa có API chỉ số hiệu quả");
    expect(w.text()).toContain("8,14");
    expect(w.text()).toContain("29,6%");
    expect(w.text()).toContain("Chưa có số hiện tại");
    expect(w.text()).not.toContain("Số đo thật");
  });

  test("có API thì hiện số hiện tại và chiều cải thiện", async () => {
    vi.mocked(taiHieuQua).mockResolvedValue({ data: CO_SO, source: "api" });

    const w = mount(AutomationMetricsPanel);
    await flushPromises();

    expect(w.text()).toContain("Số đo thật");
    expect(w.text()).toContain("6,5");
    expect(w.text()).toContain("-20,1% so với mốc");
    expect(w.text()).toContain("12 hồ sơ");
  });

  test("đổi tháng thì gọi API đúng khoảng ngày", async () => {
    const w = mount(AutomationMetricsPanel, { props: { thang: "2026-11" } });
    await flushPromises();
    expect(taiHieuQua).toHaveBeenLastCalledWith("2026-11-01", "2026-11-30");

    await w.setProps({ thang: "2026-02" });
    await flushPromises();
    expect(taiHieuQua).toHaveBeenLastCalledWith("2026-02-01", "2026-02-28");
  });
});

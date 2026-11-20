// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** B-TEST-01: thẻ chỉ số của bảng điều hành. */
import { describe, expect, test } from "vitest";
import { mount } from "@vue/test-utils";
import KpiCard from "../src/components/KpiCard.vue";

describe("KpiCard", () => {
  test("hiện giá trị theo định dạng Việt Nam kèm đơn vị", () => {
    const w = mount(KpiCard, { props: { label: "Hồ sơ mới trong kỳ", value: 1234, unit: "hồ sơ" } });
    expect(w.text()).toContain("Hồ sơ mới trong kỳ");
    expect(w.text()).toContain("1.234");
    expect(w.text()).toContain("hồ sơ");
  });
  test("không có số liệu thì hiện gạch, không hiện đơn vị, không vẽ sparkline", () => {
    const w = mount(KpiCard, { props: { label: "Thời gian xử lý", value: null, unit: "ngày", series: [5] } });
    expect(w.text()).toContain("—");
    expect(w.text()).not.toContain("ngày");
    expect(w.find("svg").exists()).toBe(false);
  });
  test("xu hướng tăng, giảm, đứng yên có mũi tên riêng", () => {
    expect(mount(KpiCard, { props: { label: "x", value: 1, trend: 12.34 } }).text()).toContain("▲ 12,3%");
    expect(mount(KpiCard, { props: { label: "x", value: 1, trend: -5 } }).text()).toContain("▼ 5%");
    expect(mount(KpiCard, { props: { label: "x", value: 1, trend: 0 } }).text()).toContain("■ 0%");
  });
  test("có từ hai điểm thì vẽ sparkline có nhãn cho trình đọc màn hình", () => {
    const w = mount(KpiCard, { props: { label: "x", value: 3, series: [1, 4, 2] } });
    const svg = w.get("svg");
    expect(svg.attributes("aria-label")).toBe("Xu hướng gần đây");
    expect(w.get("polyline").attributes("points").split(" ")).toHaveLength(3);
  });
  test("bấm thẻ phát select để xem phả hệ", async () => {
    const w = mount(KpiCard, { props: { label: "x", value: 3 } });
    await w.trigger("click");
    expect(w.emitted("select")).toHaveLength(1);
  });
});

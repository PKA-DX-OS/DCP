// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { readFileSync } from "node:fs";
import { afterEach, describe, expect, test } from "vitest";
import { enableAutoUnmount, mount } from "@vue/test-utils";
import { nextTick } from "vue";
import axe from "axe-core";
import HelpDrawer from "../src/components/HelpDrawer.vue";

enableAutoUnmount(afterEach);

describe("trợ giúp và tiếp cận", () => {
  test("drawer có dialog, tiêu đề, phím tắt và đóng bằng Esc", async () => {
    const w = mount(HelpDrawer, { attachTo: document.body });

    expect(w.get('[role="dialog"]').attributes("aria-modal")).toBe("true");
    expect(w.get("#tieu-de-tro-giup").text()).toContain("Trợ giúp");
    expect(w.text()).toContain("Ctrl / Cmd + K");
    expect(w.text()).toContain("F1");
    await nextTick();
    expect(document.activeElement?.getAttribute("aria-label")).toBe("Đóng trợ giúp");

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(w.emitted("close")).toHaveLength(1);
  });

  test("không có vi phạm axe serious/critical trong drawer", async () => {
    const w = mount(HelpDrawer, { attachTo: document.body });
    const kq = await axe.run(w.element, {
      rules: { "color-contrast": { enabled: false } },
    });
    const nang = kq.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(nang.map((v) => v.id)).toEqual([]);
  });

  test("Navbar công bố phím tắt tìm kiếm và trợ giúp", () => {
    const navbar = readFileSync("src/components/Navbar.vue", "utf8");
    expect(navbar).toContain('aria-keyshortcuts="Control+K Meta+K"');
    expect(navbar).toContain('aria-keyshortcuts="F1"');
    expect(navbar).toContain('aria-label="Trợ giúp và phím tắt"');

    const app = readFileSync("src/App.vue", "utf8");
    expect(app).toContain('e.key === "F1"');
    expect(app).toContain("<HelpDrawer");
  });
});

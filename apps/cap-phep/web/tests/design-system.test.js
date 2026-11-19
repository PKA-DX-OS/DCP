// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { readFileSync, readdirSync } from "node:fs";
import { describe, expect, test } from "vitest";
import {
  badgeClasses,
  buttonClasses,
  fieldClasses,
  pageCount,
  pageItems,
  roleLabel,
  roleTone,
  statusTone,
  trendPercent,
} from "../src/design-system/variants";

const DS = new URL("../src/design-system/", import.meta.url);

describe("buttonClasses", () => {
  test("mỗi variant dùng token ds, không mã màu cứng", () => {
    for (const v of ["primary", "secondary", "ghost", "danger"]) {
      const c = buttonClasses(v, "md");
      expect(c).toMatch(/ds-/);
      expect(c).not.toMatch(/#[0-9a-f]{3,6}/i);
    }
  });
  test("size md và lg đủ vùng chạm 44px, block thêm w-full", () => {
    expect(buttonClasses("primary", "md")).toContain("h-11");
    expect(buttonClasses("primary", "lg")).toContain("h-12");
    expect(buttonClasses("primary", "md", true)).toContain("w-full");
    expect(buttonClasses("primary", "md", false)).not.toContain("w-full");
  });
  test("trạng thái disabled có kiểu riêng và focus nhìn thấy được", () => {
    const c = buttonClasses();
    expect(c).toContain("disabled:opacity-50");
    expect(c).toContain("ds-focus");
  });
});

describe("fieldClasses và badgeClasses", () => {
  test("ô lỗi viền đỏ, ô thường viền xám", () => {
    expect(fieldClasses("md", true)).toContain("border-ds-danger");
    expect(fieldClasses("md", false)).toContain("border-ds-border");
  });
  test("mỗi tông nhãn có màu riêng", () => {
    const tones = ["neutral", "brand", "success", "warning", "danger", "info", "gold"];
    const set = new Set(tones.map((t) => badgeClasses(t)));
    expect(set.size).toBe(tones.length);
    expect(badgeClasses("danger", "sm")).toContain("text-ds-xs");
  });
});

describe("statusTone", () => {
  test.each([
    ["DA_CAP", "success"],
    ["TU_CHOI", "danger"],
    ["QUA_HAN", "danger"],
    ["CAN_BO_SUNG", "warning"],
    ["CHO_KY", "warning"],
    ["DANG_THAM_DINH", "info"],
    ["CHO_TIEP_NHAN", "info"],
    ["da-nop", "info"],
    ["pass", "success"],
    ["", "neutral"],
    [null, "neutral"],
    ["KHONG_BIET", "neutral"],
  ])("%s -> %s", (s, tone) => {
    expect(statusTone(s)).toBe(tone);
  });
  test("so khớp nguyên mã, không bắt nhầm một phần", () => {
    expect(statusTone("CAP_NHAT")).toBe("neutral");
    expect(statusTone("UPDATED")).toBe("neutral");
  });
});

describe("vai", () => {
  test("vai nền tảng tô vàng, vai app tô thương hiệu", () => {
    expect(roleTone("dx:auditor")).toBe("gold");
    expect(roleTone("app:cap-phep:tham-dinh")).toBe("brand");
    expect(roleLabel("app:cap-phep:tham-dinh")).toBe("tham dinh");
  });
});

describe("phân trang", () => {
  test("ít trang thì hiện hết", () => {
    expect(pageItems(50, 20, 1)).toEqual([1, 2, 3]);
  });
  test("nhiều trang thì có dấu … và luôn có trang đầu, cuối", () => {
    expect(pageItems(243, 20, 6)).toEqual([1, "…", 5, 6, 7, "…", 13]);
    expect(pageItems(243, 20, 1)).toEqual([1, 2, "…", 13]);
    expect(pageItems(243, 20, 13)).toEqual([1, "…", 12, 13]);
  });
  test("khoảng trống một trang thì hiện số trang thay vì …", () => {
    expect(pageItems(243, 20, 4)).toEqual([1, 2, 3, 4, 5, "…", 13]);
  });
  test("trang ngoài phạm vi bị kẹp, tổng 0 vẫn có một trang", () => {
    expect(pageItems(0, 20, 5)).toEqual([1]);
    expect(pageCount(0, 20)).toBe(1);
    expect(pageCount(41, 20)).toBe(3);
  });
});

describe("trendPercent", () => {
  test("tính % thay đổi, làm tròn một chữ số", () => {
    expect(trendPercent(110, 100)).toBe(10);
    expect(trendPercent(2, 3)).toBe(-33.3);
  });
  test("không so được thì null", () => {
    expect(trendPercent(5, 0)).toBeNull();
    expect(trendPercent(null, 3)).toBeNull();
    expect(trendPercent(3, undefined)).toBeNull();
    expect(trendPercent(0, 0)).toBe(0);
  });
});

describe("token và component", () => {
  const tokens = readFileSync(new URL("tokens.css", DS), "utf8");
  test("theo giao diện kính sẵn có: cùng bảng màu style.css, bề mặt kính có làm mờ", () => {
    const style = readFileSync(new URL("../style.css", DS), "utf8");
    expect(style).toContain("--c-lam: 96 165 250;");
    expect(tokens).toContain("--ds-brand: 96 165 250;");
    expect(tokens).toContain("--ds-success: 134 239 172;");
    expect(tokens).toMatch(/\.ds-glass \{[^}]*background: var\(--kinh\);[^}]*backdrop-filter: blur/);
    expect(tokens).toMatch(/\.ds-hop \{[^}]*background: var\(--mat-noi\);/);
    expect(tokens).toContain("prefers-reduced-transparency");
  });
  test("thang chữ, khoảng cách và bo góc đủ bậc", () => {
    for (const px of [12, 13, 14, 16, 20, 24, 32]) expect(tokens).toContain(`: ${px}px;`);
    for (const px of [4, 8, 12, 16, 24, 32]) expect(tokens).toMatch(new RegExp(`--ds-space-\\d: ${px}px;`));
    for (const px of [8, 12, 16]) expect(tokens).toMatch(new RegExp(`--ds-radius-\\w+: ${px}px;`));
  });
  test("index xuất đủ component kế hoạch yêu cầu", () => {
    const index = readFileSync(new URL("index.ts", DS), "utf8");
    const can = [
      "Button", "Input", "Select", "Textarea", "Checkbox", "Card", "StatCard", "Table", "Badge",
      "StatusBadge", "RoleBadge", "Tabs", "Modal", "Drawer", "Toast", "EmptyState", "Skeleton", "Pagination",
    ];
    for (const ten of can) {
      expect(index).toContain(`as ${ten} }`);
      expect(readdirSync(new URL("components/", DS))).toContain(`${ten}.vue`);
    }
  });
  test("component không đặt mã màu cứng", () => {
    const files = readdirSync(new URL("components/", DS), { recursive: true }).filter((f) => /\.(vue|ts)$/.test(f));
    expect(files.length).toBeGreaterThan(20);
    for (const f of files) {
      const src = readFileSync(new URL(`components/${f}`, DS), "utf8");
      expect(src, f).not.toMatch(/#[0-9a-fA-F]{6}\b/);
    }
  });
});

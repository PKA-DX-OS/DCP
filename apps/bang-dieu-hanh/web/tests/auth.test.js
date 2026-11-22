// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import { canViewDashboard } from "../src/auth";

describe("canViewDashboard", () => {
  test("cho lãnh đạo, kiểm toán, quản trị và quản lý dữ liệu", () => {
    expect(canViewDashboard(["app:cap-phep:lanh-dao"])).toBe(true);
    expect(canViewDashboard(["dx:auditor"])).toBe(true);
    expect(canViewDashboard(["dx:tenant-admin"])).toBe(true);
    expect(canViewDashboard(["dx:platform-admin"])).toBe(true);
    expect(canViewDashboard(["dx:data-steward"])).toBe(true);
  });

  test("không cho cán bộ nghiệp vụ và chủ đầu tư", () => {
    expect(canViewDashboard(["app:cap-phep:mot-cua"])).toBe(false);
    expect(canViewDashboard(["app:cap-phep:tham-dinh"])).toBe(false);
    expect(canViewDashboard(["app:cap-phep:chu-dau-tu"])).toBe(false);
    expect(canViewDashboard([])).toBe(false);
  });
});

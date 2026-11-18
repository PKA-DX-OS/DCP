// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import { hasRole, canReviewCase, canApproveCase, canViewCase, canInspect } from "../src/utils/permissions.js";

const GIO = 60 * 60 * 1000;

// Mỗi vai một người dùng mẫu, khớp tài khoản demo.
const VAI = {
  chuDauTu: { sub: "cdt.minh", roles: ["chu-dau-tu"] },
  chuDauTuKhac: { sub: "cdt.lan", roles: ["chu-dau-tu"] },
  motCua: { sub: "mc.thu", roles: ["mot-cua"] },
  thamDinh: { sub: "td.binh", roles: ["tham-dinh"] },
  thamDinhKhac: { sub: "td.cuong", roles: ["tham-dinh"] },
  lanhDao: { sub: "ld.hoa", roles: ["lanh-dao"] },
  tratTu: { sub: "tt.khanh", roles: ["trat-tu-xay-dung"] },
};

const hoSo = (them = {}) => ({
  id: "HS-001",
  chu_dau_tu_id: "cdt.minh",
  nguoi_tham_dinh: "td.binh",
  trang_thai: "CHO_PHE_DUYET",
  ...them,
});

const truyCapKhan = (conHan, them = {}) => [
  {
    actor_id: "td.cuong",
    resource_id: "HS-001",
    status: "DA_DUYET",
    expires_at: new Date(Date.now() + (conHan ? GIO : -GIO)).toISOString(),
    ...them,
  },
];

describe("hasRole", () => {
  test("chỉ đúng khi mảng vai có vai cần tìm", () => {
    expect(hasRole(["tham-dinh", "mot-cua"], "tham-dinh")).toBe(true);
    expect(hasRole(["tham-dinh"], "lanh-dao")).toBe(false);
    expect(hasRole(null, "tham-dinh")).toBe(false);
    expect(hasRole("tham-dinh", "tham-dinh")).toBe(false);
  });
});

describe("bản đồ quyền theo vai", () => {
  // Hàng: vai; cột: xem hồ sơ, thẩm định, phê duyệt, kiểm tra hiện trường.
  const BANG = [
    ["chuDauTu", true, false, false, false],
    ["chuDauTuKhac", false, false, false, false],
    ["motCua", true, false, false, false],
    ["thamDinh", true, true, false, false],
    ["thamDinhKhac", false, false, false, false],
    ["lanhDao", true, false, true, true],
    ["tratTu", false, false, false, true],
  ];

  test.each(BANG)("%s", (vai, xem, thamDinh, pheDuyet, kiemTra) => {
    const u = VAI[vai];
    expect(canViewCase(u, hoSo())).toBe(xem);
    expect(canReviewCase(u, hoSo())).toBe(thamDinh);
    expect(canApproveCase(u, hoSo())).toBe(pheDuyet);
    expect(canInspect(u)).toBe(kiemTra);
  });

  test("thiếu người dùng hoặc hồ sơ thì không có quyền", () => {
    expect(canViewCase(null, hoSo())).toBe(false);
    expect(canReviewCase(VAI.thamDinh, null)).toBe(false);
    expect(canApproveCase(VAI.lanhDao, null)).toBe(false);
    expect(canInspect(null)).toBe(false);
  });
});

describe("truy cập khẩn", () => {
  test("thẩm định viên chưa phân công chỉ được thẩm định khi truy cập khẩn còn hạn", () => {
    const u = VAI.thamDinhKhac;
    expect(canReviewCase(u, hoSo(), truyCapKhan(true))).toBe(true);
    expect(canViewCase(u, hoSo(), truyCapKhan(true))).toBe(true);
    expect(canReviewCase(u, hoSo(), truyCapKhan(false))).toBe(false);
  });

  test("yêu cầu chưa duyệt hoặc của hồ sơ khác không mở quyền", () => {
    const u = VAI.thamDinhKhac;
    expect(canReviewCase(u, hoSo(), truyCapKhan(true, { status: "CHO_DUYET" }))).toBe(false);
    expect(canReviewCase(u, hoSo(), truyCapKhan(true, { resource_id: "HS-002" }))).toBe(false);
  });

  test("truy cập khẩn không cho người không có vai thẩm định", () => {
    expect(canReviewCase(VAI.motCua, hoSo(), truyCapKhan(true, { actor_id: "mc.thu" }))).toBe(false);
  });
});

describe("tách biệt nhiệm vụ (SoD)", () => {
  test("người đã thẩm định không được tự phê duyệt dù có vai lãnh đạo", () => {
    const haiVai = { sub: "td.binh", roles: ["tham-dinh", "lanh-dao"] };
    expect(canApproveCase(haiVai, hoSo())).toBe(false);
    expect(canApproveCase(VAI.lanhDao, hoSo())).toBe(true);
  });

  test("chỉ phê duyệt khi hồ sơ đang chờ phê duyệt", () => {
    expect(canApproveCase(VAI.lanhDao, hoSo({ trang_thai: "DANG_THAM_DINH" }))).toBe(false);
  });
});

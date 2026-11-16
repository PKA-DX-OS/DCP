// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import test from "node:test";
import assert from "node:assert/strict";
import {
  hasRole,
  canReviewCase,
  canApproveCase,
  canViewCase,
  canInspect
} from "../src/utils/permissions.js";

test("hasRole: kiem tra vai tro chinh xac", () => {
  const roles = ["tham-dinh", "mot-cua"];
  assert.strictEqual(hasRole(roles, "tham-dinh"), true);
  assert.strictEqual(hasRole(roles, "lanh-dao"), false);
  assert.strictEqual(hasRole(null, "tham-dinh"), false);
});

test("canReviewCase: tham dinh vien duoc phan cong moi duoc tham dinh", () => {
  const reviewerBinh = { sub: "td.binh", roles: ["tham-dinh"] };
  const reviewerCuong = { sub: "td.cuong", roles: ["tham-dinh"] };
  const hoSo = { id: "HS-001", nguoi_tham_dinh: "td.binh" };

  // td.binh duoc phan cong -> duoc phep
  assert.strictEqual(canReviewCase(reviewerBinh, hoSo), true);

  // td.cuong khong duoc phan cong -> khong duoc phep (403)
  assert.strictEqual(canReviewCase(reviewerCuong, hoSo), false);

  // td.cuong duoc duyet break-glass con han -> duoc phep
  const activeBreakGlass = [
    {
      actor_id: "td.cuong",
      resource_id: "HS-001",
      status: "DA_DUYET",
      expires_at: new Date(Date.now() + 3600000).toISOString()
    }
  ];
  assert.strictEqual(canReviewCase(reviewerCuong, hoSo, activeBreakGlass), true);

  // break-glass het han -> bi thu hoi quyen
  const expiredBreakGlass = [
    {
      actor_id: "td.cuong",
      resource_id: "HS-001",
      status: "DA_DUYET",
      expires_at: new Date(Date.now() - 3600000).toISOString()
    }
  ];
  assert.strictEqual(canReviewCase(reviewerCuong, hoSo, expiredBreakGlass), false);
});

test("canApproveCase: SoD nguoi phe duyet phai khac nguoi tham dinh", () => {
  const leaderHoa = { sub: "ld.hoa", roles: ["lanh-dao"] };
  const dualRoleUser = { sub: "td.binh", roles: ["tham-dinh", "lanh-dao"] };

  const hoSo = {
    id: "HS-001",
    nguoi_tham_dinh: "td.binh",
    trang_thai: "CHO_PHE_DUYET"
  };

  // ld.hoa khong tham dinh -> duoc phep phe duyet
  assert.strictEqual(canApproveCase(leaderHoa, hoSo), true);

  // td.binh la nguoi da tham dinh -> BI CAM tu phe duyet (vi pham SoD)
  assert.strictEqual(canApproveCase(dualRoleUser, hoSo), false);

  // Ho so chua o buoc CHO_PHE_DUYET -> khong the duyet
  const hoSoChuaXong = { ...hoSo, trang_thai: "DANG_THAM_DINH" };
  assert.strictEqual(canApproveCase(leaderHoa, hoSoChuaXong), false);
});

test("canInspect: chi can bo trat tu xay dung hoac lanh dao duoc phep", () => {
  const inspector = { sub: "tt.giang", roles: ["trat-tu-xay-dung"] };
  const citizen = { sub: "cdt.an", roles: ["chu-dau-tu"] };

  assert.strictEqual(canInspect(inspector), true);
  assert.strictEqual(canInspect(citizen), false);
});

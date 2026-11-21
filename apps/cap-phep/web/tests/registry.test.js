// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import { DOSSIER_TABS, FEATURES, dossierTabsChoVai, maTrung, tabsChoVai } from "../src/features/registry";

const ma = (ds) => ds.map((f) => f.ma);
const CDT = "app:cap-phep:chu-dau-tu";

describe("tab theo vai", () => {
  test.each([
    [[CDT], ["ho-so", "du-lieu"]],
    [["app:cap-phep:mot-cua"], ["ban-lam-viec", "duyet-ocr", "cong-trinh", "phap-luat"]],
    [["app:cap-phep:tham-dinh"], ["ban-lam-viec", "duyet-ocr", "cong-trinh", "phap-luat"]],
    [["app:cap-phep:trat-tu-xd"], ["ban-lam-viec", "cong-trinh", "phap-luat"]],
    [["app:cap-phep:lanh-dao"], ["ban-lam-viec", "duyet-ocr", "cong-trinh", "phap-luat", "truy-cap-khan"]],
    [[], []],
    [["dx:auditor"], []],
  ])("%j -> %j", (vai, kq) => {
    expect(ma(tabsChoVai(vai))).toEqual(kq);
  });
});

describe("registry", () => {
  test("mã tab không trùng", () => {
    expect(maTrung(FEATURES)).toEqual([]);
    expect(maTrung(DOSSIER_TABS)).toEqual([]);
    expect(maTrung([{ ma: "a" }, { ma: "b" }, { ma: "a" }])).toEqual(["a"]);
  });
  test("sắp theo thuTu, không phụ thuộc thứ tự khai báo", () => {
    const comp = {};
    const ds = [
      { ma: "sau", ten: "Sau", thuTu: 90, hienThi: () => true, component: comp },
      { ma: "truoc", ten: "Trước", thuTu: 5, hienThi: () => true, component: comp },
      { ma: "an", ten: "Ẩn", thuTu: 1, hienThi: () => false, component: comp },
    ];
    expect(ma(tabsChoVai([], ds))).toEqual(["truoc", "sau"]);
  });
  test("phần chi tiết hồ sơ lọc theo vai và hồ sơ", () => {
    const comp = {};
    const ds = [
      { ma: "thiet-ke", ten: "Thiết kế", thuTu: 20, hienThi: (vai) => vai.includes(CDT), component: comp },
      { ma: "nghiem-thu", ten: "Nghiệm thu", thuTu: 10, hienThi: (_v, hs) => hs.trang_thai === "DA_CAP", component: comp },
    ];
    expect(ma(dossierTabsChoVai([CDT], { trang_thai: "DA_CAP" }, ds))).toEqual(["nghiem-thu", "thiet-ke"]);
    expect(ma(dossierTabsChoVai([], { trang_thai: "DA_NOP" }, ds))).toEqual([]);
  });
  test("App.vue không còn khai báo tab cứng", () => {
    const app = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8");
    expect(app).toContain("tabsChoVai");
    expect(app).not.toMatch(/ma: "ho-so"|DossiersView|WorkspaceView/);
  });
});

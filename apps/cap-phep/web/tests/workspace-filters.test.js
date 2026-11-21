// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { beforeEach, describe, expect, test } from "vitest";
import { KHOA_BO_LOC, docBoLoc, luuBoLoc, xoaBoLoc } from "../src/utils/workspace-filters";

function taoStorage() {
  const m = new Map();
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
    clear: () => m.clear(),
    key: (i) => Array.from(m.keys())[i] ?? null,
    get length() {
      return m.size;
    },
  };
}

let storage;

beforeEach(() => {
  storage = taoStorage();
});

describe("bộ lọc Bàn làm việc đã lưu", () => {
  test("đọc danh sách rỗng hoặc dữ liệu hỏng thì trả []", () => {
    expect(docBoLoc(storage)).toEqual([]);
    storage.setItem(KHOA_BO_LOC, "khong-phai-json");
    expect(docBoLoc(storage)).toEqual([]);
    storage.setItem(KHOA_BO_LOC, JSON.stringify([{ ten: "x" }]));
    expect(docBoLoc(storage)).toEqual([]);
  });

  test("lưu, thay cùng tên và sắp mới nhất trước", () => {
    let ds = luuBoLoc(storage, [], "Quá hạn", "qua-han", "tham-dinh", 1000);
    ds = luuBoLoc(storage, ds, "Sắp hạn", "sap-han", "phe-duyet", 2000);
    ds = luuBoLoc(storage, ds, "Quá hạn", "qua-han", "nghiem-thu", 3000);

    expect(ds).toHaveLength(2);
    expect(ds[0]).toMatchObject({ ten: "Quá hạn", loaiViec: "nghiem-thu", at: 3000 });
    expect(ds[1].ten).toBe("Sắp hạn");
    expect(docBoLoc(storage)).toHaveLength(2);
  });

  test("xóa theo tên, không phân biệt hoa thường", () => {
    let ds = luuBoLoc(storage, [], "Quá hạn", "qua-han", "tham-dinh", 1000);
    ds = luuBoLoc(storage, ds, "Sắp hạn", "sap-han", "phe-duyet", 2000);
    ds = xoaBoLoc(storage, ds, "quá HẠN");
    expect(ds.map((x) => x.ten)).toEqual(["Sắp hạn"]);
    expect(docBoLoc(storage).map((x) => x.ten)).toEqual(["Sắp hạn"]);
  });

  test("giữ tối đa 10 bộ lọc", () => {
    let ds = [];
    for (let i = 0; i < 15; i++) {
      ds = luuBoLoc(storage, ds, `Bộ lọc ${i}`, "tat-ca", "tat-ca", 1000 + i);
    }
    expect(ds).toHaveLength(10);
    expect(ds[0].ten).toBe("Bộ lọc 14");
  });

  test("không lưu tên rỗng", () => {
    expect(luuBoLoc(storage, [], "   ", "tat-ca", "tat-ca", 1000)).toEqual([]);
    expect(storage.getItem(KHOA_BO_LOC)).toBeNull();
  });
});

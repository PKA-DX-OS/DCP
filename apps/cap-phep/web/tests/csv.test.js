// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import { taoCsv } from "../src/utils/csv";

describe("tạo CSV", () => {
  test("có BOM, tiêu đề và dòng dữ liệu", () => {
    const csv = taoCsv(["Mã", "Tên"], [["CP-001", "Thẩm định"]]);
    expect(csv.startsWith("\uFEFF")).toBe(true);
    expect(csv).toContain("Mã,Tên");
    expect(csv).toContain("CP-001,Thẩm định");
  });

  test("escape dấu phẩy, nháy kép và xuống dòng", () => {
    const csv = taoCsv(["A", "B"], [['Có "nháy", phẩy', "Dòng 1\nDòng 2"]]);
    expect(csv).toContain('"Có ""nháy"", phẩy"');
    expect(csv).toContain('"Dòng 1\nDòng 2"');
  });

  test("null và undefined thành chuỗi rỗng", () => {
    const csv = taoCsv(["A", "B", "C"], [[null, undefined, 0]]);
    expect(csv).toContain(",,");
    expect(csv).toContain(",0");
  });
});

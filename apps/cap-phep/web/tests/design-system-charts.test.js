// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { readFileSync } from "node:fs";
import { describe, expect, test } from "vitest";
import {
  barRects,
  chartColor,
  DEFAULT_BOX,
  donutArcs,
  linePath,
  linePoints,
  niceMax,
  sparkPath,
  ticks,
} from "../src/design-system/components/charts/geometry";
import { checkFile, formatBytes, isoToVn } from "../src/design-system/files";

const plotH = DEFAULT_BOX.height - DEFAULT_BOX.padTop - DEFAULT_BOX.padBottom;
const plotW = DEFAULT_BOX.width - DEFAULT_BOX.padLeft - DEFAULT_BOX.padRight;

describe("donut", () => {
  test("tỷ lệ cung đúng với dữ liệu và cộng lại bằng 1", () => {
    const arcs = donutArcs([1, 1, 2]);
    expect(arcs.map((a) => a.fraction)).toEqual([0.25, 0.25, 0.5]);
    expect(arcs.reduce((s, a) => s + a.fraction, 0)).toBeCloseTo(1);
  });
  test("cung lớn hơn nửa vòng dùng cờ large-arc", () => {
    const [a] = donutArcs([3, 1]);
    expect(a.path).toContain(" 0 1 1 ");
  });
  test("cung đầu bắt đầu ở đỉnh vòng", () => {
    expect(donutArcs([1, 1])[0].path.startsWith("M50 2 ")).toBe(true);
  });
  test("bỏ giá trị 0, âm, NaN; tổng 0 thì không có cung", () => {
    expect(donutArcs([0, 5, -2, NaN]).map((a) => a.index)).toEqual([1]);
    expect(donutArcs([0, 0])).toEqual([]);
    expect(donutArcs([])).toEqual([]);
  });
  test("một nhóm chiếm trọn vòng vẫn vẽ được", () => {
    const [a] = donutArcs([7]);
    expect(a.fraction).toBe(1);
    expect(a.path).toMatch(/^M50 2 A48 48 0 1 1 /);
  });
});

describe("trục", () => {
  test.each([
    [0, 1],
    [7, 10],
    [12, 20],
    [43, 50],
    [100, 100],
    [101, 200],
  ])("niceMax(%s) = %s", (v, kq) => expect(niceMax(v)).toBe(kq));
  test("vạch chia đều từ 0 tới đỉnh", () => {
    expect(ticks(43)).toEqual([0, 12.5, 25, 37.5, 50]);
  });
});

describe("đường", () => {
  test("điểm cao nhất chạm đỉnh khi max tròn, điểm 0 nằm ở đáy", () => {
    const pts = linePoints([0, 50, 100], 100);
    expect(pts[0].y).toBe(DEFAULT_BOX.padTop + plotH);
    expect(pts[2].y).toBe(DEFAULT_BOX.padTop);
    expect(pts[0].x).toBe(DEFAULT_BOX.padLeft);
    expect(pts[2].x).toBe(DEFAULT_BOX.padLeft + plotW);
  });
  test("dữ liệu thiếu tạo khoảng trống, không nối qua", () => {
    const d = linePath(linePoints([10, null, 30], 30));
    expect(d.match(/M/g)).toHaveLength(2);
    expect(d).not.toContain("L");
  });
  test("một điểm nằm giữa", () => {
    expect(linePoints([5], 5)[0].x).toBe(DEFAULT_BOX.padLeft + plotW / 2);
  });
});

describe("cột", () => {
  test("chiều cao tỷ lệ với giá trị, cột nằm trong vùng vẽ", () => {
    const r = barRects([5, 10], 10);
    expect(r[1].height).toBe(plotH);
    expect(r[0].height).toBe(plotH / 2);
    for (const c of r) {
      expect(c.x).toBeGreaterThanOrEqual(DEFAULT_BOX.padLeft);
      expect(c.x + c.width).toBeLessThanOrEqual(DEFAULT_BOX.width - DEFAULT_BOX.padRight);
      expect(c.y + c.height).toBeCloseTo(DEFAULT_BOX.padTop + plotH);
    }
  });
  test("giá trị âm vẽ như 0", () => {
    expect(barRects([-3], 1)[0].height).toBe(0);
  });
});

describe("sparkline và màu", () => {
  test("ít hơn hai điểm thì không vẽ", () => {
    expect(sparkPath([4])).toBe("");
    expect(sparkPath([1, 2]).startsWith("M0 24 L80 0")).toBe(true);
  });
  test("bảng 5 màu xoay vòng, lấy từ token", () => {
    expect(chartColor(0)).toBe("rgb(var(--ds-chart-1))");
    expect(chartColor(5)).toBe(chartColor(0));
    const tokens = readFileSync(new URL("../src/design-system/tokens.css", import.meta.url), "utf8");
    for (let i = 1; i <= 5; i++) expect(tokens.match(new RegExp(`--ds-chart-${i}:`, "g"))).toHaveLength(2);
  });
});

describe("tệp và ngày", () => {
  const pdf = { name: "Ban-ve.PDF", type: "application/pdf", size: 2048 };
  test("nhận đúng loại theo đuôi hoặc MIME", () => {
    expect(checkFile(pdf, { accept: [".pdf"] })).toBeNull();
    expect(checkFile(pdf, { accept: ["application/pdf"] })).toBeNull();
    expect(checkFile({ name: "a.png", type: "image/png", size: 5 }, { accept: ["image/*"] })).toBeNull();
  });
  test("từ chối sai loại, quá lớn, tệp rỗng và nói rõ lý do", () => {
    expect(checkFile({ name: "x.dwg", type: "", size: 10 }, { accept: [".pdf"] })).toMatch(/không đúng loại/);
    expect(checkFile(pdf, { maxBytes: 1024 })).toMatch(/vượt giới hạn 1 KB/);
    expect(checkFile({ ...pdf, size: 0 }, {})).toMatch(/rỗng/);
  });
  test("định dạng dung lượng và ngày kiểu Việt Nam", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1536)).toBe("1,5 KB");
    expect(formatBytes(20 * 1024 * 1024)).toBe("20 MB");
    expect(isoToVn("2026-11-19")).toBe("19/11/2026");
    expect(isoToVn("19/11/2026")).toBe("");
  });
});

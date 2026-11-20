// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { expect, test } from "vitest";
import { renderMarkdown, tenNguon } from "../src/utils/markdown.js";

test("escape HTML trước khi render", () => {
  const html = renderMarkdown("<script>alert(1)</script> **đậm**");
  expect(html.includes("&lt;script&gt;")).toBe(true);
  expect(html.includes("<script>")).toBe(false);
  expect(html.includes("<strong>đậm</strong>")).toBe(true);
});

test("render tiêu đề, danh sách và code", () => {
  const html = renderMarkdown("# Tiêu đề\n- một\n- hai\n\n`code`");
  expect(html.includes("<h1>Tiêu đề</h1>")).toBe(true);
  expect(html.includes("<ul>")).toBe(true);
  expect(html.includes("<li>một</li>")).toBe(true);
  expect(html.includes("<code>code</code>")).toBe(true);
});

test("tên nguồn không lộ file.md", () => {
  expect(tenNguon("legal-pdf/ND-278.pdf#p3")).toBe("ND 278.pdf");
  expect(tenNguon("legal-analysis/quy-dinh.md#c1")).toBe("quy dinh");
});

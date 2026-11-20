// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import { renderMarkdown, tenNguon } from "../src/utils/markdown.js";

describe("renderMarkdown", () => {
  test("escape HTML trước khi render", () => {
    const html = renderMarkdown("<script>alert(1)</script> **đậm**");
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
    expect(html).toContain("<strong>đậm</strong>");
  });

  test("render tiêu đề, danh sách và code", () => {
    const html = renderMarkdown("# Tiêu đề\n- một\n- hai\n\n`code`");
    expect(html).toContain("<h1>Tiêu đề</h1>");
    expect(html).toContain("<ul>");
    expect(html).toContain("<li>một</li>");
    expect(html).toContain("<code>code</code>");
  });
});

describe("tên nguồn trích dẫn", () => {
  test("không lộ file.md", () => {
    expect(tenNguon("legal-pdf/ND-278.pdf#p3")).toBe("ND 278.pdf");
    expect(tenNguon("legal-analysis/quy-dinh.md#c1")).toBe("quy dinh");
  });
});

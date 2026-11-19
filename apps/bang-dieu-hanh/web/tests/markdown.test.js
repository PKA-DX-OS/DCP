// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import assert from "node:assert/strict";
import test from "node:test";
import { renderMarkdown, tenNguon } from "../src/utils/markdown.js";

test("escape HTML trước khi render", () => {
  const html = renderMarkdown("<script>alert(1)</script> **đậm**");
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(!html.includes("<script>"));
  assert.ok(html.includes("<strong>đậm</strong>"));
});

test("render tiêu đề, danh sách và code", () => {
  const html = renderMarkdown("# Tiêu đề\n- một\n- hai\n\n`code`");
  assert.ok(html.includes("<h1>Tiêu đề</h1>"));
  assert.ok(html.includes("<ul>"));
  assert.ok(html.includes("<li>một</li>"));
  assert.ok(html.includes("<code>code</code>"));
});

test("tên nguồn không lộ file.md", () => {
  assert.equal(tenNguon("legal-pdf/ND-278.pdf#p3"), "ND 278.pdf");
  assert.equal(tenNguon("legal-analysis/quy-dinh.md#c1"), "quy dinh");
});

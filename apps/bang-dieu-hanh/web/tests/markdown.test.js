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
  expect(tenNguon("legal-pdf/ND-278.pdf#p3")).toBe("Nghị định 278");
  expect(tenNguon("legal-analysis/quy-dinh.md#c1")).toBe("Quy dinh");
  expect(tenNguon("quy-dinh-cap-phep.md#2")).toBe("Quy định cấp phép của địa bàn");
});

test("mã trích dẫn pháp lý đọc được", () => {
  expect(tenNguon("legal/ND217-D54")).toBe("Nghị định 217, Điều 54");
  expect(tenNguon("legal/ND217-D53-K1")).toBe("Nghị định 217, Điều 53, khoản 1");
  expect(tenNguon("legal/LXD135-TOANVAN")).toBe("Luật Xây dựng số 135, toàn văn");
});

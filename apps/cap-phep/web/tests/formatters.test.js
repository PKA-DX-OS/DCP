// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import test from "node:test";
import assert from "node:assert/strict";
import {
  formatNumberVi,
  formatCurrency,
  formatArea,
  maskCccd,
  formatDateVn,
  calculateDaysRemaining
} from "../src/utils/formatters.js";

test("formatNumberVi: dinh dang so theo chuan vi-VN", () => {
  // vi-VN su dung dau cham phan ngan va dau phay thap phan
  const formatted = formatNumberVi(1234567.89);
  assert.ok(formatted.includes("1.234.567") || formatted.includes("1234567"));
  assert.strictEqual(formatNumberVi(0), "0");
  assert.strictEqual(formatNumberVi(null), "0");
});

test("formatCurrency: dinh dang tien VND", () => {
  const result = formatCurrency(500000);
  assert.ok(result.includes("500.000") || result.includes("500000"));
  assert.ok(result.includes("₫") || result.includes("đ") || result.includes("VND"));
});

test("formatArea: dinh dang dien tich m2", () => {
  const result = formatArea(120.5);
  assert.ok(result.endsWith("m²"));
  assert.ok(result.includes("120"));
});

test("maskCccd: che gia tri CCCD bao ve quyen rieng tu", () => {
  assert.strictEqual(maskCccd("001099123456"), "001099******");
  assert.strictEqual(maskCccd("079088654321"), "079088******");
  assert.strictEqual(maskCccd("12345"), "12345"); // qua ngan khong che
  assert.strictEqual(maskCccd(""), "");
});

test("formatDateVn: dinh dang theo gio Asia/Ho_Chi_Minh", () => {
  const d = new Date("2026-11-04T08:30:00Z");
  const str = formatDateVn(d);
  assert.ok(str.length > 5);
  // nam 2026 phai xuat hien
  assert.ok(str.includes("2026"));
});

test("calculateDaysRemaining: tinh han xu ly", () => {
  const future = new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString();
  const resFuture = calculateDaysRemaining(future);
  assert.strictEqual(resFuture.isOverdue, false);
  assert.ok(resFuture.daysRemaining >= 4);

  const past = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
  const resPast = calculateDaysRemaining(past);
  assert.strictEqual(resPast.isOverdue, true);
  assert.ok(resPast.text.includes("Qua han"));
});

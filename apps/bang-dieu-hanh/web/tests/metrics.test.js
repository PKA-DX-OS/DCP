// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import test from "node:test";
import assert from "node:assert/strict";
import {
  calculateSlaRate,
  formatMetricValue
} from "../src/utils/metrics.js";

test("calculateSlaRate: tinh ty le dung han chinh xac", () => {
  assert.strictEqual(calculateSlaRate(100, 95), 95.0);
  assert.strictEqual(calculateSlaRate(50, 48), 96.0);
  assert.strictEqual(calculateSlaRate(0, 0), 100.0);
  assert.strictEqual(calculateSlaRate(10, 0), 0.0);
});

test("formatMetricValue: dinh dang so kem don vi vi-VN", () => {
  assert.strictEqual(formatMetricValue(1234.5, "hồ sơ"), "1.234,5 hồ sơ");
  assert.strictEqual(formatMetricValue(98.5, "%"), "98,5 %");
  assert.strictEqual(formatMetricValue(null, "ngày"), "0 ngày");
});

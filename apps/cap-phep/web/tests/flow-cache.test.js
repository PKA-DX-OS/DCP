// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later
// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { completeTask, fetchTasks, invalidateTasks } from "../src/api/flow";

let goi = [];

beforeEach(() => {
  goi = [];
  invalidateTasks();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url, init) => {
      goi.push(`${init?.method || "GET"} ${url}`);
      return new Response(JSON.stringify({ tasks: [{ id: "t1" }] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("mở hồ sơ: các phần cùng lấy danh sách việc chỉ gọi máy chủ một lần", async () => {
  const [a, b, c] = await Promise.all([fetchTasks("tk"), fetchTasks("tk"), fetchTasks("tk")]);
  expect(a).toEqual([{ id: "t1" }]);
  expect(b).toBe(a);
  expect(c).toBe(a);
  expect(goi.filter((g) => g.includes("/flow/tasks")).length).toBe(1);
});

test("hoàn thành việc thì lần lấy sau gọi lại máy chủ", async () => {
  await fetchTasks("tk");
  await completeTask("tk", "t1", {});
  await fetchTasks("tk");
  expect(goi.filter((g) => g.startsWith("GET") && g.includes("/flow/tasks")).length).toBe(2);
});

test("sự kiện dxos:tasks-changed bỏ bộ nhớ đệm", async () => {
  await fetchTasks("tk");
  window.dispatchEvent(new Event("dxos:tasks-changed"));
  await fetchTasks("tk");
  expect(goi.filter((g) => g.startsWith("GET")).length).toBe(2);
});

test("token khác không dùng chung kết quả", async () => {
  await fetchTasks("a");
  await fetchTasks("b");
  expect(goi.length).toBe(2);
});

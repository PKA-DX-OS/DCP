// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import WorkspaceView from "../src/views/WorkspaceView.vue";
import { fetchTasks } from "../src/api/flow";

vi.mock("../src/auth", () => ({
  getUser: vi.fn(async () => ({ profile: { sub: "u-1" }, access_token: "token" })),
  getValidToken: vi.fn(async () => "token"),
  readRoles: vi.fn(() => ["app:cap-phep:mot-cua"]),
}));

vi.mock("../src/api/flow", () => ({
  fetchTasks: vi.fn(),
  fetchEscalations: vi.fn(async () => ({ items: [] })),
  remindTask: vi.fn(),
  assignTask: vi.fn(),
  fetchOfficers: vi.fn(),
  fetchWorkload: vi.fn(async () => []),
  completeTask: vi.fn(),
  invalidateTasks: vi.fn(),
}));

const HO_SO_ID = "11111111-1111-4111-8111-111111111111";

function traLoi(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === null || body === undefined ? "" : JSON.stringify(body)),
  };
}

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(fetchTasks).mockResolvedValue([
    {
      id: "t1",
      name: "Thẩm định hồ sơ",
      taskDefinitionKey: "taskThamDinh",
      businessKey: "CP-001",
      dueDate: "2026-11-30T10:00:00+07:00",
      variables: [
        { name: "ma_ho_so", value: "CP-001" },
        { name: "ho_so_id", value: HO_SO_ID },
        { name: "trang_thai_ho_so", value: "DA_NOP" },
        { name: "do_uu_tien", value: "binh_thuong" },
      ],
    },
  ]);
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("WorkspaceView — trạng thái hàng đợi", () => {
  test("ưu tiên trạng thái sống trong v_ho_so thay vì biến Flowable cũ", async () => {
    const fetchMock = vi.fn(async (url) => {
      if (String(url).includes("/rest/v_ho_so?") && String(url).includes("id=in.")) {
        return traLoi(200, [{ id: HO_SO_ID, trang_thai: "DA_CAP" }]);
      }
      return traLoi(404, { message: "not found" });
    });
    vi.stubGlobal("fetch", fetchMock);

    const w = mount(WorkspaceView, { attachTo: document.body });
    await flushPromises();

    expect(w.text()).toContain("Đã cấp phép");
    expect(w.text()).not.toContain("Đã nộp");
    expect(fetchMock).toHaveBeenCalled();
  });
});

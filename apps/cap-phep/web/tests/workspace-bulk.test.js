// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import WorkspaceView from "../src/views/WorkspaceView.vue";
import { assignTask, fetchEscalations, fetchOfficers, fetchTasks, remindTask } from "../src/api/flow";
import { taiCsv } from "../src/utils/csv";

vi.mock("../src/auth", () => ({
  getUser: vi.fn(async () => ({ profile: { sub: "u-1" }, access_token: "token" })),
  getValidToken: vi.fn(async () => "token"),
  readRoles: vi.fn(() => ["app:cap-phep:mot-cua"]),
}));

vi.mock("../src/api/flow", () => ({
  fetchTasks: vi.fn(),
  fetchEscalations: vi.fn(),
  remindTask: vi.fn(),
  assignTask: vi.fn(),
  fetchOfficers: vi.fn(),
  fetchWorkload: vi.fn(async () => []),
  completeTask: vi.fn(),
  invalidateTasks: vi.fn(),
}));

vi.mock("../src/utils/csv", () => ({
  taiCsv: vi.fn(),
}));

function taoTask(id, ma, dueDate) {
  return {
    id,
    name: "Thẩm định hồ sơ",
    taskDefinitionKey: "taskThamDinh",
    businessKey: ma,
    dueDate,
    assignee: "u-2",
    variables: [
      { name: "ma_ho_so", value: ma },
      { name: "ho_so_id", value: `hs-${id}` },
      { name: "dia_chi_cong_trinh", value: `Địa chỉ ${ma}` },
      { name: "trang_thai_ho_so", value: "DANG_THAM_DINH" },
      { name: "do_uu_tien", value: "binh_thuong" },
    ],
  };
}

enableAutoUnmount(afterEach);

beforeEach(() => {
  localStorage.clear();
  vi.mocked(fetchTasks).mockResolvedValue([
    taoTask("t1", "CP-001", "2026-11-30T10:00:00+07:00"),
    taoTask("t2", "CP-002", "2026-11-21T10:00:00+07:00"),
  ]);
  vi.mocked(fetchEscalations).mockResolvedValue({ items: [] });
  vi.mocked(fetchOfficers).mockResolvedValue([{ sub: "u-2", username: "td.mau", ho_ten: "Thẩm định viên Mẫu" }]);
  vi.mocked(remindTask).mockResolvedValue({});
  vi.mocked(assignTask).mockResolvedValue({});
});

afterEach(() => {
  vi.clearAllMocks();
});

async function moManHinh() {
  const w = mount(WorkspaceView, { attachTo: document.body });
  await flushPromises();
  return w;
}

function nut(w, text) {
  return w.findAll("button").find((b) => b.text() === text);
}

describe("WorkspaceView — thao tác hàng loạt", () => {
  test("chọn một việc rồi nhắc việc có xác nhận", async () => {
    const w = await moManHinh();
    await w.get('input[aria-label="Chọn việc CP-001"]').setValue(true);
    expect(w.text()).toContain("Đã chọn 1 việc");

    await nut(w, "Nhắc việc").trigger("click");
    expect(w.text()).toContain("Gửi nhắc 1 việc đã chọn?");
    await nut(w, "Xác nhận nhắc").trigger("click");
    await flushPromises();

    expect(remindTask).toHaveBeenCalledWith("token", "t1");
    expect(remindTask).toHaveBeenCalledTimes(1);
  });

  test("phân công hàng loạt cần chọn cán bộ và gửi lý do", async () => {
    const w = await moManHinh();
    await w.get('input[aria-label="Chọn việc CP-001"]').setValue(true);
    await nut(w, "Phân công").trigger("click");
    await flushPromises();

    expect(fetchOfficers).toHaveBeenCalledWith("token", "tham-dinh");
    await w.get('select[aria-label="Cán bộ được phân công"]').setValue("u-2");
    await w.get('input[aria-label="Lý do phân công"]').setValue("Cân bằng tải việc");
    await nut(w, "Xác nhận phân công").trigger("click");
    await flushPromises();

    expect(assignTask).toHaveBeenCalledWith("token", "t1", "u-2", "Cân bằng tải việc");
  });

  test("chọn tất cả và xuất CSV các việc đang lọc", async () => {
    const w = await moManHinh();
    await w.get('input[aria-label="Chọn tất cả việc đang lọc"]').setValue(true);
    expect(w.text()).toContain("Đã chọn 2 việc");

    await nut(w, "Xuất CSV").trigger("click");

    expect(taiCsv).toHaveBeenCalledTimes(1);
    const [tenFile, headers, rows] = vi.mocked(taiCsv).mock.calls[0];
    expect(tenFile).toMatch(/^viec-da-chon-\d{4}-\d{2}-\d{2}\.csv$/);
    expect(headers).toEqual(["Mã hồ sơ", "Tên việc", "Địa chỉ", "Hạn xử lý", "Trạng thái", "Mức ưu tiên"]);
    expect(rows).toHaveLength(2);
    expect(rows[0][0]).toBe("CP-001");
  });

  test("lưu bộ lọc hiện tại vào localStorage và áp dụng lại", async () => {
    const w = await moManHinh();
    await w.get("#loc-viec").setValue("qua-han");
    await w.get("#loc-loai-viec").setValue("tham-dinh");
    await nut(w, "Lưu bộ lọc").trigger("click");
    await w.get('input[aria-label="Tên bộ lọc"]').setValue("Quá hạn thẩm định");
    await nut(w, "Lưu").trigger("click");

    const raw = localStorage.getItem("dxos-workspace-filters-v1");
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw)[0]).toMatchObject({
      ten: "Quá hạn thẩm định",
      boLoc: "qua-han",
      loaiViec: "tham-dinh",
    });
    expect(w.get('select[aria-label="Bộ lọc đã lưu"]').text()).toContain("Quá hạn thẩm định");
  });
});

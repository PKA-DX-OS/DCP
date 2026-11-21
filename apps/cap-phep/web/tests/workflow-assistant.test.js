// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import WorkflowAssistantPanel from "../src/components/workflow/WorkflowAssistantPanel.vue";
import { assignTask, fetchOfficers, fetchWorkload, remindTask } from "../src/api/flow";

vi.mock("../src/api/flow", () => ({
  fetchOfficers: vi.fn(),
  fetchWorkload: vi.fn(),
  assignTask: vi.fn(),
  remindTask: vi.fn(),
  completeTask: vi.fn(),
  invalidateTasks: vi.fn(),
}));

const TASK = {
  id: "t1",
  name: "Thẩm định hồ sơ",
  taskDefinitionKey: "taskThamDinh",
  dueDate: "2026-11-22T17:00:00+07:00",
  assignee: "u-2",
};

const HO_SO = {
  id: "hs-1",
  ma_ho_so: "CP-001",
  ho_ten: "Nguyễn Văn Mẫu",
  dia_chi_cong_trinh: "12 Lê Lợi",
  trang_thai: "CAN_BO_SUNG",
  ly_do_bo_sung: "Bổ sung bản vẽ tầng 1",
  han_buoc_at: "2026-11-25T12:00:00+07:00",
};

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(fetchOfficers).mockResolvedValue([
    { sub: "u-1", username: "td.a", ho_ten: "Cán bộ A" },
    { sub: "u-2", username: "td.b", ho_ten: "Cán bộ B" },
  ]);
  vi.mocked(fetchWorkload).mockResolvedValue([
    { user_sub: "u-1", so_ho_so_duoc_giao: 10, dang_xu_ly: 5 },
    { user_sub: "u-2", so_ho_so_duoc_giao: 8, dang_xu_ly: 1 },
  ]);
  vi.mocked(assignTask).mockResolvedValue({});
  vi.mocked(remindTask).mockResolvedValue({});
});

afterEach(() => {
  vi.clearAllMocks();
});

function moPanel() {
  return mount(WorkflowAssistantPanel, {
    props: { task: TASK, dossier: HO_SO, token: "token", laQuanLy: true },
    attachTo: document.body,
  });
}

describe("WorkflowAssistantPanel", () => {
  test("gợi ý cán bộ ít việc và chỉ giao khi xác nhận", async () => {
    const w = moPanel();
    await flushPromises();

    expect(fetchOfficers).toHaveBeenCalledWith("token", "tham-dinh");
    expect(fetchWorkload).toHaveBeenCalledWith("token");
    expect(w.text()).toContain("Cán bộ B");
    expect(w.text()).toContain("Ít việc nhất");

    const chon = w.findAll("button").filter((b) => b.text() === "Chọn")[0];
    await chon.trigger("click");
    await w.get('input[aria-label="Lý do giao việc"]').setValue("Cân bằng tải việc");
    await w.findAll("button").find((b) => b.text() === "Xác nhận giao việc").trigger("click");
    await flushPromises();

    expect(assignTask).toHaveBeenCalledWith("token", "t1", "u-2", "Cân bằng tải việc");
  });

  test("tạo nháp theo mẫu và gửi nhắc việc nội bộ", async () => {
    const w = moPanel();
    await flushPromises();

    const nhap = w.get('textarea[aria-label="Nội dung nháp thông báo"]');
    expect(nhap.element.value).toContain("Bổ sung bản vẽ tầng 1");

    await w.get('select[aria-label="Mẫu nháp thông báo"]').setValue("da_cap");
    expect(nhap.element.value).toContain("đã được cấp giấy phép");

    await w.findAll("button").find((b) => b.text() === "Gửi nhắc việc nội bộ").trigger("click");
    await flushPromises();

    expect(remindTask).toHaveBeenCalledWith("token", "t1", expect.stringContaining("CP-001"));
    expect(w.emitted("reminded")).toHaveLength(1);
  });
});

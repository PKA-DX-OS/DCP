// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import GlobalSearch from "../src/components/GlobalSearch.vue";
import { timKiemToanCuc } from "../src/api/dh";

vi.mock("../src/api/dh", () => ({
  timKiemToanCuc: vi.fn(),
}));

const KET_QUA = {
  groups: [
    {
      type: "ho_so",
      total: 1,
      items: [
        {
          type: "ho_so",
          id: "00000000-0000-4000-8000-000000000101",
          nhan: "CP-MAU-000001",
          phu: "Đã cấp phép · 12 Đường Mẫu",
          khop: "exact",
          diem: 1,
          dossier_id: "00000000-0000-4000-8000-000000000101",
        },
      ],
    },
  ],
  took_ms: 4,
};

beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(timKiemToanCuc).mockResolvedValue({ data: KET_QUA, source: "api" });
});

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
  document.body.innerHTML = "";
});

describe("GlobalSearch", () => {
  test("gõ từ khóa thì tìm sau debounce và mở hồ sơ khi chọn", async () => {
    const w = mount(GlobalSearch, { props: { token: "token" }, attachTo: document.body });

    await w.get("input").setValue("CP-MAU-000001");
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();

    expect(timKiemToanCuc).toHaveBeenCalledWith("token", "CP-MAU-000001");
    expect(w.text()).toContain("CP-MAU-000001");
    expect(w.text()).toContain("Hồ sơ");

    const nut = w.findAll("button").find((b) => b.text().includes("CP-MAU-000001"));
    expect(nut).toBeTruthy();
    await nut.trigger("click");

    expect(w.emitted("mo-ho-so")).toEqual([["00000000-0000-4000-8000-000000000101"]]);
  });

  test("kết quả chưa gắn hồ sơ thì không mở được", async () => {
    vi.mocked(timKiemToanCuc).mockResolvedValue({
      data: {
        groups: [
          {
            type: "thua_dat",
            total: 1,
            items: [
              {
                type: "thua_dat",
                id: "00000000-0000-4000-8000-000000000301",
                nhan: "Thửa 125, tờ 18",
                phu: "Chưa gắn hồ sơ",
                khop: "exact",
                diem: 1,
                dossier_id: null,
              },
            ],
          },
        ],
        took_ms: 2,
      },
      source: "api",
    });

    const w = mount(GlobalSearch, { props: { token: "token" }, attachTo: document.body });
    await w.get("input").setValue("thửa 125");
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();

    const nut = w.findAll("button").find((b) => b.text().includes("Thửa 125"));
    expect(nut).toBeTruthy();
    expect(nut.attributes("disabled")).toBeDefined();
    await nut.trigger("click");
    expect(w.emitted("mo-ho-so")).toBeUndefined();
  });

  test("nhãn nguồn nói rõ khi đang tìm trong danh sách hiện có", async () => {
    vi.mocked(timKiemToanCuc).mockResolvedValue({ data: KET_QUA, source: "cuc-bo" });

    const w = mount(GlobalSearch, { props: { token: "token" }, attachTo: document.body });
    await w.get("input").setValue("CP-MAU");
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();

    expect(w.text()).toContain("API tìm kiếm chưa sẵn sàng");
  });
});

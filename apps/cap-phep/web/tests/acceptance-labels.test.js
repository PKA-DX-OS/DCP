// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import AcceptancePanel from "../src/features/acceptance/AcceptancePanel.vue";
import { fetchAcceptance, fetchAcceptanceHistory } from "../src/api/acceptance";
import { startWorkflow } from "../src/api/flow";

vi.mock("../src/api/acceptance", () => ({
  fetchAcceptance: vi.fn(),
  fetchAcceptanceHistory: vi.fn(),
  createMilestone: vi.fn(),
  submitAcceptanceRecord: vi.fn(),
  submitAsBuilt: vi.fn(),
}));

vi.mock("../src/api/flow", () => ({
  fetchTasks: vi.fn(async () => []),
  completeTask: vi.fn(),
  startWorkflow: vi.fn(async () => ({})),
}));

vi.mock("../src/api/files", () => ({
  uploadFile: vi.fn(),
}));

const HO_SO = {
  id: "11111111-1111-4111-8111-111111111111",
  ma_ho_so: "CP-001",
  dia_chi_cong_trinh: "Số 1 Đường Mẫu",
  trang_thai: "DA_CAP",
};

const DU_LIEU = {
  ho_so: HO_SO,
  moc_tiep_theo: "hoan_thien",
  milestones: [
    {
      id: "m1",
      loai_moc: "ket_cau",
      version: 2,
      ket_qua: "dat",
      ngay_nghiem_thu: "2026-11-20",
      bien_ban: [{ id: "b1", so_bien_ban: "BB-01", ket_luan: "Đạt yêu cầu" }],
    },
    {
      id: "m2",
      loai_moc: "mong",
      version: 1,
      ket_qua: "khong_dat",
      ngay_nghiem_thu: "2026-11-18",
      bien_ban: [],
    },
  ],
  as_built: [{ id: "a1", version: 1, ngay_nop: "2026-11-20T09:00:00+07:00", trang_thai: "cho_kiem_tra" }],
};

const LICH_SU = [
  {
    loai: "moc",
    id: "m1",
    su_kien: "ket_cau",
    trang_thai: "dat",
    noi_dung: "Kết cấu đạt yêu cầu",
    created_at: "2026-11-20T09:00:00+07:00",
  },
  {
    loai: "bien_ban",
    id: "b1",
    su_kien: "bien_ban",
    trang_thai: "BB-01",
    noi_dung: "Đạt yêu cầu",
    created_at: "2026-11-20T09:05:00+07:00",
  },
  {
    loai: "ban_ve",
    id: "a1",
    su_kien: "ban_ve_hoan_cong",
    trang_thai: "cho_kiem_tra",
    noi_dung: "Bản vẽ hoàn công",
    created_at: "2026-11-20T09:10:00+07:00",
  },
];

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(fetchAcceptance).mockResolvedValue(structuredClone(DU_LIEU));
  vi.mocked(fetchAcceptanceHistory).mockResolvedValue(structuredClone(LICH_SU));
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AcceptancePanel — nhãn và làm mới", () => {
  test("hiện nhãn tiếng Việt thay cho mã thô", async () => {
    const w = mount(AcceptancePanel, { props: { dossier: HO_SO, token: "token" } });
    await flushPromises();

    expect(w.text()).toContain("Nghiệm thu kết cấu");
    expect(w.text()).toContain("lần 2 (Đạt)");
    expect(w.text()).toContain("Mốc nghiệm thu kết cấu");
    expect(w.text()).toContain("Biên bản nghiệm thu");
    expect(w.text()).toContain("Bản vẽ hoàn công");
    expect(w.text()).toContain("Chờ kiểm tra");
    expect(w.text()).toContain("Nghiệm thu kết cấu lần 2");
    expect(w.text()).not.toContain("ket_cau");
    expect(w.text()).not.toContain("bien_ban");
    expect(w.text()).not.toContain("cho_kiem_tra");
  });

  test("bắt đầu quy trình thì tải lại panel, không chỉ tải lại danh sách việc", async () => {
    const w = mount(AcceptancePanel, { props: { dossier: HO_SO, token: "token" } });
    await flushPromises();
    expect(fetchAcceptance).toHaveBeenCalledTimes(1);

    const nut = w.findAll("button").find((b) => b.text().includes("Bắt đầu quy trình nghiệm thu"));
    expect(nut).toBeTruthy();
    await nut.trigger("click");
    await new Promise((r) => setTimeout(r, 350));
    await flushPromises();

    expect(startWorkflow).toHaveBeenCalledTimes(1);
    expect(fetchAcceptance).toHaveBeenCalledTimes(2);
  });
});

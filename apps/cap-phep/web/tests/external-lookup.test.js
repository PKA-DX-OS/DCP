// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import ExternalLookupPanel from "../src/features/link/ExternalLookupPanel.vue";
import { fetchDossierLinks } from "../src/api/mdm";

vi.mock("../src/auth", () => ({
  readRoles: vi.fn(() => ["app:cap-phep:tham-dinh"]),
}));

vi.mock("../src/api/mdm", () => ({
  fetchDossierLinks: vi.fn(async () => ({ data: null, source: "khong_co" })),
}));

const HO_SO = {
  id: "11111111-1111-4111-8111-111111111111",
  ma_ho_so: "CP-001",
  cccd: "001099001234",
  ho_ten: "Trần Văn Minh",
  dien_thoai: "0901234567",
  dia_chi_cong_trinh: "Số 1 Đường Mẫu",
  thua_dat: "Thửa 12, Tờ 4",
  dien_tich_san_m2: 120,
  ma_cong_trinh: "CT-01",
};

enableAutoUnmount(afterEach);

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.mocked(fetchDossierLinks).mockResolvedValue({ data: null, source: "khong_co" });
});

afterEach(() => {
  vi.clearAllMocks();
});

function moManHinh(vaiTro = ["app:cap-phep:tham-dinh"]) {
  return mount(ExternalLookupPanel, {
    props: { dossier: HO_SO, userToken: "token", vaiTro },
    attachTo: document.body,
  });
}

async function traCuu(w, tuKhoa) {
  const o = w.get('input[placeholder="Nhập số CCCD 12 chữ số"]');
  await o.setValue(tuKhoa);
  await w.findAll("button").find((b) => b.text() === "Tra cứu").trigger("click");
  await new Promise((r) => setTimeout(r, 400));
  await flushPromises();
}

describe("ExternalLookupPanel — H-LINK", () => {
  test("hiện dữ liệu mẫu, tra cứu dân cư và xác nhận trên phiên", async () => {
    const w = moManHinh();
    await flushPromises();
    expect(w.text()).toContain("Dữ liệu mẫu");
    expect(w.text()).toContain("API liên ngành chưa sẵn sàng");

    await traCuu(w, "001099001234");
    expect(w.text()).toContain("Khớp hồ sơ");
    expect(w.text()).toContain("0010****1234");
    expect(w.text()).not.toContain("001099001234");

    await w.findAll("button").find((b) => b.text() === "Xác nhận đối chiếu").trigger("click");
    await flushPromises();
    expect(w.text()).toContain("Đã xác nhận 1/4 nguồn");
    expect(w.findAll("button").some((b) => b.text() === "Đã xác nhận")).toBe(true);

    // Không lưu PII vào storage.
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  test("kiểm toán viên chỉ xem, không có nút xác nhận", async () => {
    const w = moManHinh(["dx:auditor"]);
    await flushPromises();
    await traCuu(w, "001099001234");
    expect(w.text()).toContain("Chỉ cán bộ nghiệp vụ được xác nhận đối chiếu");
    expect(w.findAll("button").some((b) => b.text() === "Xác nhận đối chiếu")).toBe(false);
  });

  test("API liên kết MDM thiếu thì hiện ghi chú, không chặn tra cứu", async () => {
    const w = moManHinh();
    await flushPromises();
    expect(fetchDossierLinks).toHaveBeenCalledWith("token", HO_SO.id);
    expect(w.text()).toContain("chưa sẵn sàng");
    expect(w.text()).toContain("Tra cứu");
  });
});

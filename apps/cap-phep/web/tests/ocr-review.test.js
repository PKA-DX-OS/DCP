// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import OcrReviewTab from "../src/features/ocr-review/OcrReviewTab.vue";
import { provideFeatureContext } from "../src/features/context";
import {
  fetchOcrDetail,
  fetchOcrQueue,
  mockConfirmOcr,
  mockRejectOcr,
} from "../src/api/ocr";

vi.mock("../src/auth", () => ({
  getValidToken: vi.fn(async () => "token"),
}));

vi.mock("../src/api/ocr", () => ({
  fetchOcrQueue: vi.fn(),
  fetchOcrDetail: vi.fn(),
  confirmOcr: vi.fn(),
  rejectOcr: vi.fn(),
  mockConfirmOcr: vi.fn(),
  mockRejectOcr: vi.fn(),
}));

const TOM_TAT = {
  id: "00000000-0000-4000-8000-000000001001",
  file_id: "00000000-0000-4000-8000-000000001101",
  dossier_id: "00000000-0000-4000-8000-000000000101",
  doc_type: "giay_chung_nhan_qsdd",
  status: "needs_review",
  confidence: 0.71,
  created_at: "2026-11-20T09:00:00+07:00",
};

const CHI_TIET = {
  ...TOM_TAT,
  fields: [
    { name: "so_thua", value: "125", confidence: 0.94, page: 1, bbox: [0.12, 0.31, 0.08, 0.03], edited: false },
    { name: "to_ban_do", value: "18", confidence: 0.91, page: 1, bbox: [0.32, 0.31, 0.06, 0.03], edited: false },
    { name: "dien_tich_m2", value: "82,5", confidence: 0.48, page: 1, bbox: [0.12, 0.36, 0.1, 0.03], edited: false },
  ],
  reviewed_by: null,
  reviewed_at: null,
  reject_reason: null,
  error: null,
};

function bocNoiDung() {
  return defineComponent({
    setup() {
      provideFeatureContext({
        vaiTro: ref(["app:cap-phep:mot-cua"]),
        sub: ref("u-1"),
        cd: {},
        moHoSo: vi.fn(),
        moNopHoSo: vi.fn(),
        moBoSung: vi.fn(),
      });
      return () => h(OcrReviewTab);
    },
  });
}

function moManHinh() {
  return mount(bocNoiDung(), { attachTo: document.body });
}

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(fetchOcrQueue).mockResolvedValue({
    data: { items: [TOM_TAT], page: 1, page_size: 20, total: 1 },
    source: "mock",
  });
  vi.mocked(fetchOcrDetail).mockResolvedValue({ data: structuredClone(CHI_TIET), source: "mock" });
  vi.mocked(mockConfirmOcr).mockImplementation((_id, fields) => ({
    ...structuredClone(CHI_TIET),
    status: "confirmed",
    fields: CHI_TIET.fields.map((f) => {
      const moi = fields.find((x) => x.name === f.name);
      return moi ? { ...f, value: moi.value, edited: f.edited || moi.value !== f.value } : f;
    }),
    reviewed_by: "demo.mot-cua",
    reviewed_at: "2026-11-21T09:00:00+07:00",
  }));
  vi.mocked(mockRejectOcr).mockReturnValue({
    ...structuredClone(CHI_TIET),
    status: "rejected",
    reviewed_by: "demo.mot-cua",
    reviewed_at: "2026-11-21T09:00:00+07:00",
    reject_reason: "Ảnh mờ",
  });
});

afterEach(() => vi.clearAllMocks());

describe("OcrReviewTab", () => {
  test("tải hàng chờ mẫu, hiện chi tiết và ghi rõ nguồn", async () => {
    const w = moManHinh();
    await flushPromises();

    expect(fetchOcrQueue).toHaveBeenCalled();
    expect(fetchOcrDetail).toHaveBeenCalledWith("token", TOM_TAT.id, true);
    expect(w.text()).toContain("Dữ liệu mẫu");
    expect(w.text()).toContain("Giấy chứng nhận QSDĐ");
    expect(w.text()).toContain("Số thửa");
    expect(w.findAll("tbody input")[2].element.value).toBe("82,5");
    expect(w.text()).toContain("Xác nhận kết quả");
  });

  test("503 OCR_DISABLED hiện banner dịch vụ đang tắt", async () => {
    vi.mocked(fetchOcrQueue).mockResolvedValueOnce({
      data: { items: [structuredClone(TOM_TAT)], page: 1, page_size: 20, total: 1 },
      source: "mock",
      disabled: true,
    });
    const w = moManHinh();
    await flushPromises();

    expect(w.text()).toContain("Dịch vụ OCR đang tắt");
    expect(w.text()).toContain("DH_OCR=false");
    expect(w.text()).toContain("OCR đang tắt · dữ liệu mẫu");
  });

  test("sửa trường rồi xác nhận trên bản mô phỏng", async () => {
    const w = moManHinh();
    await flushPromises();

    const inputs = w.findAll("tbody input");
    expect(inputs.length).toBe(3);
    await inputs[2].setValue("82.5");
    const nut = w.findAll("button").find((b) => b.text().includes("Xác nhận kết quả"));
    expect(nut).toBeTruthy();
    await nut.trigger("click");
    await flushPromises();

    expect(mockConfirmOcr).toHaveBeenCalledWith(TOM_TAT.id, [
      { name: "so_thua", value: "125" },
      { name: "to_ban_do", value: "18" },
      { name: "dien_tich_m2", value: "82.5" },
    ]);
    expect(w.text()).toContain("Đã xác nhận");
  });

  test("từ chối cần lý do và cập nhật trạng thái", async () => {
    const w = moManHinh();
    await flushPromises();

    const moForm = w.findAll("button").find((b) => b.text() === "Từ chối");
    await moForm.trigger("click");
    const form = w.get("form");
    await form.get("input").setValue("Ảnh mờ");
    await form.trigger("submit");
    await flushPromises();

    expect(mockRejectOcr).toHaveBeenCalledWith(TOM_TAT.id, "Ảnh mờ");
    expect(w.text()).toContain("Đã từ chối");
    expect(w.text()).toContain("Ảnh mờ");
  });

  test("đổi bộ lọc thì tải lại hàng chờ", async () => {
    const w = moManHinh();
    await flushPromises();
    vi.mocked(fetchOcrQueue).mockClear();

    await w.get("select").setValue("confirmed");
    await flushPromises();

    expect(fetchOcrQueue).toHaveBeenLastCalledWith(
      "token",
      expect.objectContaining({ status: "confirmed", page: 1, page_size: 20 }),
    );
  });
});

// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import MdmLinksPanel from "../src/components/data/MdmLinksPanel.vue";
import {
  fetchMdmCandidates,
  fetchMdmEntity,
  fetchMdmSearch,
  mergeMdmEntities,
  undoMdmMerge,
} from "../src/api/mdm";

vi.mock("../src/api/mdm", () => ({
  fetchMdmSearch: vi.fn(),
  fetchMdmEntity: vi.fn(),
  fetchMdmCandidates: vi.fn(),
  mergeMdmEntities: vi.fn(),
  undoMdmMerge: vi.fn(),
}));

const TIM = {
  items: [
    { type: "subject", id: "s1", nhan: "Nguyễn Văn An", ma: null, confidence: 0.95 },
    { type: "subject", id: "s2", nhan: "Nguyễn Văn Bình", ma: null, confidence: 0.7 },
  ],
  page: 1,
  page_size: 10,
  total: 2,
};

const CHI_TIET = {
  type: "subject",
  id: "s1",
  nhan: "Nguyễn Văn An",
  ma: null,
  confidence: 0.95,
  merged_into: null,
  thuoc_tinh: { ho_ten: "Nguyễn Văn An", dien_thoai: "0901234567", source: "ho_so" },
  ho_so: [{ dossier_id: "d1", ma_ho_so: "HS-001", trang_thai: "dang_xu_ly" }],
  external_refs: [],
};

const UNG_VIEN = [
  {
    ung_vien: { type: "subject", id: "s2", nhan: "Nguyễn Văn Bình", ma: null, confidence: 0.7 },
    confidence: 0.7,
    ly_do: ["ho_ten", "dien_thoai"],
  },
];

const KET_QUA_GOP = {
  merge_id: "99999999-9999-4999-8999-999999999999",
  entity_type: "subject",
  giu_id: "s1",
  gop_ids: ["s2"],
  trang_thai: "da_gop",
  thuc_hien_luc: "2026-11-22T13:00:00Z",
};

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(fetchMdmSearch).mockResolvedValue(structuredClone(TIM));
  vi.mocked(fetchMdmEntity).mockResolvedValue(structuredClone(CHI_TIET));
  vi.mocked(fetchMdmCandidates).mockResolvedValue(structuredClone(UNG_VIEN));
  vi.mocked(mergeMdmEntities).mockResolvedValue(structuredClone(KET_QUA_GOP));
  vi.mocked(undoMdmMerge).mockResolvedValue({ ...structuredClone(KET_QUA_GOP), trang_thai: "da_hoan_tac" });
});

afterEach(() => {
  vi.clearAllMocks();
});

function moManHinh(vaiTro = ["dx:data-steward"]) {
  return mount(MdmLinksPanel, { props: { vaiTro }, attachTo: document.body });
}

async function timVaMo(w) {
  await w.get('input[placeholder^="Ví dụ"]').setValue("Nguyễn");
  await w.get("form").trigger("submit");
  await flushPromises();
  const nutXem = w.findAll("button").find((b) => b.text() === "Xem");
  expect(nutXem).toBeTruthy();
  await nutXem.trigger("click");
  await flushPromises();
}

describe("MdmLinksPanel", () => {
  test("tìm thực thể theo loại và từ khóa", async () => {
    const w = moManHinh();
    await w.get('input[placeholder^="Ví dụ"]').setValue("Nguyễn");
    await w.get("form").trigger("submit");
    await flushPromises();

    expect(fetchMdmSearch).toHaveBeenCalledWith("subject", "Nguyễn", 1, 10);
    expect(w.text()).toContain("Nguyễn Văn An");
    expect(w.text()).toContain("Nguyễn Văn Bình");
    expect(w.text()).toContain("2 thực thể");
  });

  test("xem chi tiết và ứng viên, không lộ điện thoại", async () => {
    const w = moManHinh();
    await timVaMo(w);

    expect(fetchMdmEntity).toHaveBeenCalledWith("subject", "s1");
    expect(fetchMdmCandidates).toHaveBeenCalledWith("subject", "s1");
    expect(w.text()).toContain("HS-001");
    expect(w.text()).toContain("Ứng viên trùng");
    expect(w.text()).toContain("Họ tên");
    expect(w.text()).toContain("Điện thoại");
    expect(w.text()).toContain("Nguồn");
    expect(w.text()).not.toContain("0901234567");
  });

  test("quản trị dữ liệu gộp có lý do và hoàn tác", async () => {
    const w = moManHinh();
    await timVaMo(w);

    await w.findAll("button").find((b) => b.text() === "Gộp").trigger("click");
    await w.get('input[placeholder^="Ví dụ: cùng"]').setValue("Cùng một chủ đầu tư");
    await w.findAll("button").find((b) => b.text() === "Xác nhận gộp").trigger("click");
    await flushPromises();

    expect(mergeMdmEntities).toHaveBeenCalledWith({
      entity_type: "subject",
      giu_id: "s1",
      gop_ids: ["s2"],
      ly_do: "Cùng một chủ đầu tư",
    });
    expect(w.text()).toContain("Đã gộp");
    expect(w.text()).toContain("Hoàn tác lần gộp");

    await w.findAll("button").find((b) => b.text() === "Hoàn tác lần gộp").trigger("click");
    await flushPromises();

    expect(undoMdmMerge).toHaveBeenCalledWith(KET_QUA_GOP.merge_id);
    expect(w.text()).toContain("Đã hoàn tác");
  });

  test("lý do quá ngắn không gọi API gộp", async () => {
    const w = moManHinh();
    await timVaMo(w);

    await w.findAll("button").find((b) => b.text() === "Gộp").trigger("click");
    await w.get('input[placeholder^="Ví dụ: cùng"]').setValue("trun");
    await w.findAll("button").find((b) => b.text() === "Xác nhận gộp").trigger("click");
    await flushPromises();

    expect(mergeMdmEntities).not.toHaveBeenCalled();
    expect(w.text()).toContain("ít nhất 5 ký tự");
  });

  test("kiểm toán viên chỉ đọc, không có nút gộp", async () => {
    const w = moManHinh(["dx:auditor"]);
    await timVaMo(w);

    expect(w.text()).toContain("Ứng viên trùng");
    expect(w.findAll("button").some((b) => b.text() === "Gộp")).toBe(false);
  });
});

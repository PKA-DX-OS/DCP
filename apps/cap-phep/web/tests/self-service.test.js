// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import SelfServiceTab from "../src/features/tu-phuc-vu/SelfServiceTab.vue";
import { provideFeatureContext } from "../src/features/context";
import { fetchPermitInfo } from "../src/api/dossiers";
import { downloadFile } from "../src/api/files";
import QRCode from "qrcode";

vi.mock("../src/auth", () => ({
  getValidToken: vi.fn(async () => "token"),
}));

vi.mock("../src/api/dossiers", () => ({
  fetchPermitInfo: vi.fn(),
}));

vi.mock("../src/api/files", () => ({
  downloadFile: vi.fn(),
}));

vi.mock("qrcode", () => ({
  default: { toDataURL: vi.fn(async () => "data:image/png;base64,QRMAU") },
}));

const DS = [
  {
    id: "hs-1",
    ma_ho_so: "CP-001",
    ho_ten: "Nguyễn Văn Mẫu",
    dia_chi_cong_trinh: "12 Lê Lợi",
    trang_thai: "DA_CAP",
    buoc: "hoan_thanh",
    han_tong_at: "2026-11-30T00:00:00+07:00",
    updated_at: "2026-11-20T08:00:00+07:00",
    created_at: "2026-11-01T08:00:00+07:00",
    so_tang: 3,
    dien_tich_san_m2: 150,
  },
  {
    id: "hs-2",
    ma_ho_so: "CP-002",
    ho_ten: "Nguyễn Văn Mẫu",
    dia_chi_cong_trinh: "14 Lê Lợi",
    trang_thai: "CAN_BO_SUNG",
    buoc: "tiep_nhan",
    ly_do_bo_sung: "Bổ sung bản vẽ tầng 1",
    han_buoc_at: "2026-11-22T00:00:00+07:00",
    updated_at: "2026-11-21T08:00:00+07:00",
    created_at: "2026-11-02T08:00:00+07:00",
    so_tang: 2,
    dien_tich_san_m2: 90,
  },
  {
    id: "hs-3",
    ma_ho_so: "CP-003",
    ho_ten: "Nguyễn Văn Mẫu",
    dia_chi_cong_trinh: "16 Lê Lợi",
    trang_thai: "DANG_THAM_DINH",
    buoc: "tham_dinh",
    han_tong_at: "2026-12-01T00:00:00+07:00",
    updated_at: "2026-11-21T09:00:00+07:00",
    created_at: "2026-11-03T08:00:00+07:00",
    so_tang: 4,
    dien_tich_san_m2: 200,
  },
];

const moBoSung = vi.fn();
const moNopHoSo = vi.fn();
const moHoSo = vi.fn();
const taiHoSo = vi.fn();

function bocNoiDung(ds = DS) {
  return defineComponent({
    setup() {
      provideFeatureContext({
        vaiTro: ref(["app:cap-phep:chu-dau-tu"]),
        sub: ref("u-1"),
        cd: {
          dossiers: ref(ds),
          dangTai: ref(false),
          loi: ref(""),
          taiHoSo,
        },
        moHoSo,
        moNopHoSo,
        moBoSung,
      });
      return () => h(SelfServiceTab);
    },
  });
}

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(fetchPermitInfo).mockResolvedValue({
    so_giay_phep: "GP-001",
    ma_cong_khai: "GP-001",
    file_url: "/api/v1/docs/doc-1/download",
  });
  vi.mocked(downloadFile).mockResolvedValue(new Blob(["pdf"], { type: "application/pdf" }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  vi.spyOn(window.URL, "createObjectURL").mockReturnValue("blob:test");
  vi.spyOn(window.URL, "revokeObjectURL").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

describe("SelfServiceTab", () => {
  test("hiện tổng quan, tiến độ và CTA theo trạng thái", async () => {
    const w = mount(bocNoiDung(), { attachTo: document.body });
    await flushPromises();

    expect(w.text()).toContain("Tổng hồ sơ");
    expect(w.text()).toContain("Cần bổ sung");
    expect(w.text()).toContain("Đã cấp giấy phép");
    expect(w.text()).toContain("Bổ sung ngay");
    expect(w.text()).toContain("Tải giấy phép");
    expect(w.text()).toContain("QR tra cứu");
  });

  test("bổ sung hồ sơ gọi đúng hồ sơ cần bổ sung", async () => {
    const w = mount(bocNoiDung(), { attachTo: document.body });
    await flushPromises();

    await w.findAll("button").find((b) => b.text() === "Bổ sung ngay").trigger("click");
    expect(moBoSung).toHaveBeenCalledWith(expect.objectContaining({ id: "hs-2" }));
  });

  test("tải giấy phép lấy file qua token và đặt tên đúng", async () => {
    const w = mount(bocNoiDung(), { attachTo: document.body });
    await flushPromises();

    await w.findAll("button").find((b) => b.text() === "Tải giấy phép").trigger("click");
    await flushPromises();

    expect(fetchPermitInfo).toHaveBeenCalledWith("token", "hs-1");
    expect(downloadFile).toHaveBeenCalledWith("token", "/docs/doc-1/download");
    expect(window.URL.createObjectURL).toHaveBeenCalled();
  });

  test("mở QR tra cứu từ mã công khai", async () => {
    const w = mount(bocNoiDung(), { attachTo: document.body });
    await flushPromises();

    await w.findAll("button").find((b) => b.text() === "QR tra cứu").trigger("click");
    await flushPromises();

    expect(fetchPermitInfo).toHaveBeenCalledWith("token", "hs-1");
    expect(QRCode.toDataURL).toHaveBeenCalled();
    expect(w.text()).toContain("QR tra cứu CP-001");
    expect(w.get("img").attributes("src")).toContain("data:image/png;base64,QRMAU");
  });

  test("trạng thái rỗng cho phép nộp hồ sơ mới", async () => {
    const w = mount(bocNoiDung([]), { attachTo: document.body });
    await flushPromises();

    expect(w.text()).toContain("Bạn chưa có hồ sơ nào");
    await w.findAll("button").find((b) => b.text() === "Nộp hồ sơ mới").trigger("click");
    expect(moNopHoSo).toHaveBeenCalled();
  });
});

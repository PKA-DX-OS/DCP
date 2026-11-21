// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, describe, expect, test } from "vitest";
import { enableAutoUnmount, mount } from "@vue/test-utils";
import CreateDossierModal from "../src/components/CreateDossierModal.vue";

const HO_SO = {
  id: "00000000-0000-4000-8000-000000000101",
  ma_ho_so: "CP-MAU-000001",
  tenant: "phuong-mau",
  ho_ten: "Nguyễn Văn Mẫu",
  cccd: "001099123456",
  dien_thoai: "0901234567",
  dia_chi_cong_trinh: "12 Đường Mẫu, Phường Mẫu",
  thua_dat: "Thửa 125, Tờ 18",
  so_tang: 3,
  dien_tich_san_m2: 150,
  khu_quan_ly_kien_truc: true,
  trang_thai: "DA_CAP",
  created_at: "2026-11-01T08:00:00+07:00",
  updated_at: "2026-11-01T08:00:00+07:00",
};

enableAutoUnmount(afterEach);

function moChat() {
  return mount(CreateDossierModal, {
    props: {
      submitting: false,
      requirements: [],
      errors: [],
      dossiers: [HO_SO],
      tenNguoiDung: "Nguyễn Văn Tài Khoản",
      nguoiDungId: "u-1",
    },
    attachTo: document.body,
  });
}

/** Bản nháp nằm ở module của trang nên dọn trước mỗi test để các test độc lập. */
async function moChatSach() {
  const w = moChat();
  const xoa = w.findAll("button").find((b) => b.text() === "Xóa bản nháp");
  if (xoa) await xoa.trigger("click");
  return w;
}

describe("điền nhanh form nộp hồ sơ", () => {
  test("điền các ô đang trống từ hồ sơ gần nhất", async () => {
    const w = await moChatSach();
    const nut = w.findAll("button").find((b) => b.text().includes("Điền ô đang trống"));
    expect(nut).toBeTruthy();
    await nut.trigger("click");

    expect(w.get("#input-ho-ten").element.value).toBe(HO_SO.ho_ten);
    expect(w.get("#input-cccd").element.value).toBe(HO_SO.cccd);
    expect(w.get("#input-dien-thoai").element.value).toBe(HO_SO.dien_thoai);
    expect(w.get("#input-dia-chi").element.value).toBe(HO_SO.dia_chi_cong_trinh);
    expect(w.get("#input-thua-dat").element.value).toBe(HO_SO.thua_dat);
    expect(w.get("#input-so-tang").element.value).toBe("3");
    expect(w.get("#input-dien-tich").element.value).toBe("150");
    expect(w.text()).toContain("Đã điền");
  });

  test("không ghi đè dữ liệu đã nhập", async () => {
    const w = await moChatSach();
    await w.get("#input-ho-ten").setValue("Tên Tôi Đã Nhập");
    const nut = w.findAll("button").find((b) => b.text().includes("Điền ô đang trống"));
    await nut.trigger("click");

    expect(w.get("#input-ho-ten").element.value).toBe("Tên Tôi Đã Nhập");
    expect(w.get("#input-cccd").element.value).toBe(HO_SO.cccd);
  });

  test("điền họ tên từ tài khoản khi ô còn trống", async () => {
    const w = await moChatSach();
    const nut = w.findAll("button").find((b) => b.text() === "Điền họ tên");
    expect(nut).toBeTruthy();
    await nut.trigger("click");
    expect(w.get("#input-ho-ten").element.value).toBe("Nguyễn Văn Tài Khoản");
  });

  test("cảnh báo trùng CCCD và thửa đất, mở được hồ sơ đã có", async () => {
    const w = await moChatSach();
    await w.get("#input-cccd").setValue(HO_SO.cccd);
    await w.get("#input-thua-dat").setValue(HO_SO.thua_dat);

    expect(w.text()).toContain("Có hồ sơ trùng CCCD và thửa đất");
    const mo = w.findAll("button").find((b) => b.text() === "Mở hồ sơ");
    expect(mo).toBeTruthy();
    await mo.trigger("click");
    expect(w.emitted("mo-ho-so")).toEqual([[HO_SO.id, HO_SO.ma_ho_so]]);
  });
});

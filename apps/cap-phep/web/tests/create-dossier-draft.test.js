// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { enableAutoUnmount, mount } from "@vue/test-utils";
import CreateDossierModal from "../src/components/CreateDossierModal.vue";
import { formNopTrong, khoaBanNhap } from "../src/utils/nop-ho-so";

const KHOA = khoaBanNhap("u-1");

enableAutoUnmount(afterEach);

beforeEach(() => sessionStorage.clear());
afterEach(() => sessionStorage.clear());

describe("bản nháp nộp hồ sơ", () => {
  test("khôi phục bản nháp sau khi tải lại trang và cho phép xóa", async () => {
    const form = {
      ...formNopTrong(),
      ho_ten: "Nguyễn Văn Khôi",
      cccd: "001099123456",
      dien_thoai: "0901234567",
      dia_chi_cong_trinh: "12 Lê Lợi, Phường Mẫu",
      thua_dat: "Thửa 12, Tờ 34",
      so_tang: 3,
      dien_tich_san_m2: 150,
    };
    sessionStorage.setItem(KHOA, JSON.stringify({ at: Date.now(), form }));

    const w = mount(CreateDossierModal, {
      props: { submitting: false, requirements: [], errors: [], nguoiDungId: "u-1" },
      attachTo: document.body,
    });

    expect(w.text()).toContain("Đã khôi phục bản nháp");
    expect(w.get("#input-ho-ten").element.value).toBe("Nguyễn Văn Khôi");
    expect(w.get("#input-cccd").element.value).toBe("001099123456");
    expect(w.get("#input-so-tang").element.value).toBe("3");

    const nutXoa = w.findAll("button").find((b) => b.text().includes("Xóa bản nháp"));
    expect(nutXoa).toBeTruthy();
    await nutXoa.trigger("click");
    expect(w.get("#input-ho-ten").element.value).toBe("");
    expect(sessionStorage.getItem(KHOA)).toBeNull();
  });
});

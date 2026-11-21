// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, describe, expect, test } from "vitest";
import { enableAutoUnmount, mount } from "@vue/test-utils";
import SupplementModal from "../src/components/SupplementModal.vue";

enableAutoUnmount(afterEach);

const HO_SO = {
  id: "00000000-0000-4000-8000-000000000101",
  ma_ho_so: "CP-MAU-000001",
  ly_do_bo_sung: "",
  han_buoc_at: null,
  dia_chi_cong_trinh: "12 Lê Lợi, Phường Mẫu",
  thua_dat: "Thửa 12, Tờ 34",
  so_tang: 3,
  dien_tich_san_m2: 150,
  khu_quan_ly_kien_truc: true,
};

describe("kiểm tra form bổ sung hồ sơ", () => {
  test("báo lỗi tại chỗ và không gửi khi số tầng/diện tích sai", async () => {
    const w = mount(SupplementModal, {
      props: { dossier: HO_SO, submitting: false },
      attachTo: document.body,
    });

    await w.get("#input-bo-sung-so-tang").setValue("9");
    await w.get("#input-bo-sung-dien-tich").setValue("0");
    await w.get("#form-bo-sung-ho-so").trigger("submit");

    expect(w.text()).toContain("Số tầng phải từ 1 đến 5");
    expect(w.text()).toContain("Diện tích sàn phải lớn hơn 0");
    expect(w.emitted("submit")).toBeUndefined();
  });

  test("dữ liệu hợp lệ thì gửi đúng form", async () => {
    const w = mount(SupplementModal, {
      props: { dossier: HO_SO, submitting: false },
      attachTo: document.body,
    });

    await w.get("#form-bo-sung-ho-so").trigger("submit");

    const payload = w.emitted("submit")?.[0]?.[0];
    expect(payload?.form.so_tang).toBe(3);
    expect(payload?.form.dien_tich_san_m2).toBe(150);
  });
});

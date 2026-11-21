// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, describe, expect, test } from "vitest";
import { enableAutoUnmount, mount } from "@vue/test-utils";
import CreateDossierModal from "../src/components/CreateDossierModal.vue";

enableAutoUnmount(afterEach);

function moChat() {
  return mount(CreateDossierModal, {
    props: { submitting: false, requirements: [], errors: [], nguoiDungId: "u-validation" },
    attachTo: document.body,
  });
}

describe("kiểm tra dữ liệu form nộp hồ sơ", () => {
  test("báo lỗi tại chỗ và không gửi khi CCCD, điện thoại, địa chỉ, thửa đất sai", async () => {
    const w = moChat();
    await w.get("#input-ho-ten").setValue("A");
    await w.get("#input-cccd").setValue("123");
    await w.get("#input-dien-thoai").setValue("123");
    await w.get("#input-dia-chi").setValue("abc");
    await w.get("#input-thua-dat").setValue("abc");
    await w.get("#input-so-tang").setValue("7");
    await w.get("#input-dien-tich").setValue("0");

    await w.get("#form-nop-ho-so").trigger("submit");

    const text = w.text();
    expect(text).toContain("Kiểm tra lại thông tin");
    expect(text).toContain("Họ và tên phải có ít nhất 3 ký tự");
    expect(text).toContain("CCCD phải gồm đúng 12 chữ số");
    expect(text).toContain("Số điện thoại phải bắt đầu");
    expect(text).toContain("Địa chỉ công trình phải có ít nhất 5 ký tự");
    expect(text).toContain("Thửa đất, tờ bản đồ cần có số");
    expect(text).toContain("Số tầng phải từ 1 đến 5");
    expect(text).toContain("Diện tích sàn phải lớn hơn 0");
    expect(w.get("#input-cccd").attributes("aria-invalid")).toBe("true");
    expect(w.emitted("submit")).toBeUndefined();
  });

  test("chuẩn hóa CCCD/điện thoại trước khi gửi", async () => {
    const w = moChat();
    await w.get("#input-ho-ten").setValue("Nguyễn Văn A");
    await w.get("#input-cccd").setValue("0010 9912 3456");
    await w.get("#input-dien-thoai").setValue("+84 90 123 4567");
    await w.get("#input-dia-chi").setValue("12 Lê Lợi, Phường Mẫu");
    await w.get("#input-thua-dat").setValue("Thửa 12, Tờ 34");
    await w.get("#input-so-tang").setValue("3");
    await w.get("#input-dien-tich").setValue("150");

    await w.get("#form-nop-ho-so").trigger("submit");

    const payload = w.emitted("submit")?.[0]?.[0];
    expect(payload).toBeTruthy();
    expect(payload.cccd).toBe("001099123456");
    expect(payload.dien_thoai).toBe("0901234567");
  });
});

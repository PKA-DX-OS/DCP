// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** B-TEST-01: hành vi component design system khi gắn vào DOM (happy-dom, @vue/test-utils). */
import { afterEach, describe, expect, test } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import Button from "../src/design-system/components/Button.vue";
import Input from "../src/design-system/components/Input.vue";
import Pagination from "../src/design-system/components/Pagination.vue";
import Modal from "../src/design-system/components/Modal.vue";
import Tabs from "../src/design-system/components/Tabs.vue";
import StatusBadge from "../src/design-system/components/StatusBadge.vue";
import EmptyState from "../src/design-system/components/EmptyState.vue";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("Button", () => {
  test("phát click, mặc định type=button", async () => {
    const w = mount(Button, { slots: { default: "Lưu" } });
    expect(w.attributes("type")).toBe("button");
    expect(w.text()).toBe("Lưu");
    await w.trigger("click");
    expect(w.emitted("click")).toHaveLength(1);
  });
  test("đang tải thì khoá nút và báo aria-busy", () => {
    const w = mount(Button, { props: { loading: true }, slots: { default: "Gửi" } });
    expect(w.attributes("disabled")).toBeDefined();
    expect(w.attributes("aria-busy")).toBe("true");
  });
  test("disabled thì không phát click", async () => {
    const w = mount(Button, { props: { disabled: true }, slots: { default: "Xoá" } });
    await w.trigger("click");
    expect(w.emitted("click")).toBeUndefined();
  });
});

describe("Input", () => {
  test("v-model hai chiều và nhãn gắn với ô", async () => {
    const w = mount(Input, { props: { label: "Họ tên", modelValue: "", "onUpdate:modelValue": (v) => w.setProps({ modelValue: v }) } });
    const input = w.get("input");
    expect(w.get("label").attributes("for")).toBe(input.attributes("id"));
    await input.setValue("Nguyễn Văn Minh");
    expect(w.props("modelValue")).toBe("Nguyễn Văn Minh");
  });
  test("có lỗi thì aria-invalid và aria-describedby trỏ tới dòng lỗi", () => {
    const w = mount(Input, { props: { label: "CCCD", error: "Cần 12 chữ số", id: "cccd" } });
    const input = w.get("input");
    expect(input.attributes("aria-invalid")).toBe("true");
    expect(input.attributes("aria-describedby")).toBe("cccd-loi");
    expect(w.get("#cccd-loi").text()).toContain("Cần 12 chữ số");
  });
});

describe("Pagination", () => {
  test("bấm trang sau thì cập nhật v-model, không vượt trang cuối", async () => {
    const w = mount(Pagination, {
      props: { total: 45, pageSize: 20, modelValue: 1, "onUpdate:modelValue": (v) => w.setProps({ modelValue: v }) },
    });
    const sau = w.findAll("button").find((b) => /sau|tiếp|›|»/i.test(b.attributes("aria-label") || b.text()));
    expect(sau).toBeTruthy();
    await sau.trigger("click");
    expect(w.props("modelValue")).toBe(2);
    await sau.trigger("click");
    await sau.trigger("click");
    expect(w.props("modelValue")).toBe(3);
  });
});

describe("Modal", () => {
  test("mở thì có role dialog gắn tiêu đề; bấm Đóng thì tắt", async () => {
    const w = mount(Modal, {
      props: { title: "Xác nhận từ chối", open: true, "onUpdate:open": (v) => w.setProps({ open: v }) },
      slots: { default: "<p>Nội dung</p>" },
      attachTo: document.body,
    });
    await nextTick();
    const dlg = document.querySelector('[role="dialog"]');
    expect(dlg).not.toBeNull();
    expect(dlg.getAttribute("aria-modal")).toBe("true");
    const tieuDe = document.getElementById(dlg.getAttribute("aria-labelledby"));
    expect(tieuDe.textContent).toBe("Xác nhận từ chối");
    document.querySelector('button[aria-label="Đóng"]').click();
    await nextTick();
    expect(w.props("open")).toBe(false);
    w.unmount();
  });
  test("đóng thì không còn trong DOM", async () => {
    const w = mount(Modal, { props: { title: "X", open: false }, attachTo: document.body });
    await nextTick();
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    w.unmount();
  });
});

describe("Tabs", () => {
  const tabs = [
    { key: "a", label: "Thông tin" },
    { key: "b", label: "Giấy tờ", disabled: true },
    { key: "c", label: "Lịch sử", count: 3 },
  ];
  test("mũi tên phải bỏ qua tab bị khoá, End về tab cuối, aria-selected đúng", async () => {
    const w = mount(Tabs, {
      props: { tabs, modelValue: "a", "onUpdate:modelValue": (v) => w.setProps({ modelValue: v }) },
      attachTo: document.body,
    });
    const nut = () => w.findAll('[role="tab"]');
    expect(nut()).toHaveLength(3);
    expect(nut()[0].attributes("aria-selected")).toBe("true");
    await nut()[0].trigger("keydown", { key: "ArrowRight" });
    expect(w.props("modelValue")).toBe("c");
    await nut()[2].trigger("keydown", { key: "Home" });
    expect(w.props("modelValue")).toBe("a");
    await nut()[0].trigger("keydown", { key: "End" });
    expect(w.props("modelValue")).toBe("c");
    expect(nut()[2].text()).toContain("3");
    w.unmount();
  });
});

describe("StatusBadge và EmptyState", () => {
  test("nhãn trạng thái hiện chữ, màu theo nhóm trạng thái", () => {
    const dat = mount(StatusBadge, { props: { status: "DA_CAP", label: "Đã cấp phép" } });
    const loi = mount(StatusBadge, { props: { status: "TU_CHOI", label: "Từ chối" } });
    expect(dat.text()).toContain("Đã cấp phép");
    expect(dat.classes().join(" ")).not.toBe(loi.classes().join(" "));
  });
  test("trạng thái rỗng có tiêu đề, mô tả và nút hành động", () => {
    const w = mount(EmptyState, {
      props: { title: "Chưa có hồ sơ nào", description: "Bấm Nộp hồ sơ mới để bắt đầu" },
      slots: { default: "<button>Nộp hồ sơ mới</button>" },
    });
    expect(w.text()).toContain("Chưa có hồ sơ nào");
    expect(w.text()).toContain("Bấm Nộp hồ sơ mới để bắt đầu");
    expect(w.find("button").text()).toBe("Nộp hồ sơ mới");
  });
});

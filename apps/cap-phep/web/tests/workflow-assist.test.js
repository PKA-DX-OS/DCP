// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import {
  loaiNhapMacDinh,
  taoNhapThongBao,
  vaiGoiY,
  xepHangCanBo,
} from "../src/utils/workflow-assist";

const HO_SO = {
  id: "hs-1",
  ma_ho_so: "CP-001",
  ho_ten: "Nguyễn Văn Mẫu",
  dia_chi_cong_trinh: "12 Lê Lợi",
  trang_thai: "CAN_BO_SUNG",
  ly_do_bo_sung: "Bổ sung bản vẽ tầng 1",
  han_buoc_at: "2026-11-25T12:00:00+07:00",
};

describe("gợi ý vai theo loại việc", () => {
  test("ánh xạ nhóm việc sang vai", () => {
    expect(vaiGoiY("taskKiemTraHopLe")).toBe("mot-cua");
    expect(vaiGoiY("taskChoBoSung")).toBe("mot-cua");
    expect(vaiGoiY("taskThamDinhHoSo")).toBe("tham-dinh");
    expect(vaiGoiY("taskKiemTraQuyHoach")).toBe("tham-dinh");
    expect(vaiGoiY("taskDuyetCapPhep")).toBe("lanh-dao");
    expect(vaiGoiY("taskPheDuyet")).toBe("lanh-dao");
    expect(vaiGoiY("taskNghiemThuMong")).toBe("tham-dinh");
    expect(vaiGoiY("taskKiemTraHienTruong")).toBe("trat-tu-xd");
  });

  test("xếp cán bộ ít việc đang xử lý trước, khớp username", () => {
    const ds = xepHangCanBo(
      [
        { sub: "u-1", username: "td.a", ho_ten: "Cán bộ A" },
        { sub: "u-2", username: "td.b", ho_ten: "Cán bộ B" },
        { sub: "u-3", username: "td.c", ho_ten: "Cán bộ C" },
      ],
      [
        { user_sub: "u-1", so_ho_so_duoc_giao: 10, dang_xu_ly: 5 },
        { user_sub: "td.b", so_ho_so_duoc_giao: 8, dang_xu_ly: 1 },
        { user_sub: "u-3", so_ho_so_duoc_giao: 6, dang_xu_ly: 2 },
      ],
    );
    expect(ds.map((x) => x.sub)).toEqual(["u-2", "u-3", "u-1"]);
    expect(ds[0].dangXuLy).toBe(1);
  });
});

describe("nháp thông báo", () => {
  test("chọn mẫu mặc định theo trạng thái", () => {
    expect(loaiNhapMacDinh(HO_SO)).toBe("nhac_bo_sung");
    expect(loaiNhapMacDinh({ ...HO_SO, trang_thai: "DA_CAP" })).toBe("da_cap");
    expect(loaiNhapMacDinh({ ...HO_SO, trang_thai: "DANG_THAM_DINH" })).toBe("tiep_nhan");
  });

  test("nhắc bổ sung có mã hồ sơ, lý do và hạn", () => {
    const text = taoNhapThongBao("nhac_bo_sung", HO_SO);
    expect(text).toContain("CP-001");
    expect(text).toContain("Bổ sung bản vẽ tầng 1");
    expect(text).toContain("25/11/2026");
    expect(text).toContain("Nội dung nháp");
  });

  test("nhắc việc nội bộ dùng tên việc và hạn việc", () => {
    const text = taoNhapThongBao("nhac_viec", HO_SO, {
      id: "t1",
      name: "Thẩm định hồ sơ",
      taskDefinitionKey: "taskThamDinh",
      dueDate: "2026-11-24T17:00:00+07:00",
    });
    expect(text).toContain("Thẩm định hồ sơ");
    expect(text).toContain("24/11/2026");
  });
});

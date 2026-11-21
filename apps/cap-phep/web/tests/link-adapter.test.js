// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import { giaTriMacDinh, nguonMeta, traCuuMock, uuidTuChuoi } from "../src/features/link/adapter";

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
  ma_dinh_danh_dia_diem: "790101000001",
};

describe("H-LINK adapter", () => {
  test("giá trị mặc định lấy từ hồ sơ theo từng nguồn", () => {
    expect(giaTriMacDinh(HO_SO, "dan_cu")).toBe("001099001234");
    expect(giaTriMacDinh(HO_SO, "dat_dai")).toBe("Thửa 12, Tờ 4");
    expect(giaTriMacDinh(HO_SO, "thue")).toBe("001099001234");
    expect(giaTriMacDinh(HO_SO, "pccc")).toBe("CT-01");
    expect(giaTriMacDinh(null, "dan_cu")).toBe("");
    expect(nguonMeta("mep").value).toBe("dan_cu");
  });

  test("dân cư khớp thì che CCCD/điện thoại, không lộ dữ liệu đầy đủ", () => {
    const kq = traCuuMock("dan_cu", "001099001234", HO_SO);
    expect(kq.trang_thai).toBe("khop");
    expect(kq.truong.find((x) => x.nhan === "CCCD")?.gia_tri).toBe("0010****1234");
    expect(kq.truong.find((x) => x.nhan === "Điện thoại")?.gia_tri).toBe("0901***567");
    const json = JSON.stringify(kq);
    expect(json).not.toContain("001099001234");
    expect(json).not.toContain("0901234567");
  });

  test("CCCD khác 12 số đã có trong hồ sơ thì báo không khớp", () => {
    const kq = traCuuMock("dan_cu", "001099999999", HO_SO);
    expect(kq.trang_thai).toBe("khong_khop");
    expect(JSON.stringify(kq)).not.toContain("001099999999");
  });

  test("đất đai so khớp thửa/tờ", () => {
    expect(traCuuMock("dat_dai", "Thửa 12, Tờ 4", HO_SO).trang_thai).toBe("khop");
    expect(traCuuMock("dat_dai", "Thửa 99", HO_SO).trang_thai).toBe("khong_khop");
  });

  test("thuế và PCCC trả kết quả mẫu đã che", () => {
    const thue = traCuuMock("thue", "001099001234", HO_SO);
    expect(thue.trang_thai).toBe("khop");
    expect(thue.truong.find((x) => x.nhan === "Mã số thuế")?.gia_tri).toBe("••••1234");
    const pccc = traCuuMock("pccc", "CT-01", HO_SO);
    expect(pccc.trang_thai).toBe("khop");
    expect(pccc.truong.find((x) => x.nhan === "Số giấy chứng nhận")?.gia_tri).toMatch(/^PCCC-2026-\d{4}$/);
  });

  test("ô trống trả không tìm thấy; UUID mock ổn định và đúng định dạng", () => {
    expect(traCuuMock("dan_cu", "", HO_SO).trang_thai).toBe("khong_thay");
    const a = uuidTuChuoi("dan_cu:001099001234");
    const b = uuidTuChuoi("dan_cu:001099001234");
    expect(a).toBe(b);
    expect(a).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-8[0-9a-f]{3}-[0-9a-f]{12}$/);
  });
});

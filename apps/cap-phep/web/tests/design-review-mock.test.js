// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import { createMockApi } from "../src/features/design-review/mock";

const HS = "7a1c2e00-0000-4000-8000-000000000001";

describe("API 5.2 giả lập", () => {
  test("mặc định trả phiên bản mới nhất (v2) đủ bộ môn bắt buộc", async () => {
    const api = createMockApi();
    const tt = await api.trangThaiThamDinh({ p_ho_so_id: HS });
    expect(tt.so_phien_ban).toBe(2);
    expect(tt.thieu_bo_mon).toEqual([]);
    expect(tt.ket_luan).toBe("dat");
    const ds = await api.dsBanVe({ p_ho_so_id: HS });
    expect(ds.nhom.map((n) => n.bo_mon)).toEqual(["kien_truc", "ket_cau", "mep", "pccc"]);
    expect(ds.nhom.find((n) => n.bo_mon === "ket_cau").ban_ve).toHaveLength(2);
  });

  test("xem lại phiên bản 1: thiếu kết cấu", async () => {
    const api = createMockApi();
    const [v2, v1] = await api.dsPhienBan({ p_ho_so_id: HS });
    expect([v2.so_phien_ban, v1.so_phien_ban]).toEqual([2, 1]);
    const ds = await api.dsBanVe({ p_ho_so_id: HS, p_phien_ban_id: v1.id });
    expect(ds.nhom.find((n) => n.bo_mon === "ket_cau").ban_ve).toEqual([]);
  });

  test("phiên bản mới: thêm bản vẽ, trạng thái chờ thẩm định, khóa idempotency không tạo trùng", async () => {
    const api = createMockApi("Nguyễn Văn Minh");
    const a = await api.taoPhienBan({ p_ho_so_id: HS, p_mo_ta: "Sửa mặt đứng", p_idempotency_key: "k1" });
    const b = await api.taoPhienBan({ p_ho_so_id: HS, p_mo_ta: "Sửa mặt đứng", p_idempotency_key: "k1" });
    expect(b.id).toBe(a.id);
    expect(a.so_phien_ban).toBe(3);
    await api.themBanVe({ p_phien_ban_id: a.id, p_bo_mon: "kien_truc", p_ten: "KT-02 Mặt đứng", p_file_id: "f" });
    const tt = await api.trangThaiThamDinh({ p_ho_so_id: HS });
    expect(tt.thieu_bo_mon).toEqual(["ket_cau", "mep"]);
    expect(tt.ket_luan).toBe("khong_dat");
  });

  test("nhận xét: thêm, lọc, xử lý một lần", async () => {
    const api = createMockApi("Thẩm định viên");
    const ds = await api.dsBanVe({ p_ho_so_id: HS });
    const bv = ds.nhom[0].ban_ve[0];
    const nx = await api.themNhanXet({ p_ban_ve_id: bv.id, p_noi_dung: "Ghi rõ cao độ.", p_muc_do: "canh_bao" });
    expect(nx.trang_thai).toBe("mo");
    const loc = await api.dsNhanXet({ p_phien_ban_id: bv.phien_ban_id, p_muc_do: "canh_bao" });
    expect(loc.map((x) => x.id)).toEqual([nx.id]);
    await api.xuLyNhanXet({ p_nhan_xet_id: nx.id, p_ghi_chu: "Đã sửa" });
    await expect(api.xuLyNhanXet({ p_nhan_xet_id: nx.id })).rejects.toMatchObject({ code: "PT409" });
  });

  test("hai phiên làm việc không dùng chung dữ liệu", async () => {
    const a = createMockApi();
    const b = createMockApi();
    await a.taoPhienBan({ p_ho_so_id: HS, p_mo_ta: "x" });
    expect((await b.dsPhienBan({ p_ho_so_id: HS })).length).toBe(2);
  });
});

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiJson } from "../../api/client";
import { createMockApi, MOCK_ENABLED } from "./mock";
import type { DesignReviewApi } from "./types";

/** Tạo client 5.2 theo token; mock chỉ bật khi VITE_MOCK_DESIGN_REVIEW=1. */
export function createDesignReviewApi(token: string, nguoi = "Người dùng thử"): DesignReviewApi {
  if (MOCK_ENABLED) return createMockApi(nguoi);
  const goi = <T>(path: string, body: unknown, fallback: string): Promise<T> =>
    apiJson<T>(path, { token, method: "POST", body }, fallback);
  return {
    dsBoMon: () =>
      apiJson("/rest/bo_mon_thiet_ke?select=ma,ten,bat_buoc,thu_tu&order=thu_tu.asc", { token }, "Lỗi tải danh mục bộ môn"),
    taoPhienBan: (b) => goi("/rest/rpc/tao_phien_ban", b, "Lỗi tạo phiên bản thiết kế"),
    themBanVe: (b) => goi("/rest/rpc/them_ban_ve", b, "Lỗi thêm bản vẽ"),
    dsBanVe: (b) => goi("/rest/rpc/ds_ban_ve", b, "Lỗi tải danh sách bản vẽ"),
    dsPhienBan: (b) => goi("/rest/rpc/ds_phien_ban", b, "Lỗi tải danh sách phiên bản"),
    danhGiaBanVe: (b) => goi("/rest/rpc/danh_gia_ban_ve", b, "Lỗi đánh giá bản vẽ"),
    themNhanXet: (b) => goi("/rest/rpc/them_nhan_xet", b, "Lỗi thêm nhận xét"),
    xuLyNhanXet: (b) => goi("/rest/rpc/xu_ly_nhan_xet", b, "Lỗi xử lý nhận xét"),
    dsNhanXet: (b) => goi("/rest/rpc/ds_nhan_xet", b, "Lỗi tải nhận xét"),
    trangThaiThamDinh: (b) => goi("/rest/rpc/trang_thai_tham_dinh", b, "Lỗi tải trạng thái thẩm định"),
  };
}

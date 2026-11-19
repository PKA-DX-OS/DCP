// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Tên gọn cho kiểu sinh từ contract 5.2 (contracts/design-review.yaml). */
import type { components, operations } from "./schema.gen";

type S = components["schemas"];

export type MaBoMon = S["MaBoMon"];
export type MucDo = S["MucDo"];
export type BoMon = S["BoMon"];
export type PhienBan = S["PhienBan"];
export type PhienBanDayDu = S["PhienBanDayDu"];
export type BanVe = S["BanVe"];
export type NhomBoMon = S["NhomBoMon"];
export type DanhSachBanVe = S["DanhSachBanVe"];
export type NhanXet = S["NhanXet"];
export type TrangThaiBoMon = S["TrangThaiBoMon"];
export type TrangThaiThamDinh = S["TrangThaiThamDinh"];
export type LoiPostgrest = S["LoiPostgrest"];

type Body<K extends keyof operations> = operations[K] extends { requestBody: { content: { "application/json": infer B } } }
  ? B
  : never;

export type TaoPhienBanBody = Body<"tao_phien_ban">;
export type ThemBanVeBody = Body<"them_ban_ve">;
export type DsBanVeBody = Body<"ds_ban_ve">;
export type DsPhienBanBody = Body<"ds_phien_ban">;
export type DanhGiaBanVeBody = Body<"danh_gia_ban_ve">;
export type ThemNhanXetBody = Body<"them_nhan_xet">;
export type XuLyNhanXetBody = Body<"xu_ly_nhan_xet">;
export type DsNhanXetBody = Body<"ds_nhan_xet">;
export type TrangThaiThamDinhBody = Body<"trang_thai_tham_dinh">;

/** Mọi lời gọi API 5.2; bản thật (api.ts, B-REVIEW-04) và bản mock (mock.ts) cùng hình dạng này. */
export interface DesignReviewApi {
  dsBoMon(): Promise<BoMon[]>;
  taoPhienBan(body: TaoPhienBanBody): Promise<PhienBan>;
  themBanVe(body: ThemBanVeBody): Promise<BanVe>;
  dsBanVe(body: DsBanVeBody): Promise<DanhSachBanVe>;
  dsPhienBan(body: DsPhienBanBody): Promise<PhienBanDayDu[]>;
  danhGiaBanVe(body: DanhGiaBanVeBody): Promise<BanVe>;
  themNhanXet(body: ThemNhanXetBody): Promise<NhanXet>;
  xuLyNhanXet(body: XuLyNhanXetBody): Promise<NhanXet>;
  dsNhanXet(body: DsNhanXetBody): Promise<NhanXet[]>;
  trangThaiThamDinh(body: TrangThaiThamDinhBody): Promise<TrangThaiThamDinh>;
}

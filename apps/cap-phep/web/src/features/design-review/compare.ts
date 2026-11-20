// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { BanVe, MaBoMon, PhienBanDayDu } from "./types";

export interface BanVeDoi {
  cu: BanVe;
  moi: BanVe;
}

export interface SoSanhPhienBan {
  them: BanVe[];
  bo: BanVe[];
  doi: BanVeDoi[];
  thieuBoMon: MaBoMon[];
}

const khoa = (bv: BanVe) => `${bv.bo_mon}|${bv.ten}`;

/** So sánh metadata/hash giữa hai phiên bản; không đọc nội dung CAD. */
export function soSanhPhienBan(
  cu: PhienBanDayDu,
  moi: PhienBanDayDu,
  boMonBatBuoc: readonly MaBoMon[],
): SoSanhPhienBan {
  const cuTheoKhoa = new Map(cu.ban_ve.map((bv) => [khoa(bv), bv]));
  const moiTheoKhoa = new Map(moi.ban_ve.map((bv) => [khoa(bv), bv]));
  const them: BanVe[] = [];
  const doi: BanVeDoi[] = [];

  for (const [k, bvMoi] of moiTheoKhoa) {
    const bvCu = cuTheoKhoa.get(k);
    if (!bvCu) {
      them.push(bvMoi);
    } else if (bvCu.sha256 !== bvMoi.sha256 || bvCu.file_id !== bvMoi.file_id) {
      doi.push({ cu: bvCu, moi: bvMoi });
    }
  }

  const bo = cu.ban_ve.filter((bv) => !moiTheoKhoa.has(khoa(bv)));
  const coBoMon = new Set(moi.ban_ve.map((bv) => bv.bo_mon));
  const thieuBoMon = boMonBatBuoc.filter((ma) => !coBoMon.has(ma));

  return { them, bo, doi, thieuBoMon };
}

/** Mô tả ngắn để hiển thị "v1 → v2: thay đổi gì". */
export function moTaSoSanh(kq: SoSanhPhienBan): string {
  const phan: string[] = [];
  if (kq.them.length) phan.push(`thêm ${kq.them.length} bản vẽ`);
  if (kq.bo.length) phan.push(`bỏ ${kq.bo.length} bản vẽ`);
  if (kq.doi.length) phan.push(`đổi ${kq.doi.length} bản vẽ`);
  if (kq.thieuBoMon.length) phan.push(`thiếu ${kq.thieuBoMon.join(", ")}`);
  return phan.length ? phan.join("; ") : "không đổi metadata/hash";
}

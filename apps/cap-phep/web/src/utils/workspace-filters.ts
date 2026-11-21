// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Bộ lọc Bàn làm việc được lưu trong trình duyệt; không chứa PII. */

export type LocHan = "tat-ca" | "qua-han" | "sap-han";
export type LocLoaiViec = "tat-ca" | "tiep-nhan" | "tham-dinh" | "phe-duyet" | "nghiem-thu" | "khac";

export interface BoLocDaLuu {
  ten: string;
  boLoc: LocHan;
  loaiViec: LocLoaiViec;
  at: number;
}

export const KHOA_BO_LOC = "dxos-workspace-filters-v1";
const TOI_DA = 10;
const TEN_DAI_TOI_DA = 50;

const LOC_HAN: readonly LocHan[] = ["tat-ca", "qua-han", "sap-han"];
const LOC_LOAI: readonly LocLoaiViec[] = ["tat-ca", "tiep-nhan", "tham-dinh", "phe-duyet", "nghiem-thu", "khac"];

function hopLe(x: any): x is BoLocDaLuu {
  return (
    x &&
    typeof x.ten === "string" &&
    x.ten.trim().length > 0 &&
    x.ten.length <= TEN_DAI_TOI_DA &&
    LOC_HAN.includes(x.boLoc) &&
    LOC_LOAI.includes(x.loaiViec) &&
    typeof x.at === "number"
  );
}

/** Đọc và làm sạch danh sách bộ lọc; dữ liệu hỏng thì bỏ qua. */
export function docBoLoc(storage: Storage | null | undefined, key = KHOA_BO_LOC): BoLocDaLuu[] {
  if (!storage) return [];
  try {
    const raw = storage.getItem(key);
    if (!raw) return [];
    const ds = JSON.parse(raw);
    if (!Array.isArray(ds)) return [];
    return ds
      .filter(hopLe)
      .sort((a, b) => b.at - a.at)
      .slice(0, TOI_DA)
      .map((x) => ({ ...x, ten: x.ten.trim() }));
  } catch {
    return [];
  }
}

/** Lưu bộ lọc mới, thay bộ lọc cùng tên; giữ tối đa 10 bộ lọc. */
export function luuBoLoc(
  storage: Storage | null | undefined,
  ds: BoLocDaLuu[],
  ten: string,
  boLoc: LocHan,
  loaiViec: LocLoaiViec,
  now = Date.now(),
): BoLocDaLuu[] {
  const tenSach = ten.trim().slice(0, TEN_DAI_TOI_DA);
  if (!tenSach) return ds;
  const tenChuan = tenSach.toLocaleLowerCase("vi");
  const next = [
    { ten: tenSach, boLoc, loaiViec, at: now },
    ...ds.filter((x) => x.ten.toLocaleLowerCase("vi") !== tenChuan),
  ].slice(0, TOI_DA);
  ghi(storage, next);
  return next;
}

export function xoaBoLoc(storage: Storage | null | undefined, ds: BoLocDaLuu[], ten: string): BoLocDaLuu[] {
  const tenChuan = ten.toLocaleLowerCase("vi");
  const next = ds.filter((x) => x.ten.toLocaleLowerCase("vi") !== tenChuan);
  ghi(storage, next);
  return next;
}

function ghi(storage: Storage | null | undefined, ds: BoLocDaLuu[]): void {
  if (!storage) return;
  try {
    storage.setItem(KHOA_BO_LOC, JSON.stringify(ds));
  } catch {
    /* trình duyệt chặn storage: bỏ qua */
  }
}

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Vai Keycloak của app cấp phép (khai báo trong apps/cap-phep/app.yaml). */
export const VAI = {
  CHU_DAU_TU: "app:cap-phep:chu-dau-tu",
  MOT_CUA: "app:cap-phep:mot-cua",
  THAM_DINH: "app:cap-phep:tham-dinh",
  LANH_DAO: "app:cap-phep:lanh-dao",
  TRAT_TU_XD: "app:cap-phep:trat-tu-xd",
  AUDITOR: "dx:auditor",
} as const;

export const VAI_CAN_BO: readonly string[] = [VAI.MOT_CUA, VAI.THAM_DINH, VAI.LANH_DAO, VAI.TRAT_TU_XD];

export const coVai = (vaiTro: string[], ...can: string[]) => can.some((v) => vaiTro.includes(v));
export const laCanBo = (vaiTro: string[]) => vaiTro.some((v) => VAI_CAN_BO.includes(v));
export const laChuDauTu = (vaiTro: string[]) => vaiTro.includes(VAI.CHU_DAU_TU);

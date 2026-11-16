// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Kiem tra nguoi dung co vai tro cu the hay khong
 */
export function hasRole(roles, targetRole) {
  if (!roles || !Array.isArray(roles)) return false;
  return roles.includes(targetRole);
}

/**
 * Kiem tra quyen tham dinh ho so
 * Thoa man khi:
 * 1. Nguoi dung co role 'tham-dinh'
 * 2. VA la nguoi duoc phan cong (hoSo.nguoi_tham_dinh === user.sub)
 * 3. HOAC co quyen truy cap khan cap (Break-glass) con hieu luc
 */
export function canReviewCase(user, hoSo, activeBreakGlassList = []) {
  if (!user || !hoSo) return false;
  if (!hasRole(user.roles, "tham-dinh")) return false;

  // Truong hop duoc phan cong truc tiep
  if (hoSo.nguoi_tham_dinh && hoSo.nguoi_tham_dinh === user.sub) {
    return true;
  }

  // Truong hop co quyen Break-glass da duyet va con han
  const bg = activeBreakGlassList.find(
    (item) => item.actor_id === user.sub && item.resource_id === hoSo.id && item.status === "DA_DUYET"
  );
  if (bg) {
    if (!bg.expires_at) return true;
    return new Date(bg.expires_at).getTime() > Date.now();
  }

  return false;
}

/**
 * Kiem tra quyen phe duyet va ky so giay phep
 * RANG BUOC CUNG: Tach biet vai tro (SoD - Segregation of Duties)
 * Nguoi phe duyet PHAI KHAC nguoi tham dinh (user.sub !== hoSo.nguoi_tham_dinh)
 */
export function canApproveCase(user, hoSo) {
  if (!user || !hoSo) return false;
  if (!hasRole(user.roles, "lanh-dao")) return false;

  // SoD: Nguoi tham dinh KHONG duoc tu phe duyet ho so cua minh
  if (hoSo.nguoi_tham_dinh && hoSo.nguoi_tham_dinh === user.sub) {
    return false;
  }

  // Trang thai ho so phai o buoc CHO_PHE_DUYET
  return hoSo.trang_thai === "CHO_PHE_DUYET";
}

/**
 * Kiem tra quyen xem thong tin ho so
 */
export function canViewCase(user, hoSo, activeBreakGlassList = []) {
  if (!user || !hoSo) return false;

  // Chu dau tu xem ho so cua chinh minh
  if (hasRole(user.roles, "chu-dau-tu") && hoSo.chu_dau_tu_id === user.sub) {
    return true;
  }

  // Can bo mot cua tiep nhan
  if (hasRole(user.roles, "mot-cua")) {
    return true;
  }

  // Lanh dao quan ly
  if (hasRole(user.roles, "lanh-dao")) {
    return true;
  }

  // Tham dinh vien
  return canReviewCase(user, hoSo, activeBreakGlassList);
}

/**
 * Kiem tra quyen xu ly trat tu xay dung
 */
export function canInspect(user) {
  if (!user) return false;
  return hasRole(user.roles, "trat-tu-xay-dung") || hasRole(user.roles, "lanh-dao");
}

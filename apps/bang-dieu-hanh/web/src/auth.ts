// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { UserManager, WebStorageStateStore, User } from "oidc-client-ts";

const origin = window.location.origin;
const REALM = import.meta.env.VITE_OIDC_REALM || "dxos";
const CLIENT_ID = import.meta.env.VITE_OIDC_CLIENT_ID || "dxos-web";

/** Đăng nhập Keycloak bằng Authorization Code + PKCE (mặc định của oidc-client-ts). */
export const userManager = new UserManager({
  authority: `${origin}/auth/realms/${REALM}`,
  client_id: CLIENT_ID,
  redirect_uri: `${origin}/`,
  post_logout_redirect_uri: `${origin}/`,
  response_type: "code",
  scope: "openid",
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  automaticSilentRenew: false,
});

export async function getUser(): Promise<User | null> {
  return await userManager.getUser();
}

export async function login(): Promise<void> {
  await userManager.signinRedirect();
}

export async function logout(): Promise<void> {
  await userManager.signoutRedirect();
}

export async function clearSession(): Promise<void> {
  await userManager.removeUser();
}

/** Trả access token còn hạn; sắp hết thì làm mới bằng refresh token. Không được thì trả null. */
export async function getValidToken(minSeconds = 30): Promise<string | null> {
  const user = await userManager.getUser();
  if (!user) return null;
  if (!user.expired && (user.expires_in ?? 0) > minSeconds) return user.access_token;
  try {
    const renewed = await userManager.signinSilent();
    return renewed?.access_token ?? null;
  } catch {
    return null;
  }
}

export async function handleCallbackIfNeeded(): Promise<User | null> {
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.has("code") && urlParams.has("state")) {
    try {
      const user = await userManager.signinCallback();
      window.history.replaceState({}, document.title, window.location.pathname);
      return user || null;
    } catch (err) {
      console.error("Lỗi xác thực OIDC Callback:", err);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }
  return await getUser();
}

/** Đọc vai từ access token (realm_access.roles). */
export function readRoles(accessToken: string | null | undefined): string[] {
  if (!accessToken) return [];
  try {
    const part = accessToken.split(".")[1] || "";
    const json = JSON.parse(decodeURIComponent(escape(atob(part.replace(/-/g, "+").replace(/_/g, "/")))));
    const roles = json?.realm_access?.roles ?? json?.roles ?? [];
    return Array.isArray(roles) ? roles.map(String) : [];
  } catch {
    return [];
  }
}

/** Chỉ lãnh đạo hoặc quản trị nền tảng mới được xem bảng điều hành. */
export function canViewDashboard(roles: string[]): boolean {
  return roles.includes("app:cap-phep:lanh-dao") || roles.includes("dx:platform-admin");
}
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { UserManager, WebStorageStateStore, User } from "oidc-client-ts";

const origin = window.location.origin;
const appUrl = `${origin}/dieu-hanh/`;

// Dùng chung client và kho phiên với app Cấp phép: đã đăng nhập ở một nơi thì nơi kia dùng được.
export const userManager = new UserManager({
  authority: `${origin}/auth/realms/dxos`,
  client_id: "dxos-web",
  redirect_uri: appUrl,
  post_logout_redirect_uri: appUrl,
  response_type: "code",
  scope: "openid",
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  automaticSilentRenew: false,
});

export async function login(): Promise<void> {
  await userManager.signinRedirect();
}

export async function logout(): Promise<void> {
  await userManager.signoutRedirect();
}

export async function currentUser(): Promise<User | null> {
  const params = new URLSearchParams(window.location.search);
  if (params.has("code") && params.has("state")) {
    try {
      const user = await userManager.signinCallback();
      window.history.replaceState({}, document.title, window.location.pathname);
      return user || null;
    } catch (err) {
      console.warn("Đăng nhập không hoàn tất:", err);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }
  const user = await userManager.getUser();
  return user && !user.expired ? user : null;
}

export async function clearSession(): Promise<void> {
  await userManager.removeUser();
}

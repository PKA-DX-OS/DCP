// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { UserManager, WebStorageStateStore, User } from "oidc-client-ts";

const origin = window.location.origin;

export const userManager = new UserManager({
  authority: `${origin}/auth/realms/dxos`,
  client_id: "dxos-web",
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

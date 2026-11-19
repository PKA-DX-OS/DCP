// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { inject, provide, type InjectionKey } from "vue";
import type { FeatureContext } from "./types";

const KEY: InjectionKey<FeatureContext> = Symbol("dxos-feature-context");

export function provideFeatureContext(ctx: FeatureContext): void {
  provide(KEY, ctx);
}

/** Dùng trong component của feature; lỗi rõ ràng nếu bị render ngoài App. */
export function useFeatureContext(): FeatureContext {
  const ctx = inject(KEY, null);
  if (!ctx) throw new Error("Feature phải được render bên trong App (thiếu FeatureContext)");
  return ctx;
}

/** Như trên nhưng trả null khi không có App (ví dụ trang demo). */
export function useOptionalFeatureContext(): FeatureContext | null {
  return inject(KEY, null);
}

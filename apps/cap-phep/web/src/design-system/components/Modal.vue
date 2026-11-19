<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { ref, useId } from "vue";
import { useDialog } from "../useDialog";

const props = withDefaults(defineProps<{ title: string; size?: "sm" | "md" | "lg"; closeOnOverlay?: boolean }>(), {
  size: "md",
  closeOnOverlay: true,
});
const open = defineModel<boolean>("open", { default: false });
const panel = ref<HTMLElement | null>(null);
const uid = useId();
const width = { sm: "max-w-md", md: "max-w-2xl", lg: "max-w-4xl" };
useDialog(open, panel, () => (open.value = false));
function overlay() {
  if (props.closeOnOverlay) open.value = false;
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      :style="{ background: 'var(--phu-hop)' }"
      @click.self="overlay"
    >
      <div
        ref="panel"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="uid + '-tieu-de'"
        tabindex="-1"
        class="flex max-h-[90vh] w-full flex-col ds-hop rounded-ds-md outline-none"
        :class="width[size]"
      >
        <header class="flex items-start justify-between gap-4 px-6 pb-2 pt-5">
          <h3 :id="uid + '-tieu-de'" class="m-0 text-ds-lg font-semibold text-ds-text">{{ title }}</h3>
          <button
            type="button"
            class="ds-focus -mr-2 flex h-11 w-11 items-center justify-center rounded-ds-sm text-ds-muted hover:bg-ds-surface-2"
            aria-label="Đóng"
            @click="open = false"
          >
            ✕
          </button>
        </header>
        <div class="overflow-y-auto px-6 pb-5"><slot /></div>
        <footer v-if="$slots.footer" class="flex items-center justify-end gap-2 border-t border-ds-border px-6 py-4">
          <slot name="footer" />
        </footer>
      </div>
    </div>
  </Teleport>
</template>

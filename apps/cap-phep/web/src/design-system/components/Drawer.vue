<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { ref, useId } from "vue";
import { useDialog } from "../useDialog";

withDefaults(defineProps<{ title: string; width?: string }>(), { width: "min(640px, 100vw)" });
const open = defineModel<boolean>("open", { default: false });
const panel = ref<HTMLElement | null>(null);
const uid = useId();
useDialog(open, panel, () => (open.value = false));
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="fixed inset-0 z-50 flex justify-end" :style="{ background: 'var(--phu-hop)' }" @click.self="open = false">
      <aside
        ref="panel"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="uid + '-tieu-de'"
        tabindex="-1"
        class="flex h-full flex-col ds-hop outline-none"
        :style="{ width }"
      >
        <header class="flex items-center justify-between gap-4 border-b border-ds-border px-5 py-3">
          <h3 :id="uid + '-tieu-de'" class="m-0 text-ds-md font-semibold text-ds-text">{{ title }}</h3>
          <button
            type="button"
            class="ds-focus flex h-11 w-11 items-center justify-center rounded-ds-sm text-ds-muted hover:bg-ds-surface-2"
            aria-label="Đóng"
            @click="open = false"
          >
            ✕
          </button>
        </header>
        <div class="flex-1 overflow-y-auto p-5"><slot /></div>
        <footer v-if="$slots.footer" class="flex items-center justify-end gap-2 border-t border-ds-border px-5 py-3">
          <slot name="footer" />
        </footer>
      </aside>
    </div>
  </Teleport>
</template>

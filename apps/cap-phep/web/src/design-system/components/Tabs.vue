<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { nextTick, ref, useId } from "vue";

export interface TabItem {
  key: string;
  label: string;
  count?: number;
  disabled?: boolean;
}

const props = defineProps<{ tabs: TabItem[]; label?: string }>();
const model = defineModel<string>({ required: true });
const uid = useId();
const btns = ref<HTMLButtonElement[]>([]);

/** Mũi tên trái/phải, Home/End chuyển tab theo mẫu WAI-ARIA Tabs */
async function onKey(e: KeyboardEvent, i: number) {
  const usable = props.tabs.map((t, idx) => (t.disabled ? -1 : idx)).filter((x) => x >= 0);
  const pos = usable.indexOf(i);
  let next = -1;
  if (e.key === "ArrowRight") next = usable[(pos + 1) % usable.length];
  else if (e.key === "ArrowLeft") next = usable[(pos - 1 + usable.length) % usable.length];
  else if (e.key === "Home") next = usable[0];
  else if (e.key === "End") next = usable[usable.length - 1];
  if (next < 0) return;
  e.preventDefault();
  model.value = props.tabs[next].key;
  await nextTick();
  btns.value[next]?.focus();
}
</script>

<template>
  <div>
    <div role="tablist" :aria-label="label" class="flex gap-1 overflow-x-auto border-b border-ds-border">
      <button
        v-for="(t, i) in tabs"
        :id="uid + '-tab-' + t.key"
        :key="t.key"
        ref="btns"
        type="button"
        role="tab"
        :aria-selected="model === t.key"
        :aria-controls="uid + '-panel-' + t.key"
        :tabindex="model === t.key ? 0 : -1"
        :disabled="t.disabled"
        class="ds-focus -mb-px flex min-h-11 items-center gap-2 whitespace-nowrap border-b-2 px-3 text-ds-base disabled:opacity-50"
        :class="model === t.key ? 'border-ds-brand font-semibold text-ds-text' : 'border-transparent text-ds-muted hover:text-ds-text'"
        @click="model = t.key"
        @keydown="onKey($event, i)"
      >
        {{ t.label }}
        <span v-if="t.count !== undefined" class="rounded-full bg-ds-surface-2 px-2 text-ds-xs">{{ t.count }}</span>
      </button>
    </div>
    <div
      v-for="t in tabs"
      v-show="model === t.key"
      :id="uid + '-panel-' + t.key"
      :key="t.key"
      role="tabpanel"
      :aria-labelledby="uid + '-tab-' + t.key"
      class="pt-4"
    >
      <slot :name="t.key" />
    </div>
  </div>
</template>

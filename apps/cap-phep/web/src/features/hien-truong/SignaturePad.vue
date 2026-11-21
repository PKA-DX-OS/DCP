<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { onMounted, ref, watch } from "vue";

const props = withDefaults(defineProps<{ modelValue?: string | null; nhan?: string }>(), {
  modelValue: null,
  nhan: "Ký tay của cán bộ kiểm tra",
});
const emit = defineEmits<{ (e: "update:modelValue", value: string | null): void }>();

const canvas = ref<HTMLCanvasElement | null>(null);
let ctx: CanvasRenderingContext2D | null = null;
let dangVe = false;
let lastEmit = "";

function veNen(): void {
  if (!ctx || !canvas.value) return;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.value.width, canvas.value.height);
  ctx.strokeStyle = "#0b1322";
  ctx.lineWidth = 2.5;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
}

function toaDo(e: PointerEvent): { x: number; y: number } | null {
  const c = canvas.value;
  if (!c) return null;
  const r = c.getBoundingClientRect();
  if (!r.width || !r.height) return { x: 0, y: 0 };
  return {
    x: ((e.clientX - r.left) / r.width) * c.width,
    y: ((e.clientY - r.top) / r.height) * c.height,
  };
}

function batDau(e: PointerEvent): void {
  if (!ctx) return;
  e.preventDefault();
  dangVe = true;
  canvas.value?.setPointerCapture?.(e.pointerId);
  const p = toaDo(e);
  if (!p) return;
  ctx.beginPath();
  ctx.moveTo(p.x, p.y);
  ctx.lineTo(p.x + 0.1, p.y + 0.1);
  ctx.stroke();
}

function diChuyen(e: PointerEvent): void {
  if (!dangVe || !ctx) return;
  e.preventDefault();
  const p = toaDo(e);
  if (!p) return;
  ctx.lineTo(p.x, p.y);
  ctx.stroke();
}

function ketThuc(e?: PointerEvent): void {
  if (!dangVe) return;
  dangVe = false;
  if (e) canvas.value?.releasePointerCapture?.(e.pointerId);
  const data = canvas.value?.toDataURL?.("image/png") || "";
  lastEmit = data;
  emit("update:modelValue", data || null);
}

function xoa(): void {
  lastEmit = "";
  veNen();
  emit("update:modelValue", null);
}

function veAnh(data: string): void {
  if (!ctx || !canvas.value || typeof Image === "undefined") return;
  const img = new Image();
  img.onload = () => {
    veNen();
    ctx?.drawImage(img, 0, 0, canvas.value!.width, canvas.value!.height);
  };
  img.src = data;
}

onMounted(() => {
  if (!canvas.value) return;
  ctx = canvas.value.getContext?.("2d") || null;
  veNen();
  if (props.modelValue) veAnh(props.modelValue);
});

watch(
  () => props.modelValue,
  (value) => {
    if (value === lastEmit) return;
    if (!value) {
      veNen();
      return;
    }
    veAnh(value);
  },
);
</script>

<template>
  <div>
    <p class="nhan">{{ nhan }}</p>
    <div class="rounded-[16px] border border-vien-nhat bg-white p-2">
      <canvas
        ref="canvas"
        width="600"
        height="200"
        class="block w-full cursor-crosshair touch-none rounded-[10px]"
        role="img"
        aria-label="Khung ký tay"
        @pointerdown="batDau"
        @pointermove="diChuyen"
        @pointerup="ketThuc"
        @pointercancel="ketThuc"
        @pointerleave="ketThuc"
      >Trình duyệt không hỗ trợ vẽ chữ ký.</canvas>
    </div>
    <div class="mt-1 flex flex-wrap items-center justify-between gap-2">
      <span class="goi-y">Ký trong khung trắng; chữ ký chỉ lưu trên thiết bị.</span>
      <button type="button" class="btn btn-sm" @click="xoa">Xóa chữ ký</button>
    </div>
  </div>
</template>

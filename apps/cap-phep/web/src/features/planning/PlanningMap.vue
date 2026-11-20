<!-- SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

<script setup lang="ts">
import { computed, ref } from "vue";

const props = defineProps<{
  zones: any[];
  parcels: any[];
  selectedId?: string | null;
}>();
const emit = defineEmits<{ (e: "select", parcel: any): void }>();

const W = 640;
const H = 360;
const PAD = 24;
const hover = ref<string>("");

type Point = [number, number];

function flatten(node: any, out: Point[] = []): Point[] {
  if (Array.isArray(node)) {
    if (node.length >= 2 && typeof node[0] === "number" && typeof node[1] === "number") {
      out.push([Number(node[0]), Number(node[1])]);
    } else {
      node.forEach((n) => flatten(n, out));
    }
  }
  return out;
}

function geometry(obj: any): any {
  if (!obj) return null;
  if (obj.type === "Feature") return obj.geometry;
  return obj;
}

function allPoints(): Point[] {
  const pts: Point[] = [];
  for (const z of props.zones || []) flatten(geometry(z.geom)?.coordinates, pts);
  for (const p of props.parcels || []) flatten(geometry(p.geom)?.coordinates, pts);
  return pts;
}

const bounds = computed(() => {
  const pts = allPoints();
  if (!pts.length) return { minx: 0, miny: 0, maxx: 1, maxy: 1 };
  return {
    minx: Math.min(...pts.map((p) => p[0])),
    maxx: Math.max(...pts.map((p) => p[0])),
    miny: Math.min(...pts.map((p) => p[1])),
    maxy: Math.max(...pts.map((p) => p[1])),
  };
});

function project(p: Point): Point {
  const b = bounds.value;
  const dx = Math.max(b.maxx - b.minx, 1e-9);
  const dy = Math.max(b.maxy - b.miny, 1e-9);
  const scale = Math.min((W - PAD * 2) / dx, (H - PAD * 2) / dy);
  const x = PAD + (p[0] - b.minx) * scale;
  const y = H - PAD - (p[1] - b.miny) * scale;
  return [x, y];
}

function ringPath(ring: Point[]): string {
  if (!ring.length) return "";
  return ring.map((p, i) => `${i === 0 ? "M" : "L"}${project(p)[0].toFixed(1)},${project(p)[1].toFixed(1)}`).join(" ") + " Z";
}

function geometryPaths(obj: any): string[] {
  const g = geometry(obj);
  if (!g || !g.coordinates) return [];
  if (g.type === "Polygon") return [ringPath(g.coordinates[0] || [])];
  if (g.type === "MultiPolygon") return (g.coordinates || []).map((poly: any) => ringPath(poly[0] || []));
  return [];
}

function parcelPoint(obj: any): Point | null {
  const g = geometry(obj);
  if (!g) return null;
  if (g.type === "Point" && g.coordinates) return [Number(g.coordinates[0]), Number(g.coordinates[1])];
  const pts: Point[] = [];
  flatten(g.coordinates, pts);
  if (!pts.length) return null;
  return [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length];
}

function zonePos(z: any): { x: number; y: number } {
  const pts: Point[] = [];
  flatten(geometry(z.geom)?.coordinates, pts);
  if (!pts.length) return { x: 0, y: 0 };
  const c: Point = [pts.reduce((s, p) => s + p[0], 0) / pts.length, pts.reduce((s, p) => s + p[1], 0) / pts.length];
  const [x, y] = project(c);
  return { x, y };
}

function parcelPos(p: any): { x: number; y: number } | null {
  const c = parcelPoint(p.geom);
  if (!c) return null;
  const [x, y] = project(c);
  return { x, y };
}

function zoneTone(loai: string): { fill: string; stroke: string; ten: string } {
  if (loai === "hanh_lang_giao_thong") return { fill: "#FEF3C7", stroke: "#D97706", ten: "Hành lang giao thông" };
  if (loai === "cam_xay_dung") return { fill: "#FEE2E2", stroke: "#DC2626", ten: "Vùng cấm xây dựng" };
  if (loai === "cong_vien") return { fill: "#DCFCE7", stroke: "#16A34A", ten: "Công viên" };
  return { fill: "#DBEAFE", stroke: "#2563EB", ten: "Ô đô thị / dân cư" };
}
</script>

<template>
  <div class="rounded-[10px] border border-vien bg-mat p-3">
    <div class="flex items-center justify-between gap-3 mb-2">
      <h4 class="text-[13px] font-semibold m-0">Bản đồ quy hoạch (dữ liệu tổng hợp)</h4>
      <span class="goi-y">Nền tảng không dùng GIS toàn thành phố</span>
    </div>
    <p v-if="!zones.length && !parcels.length" class="text-phu text-[13px] m-0">Chưa có dữ liệu bản đồ.</p>
    <svg v-else :viewBox="`0 0 ${W} ${H}`" class="w-full h-auto rounded-md bg-white" role="img" aria-label="Bản đồ thửa đất và vùng quy hoạch">
      <g v-for="z in zones" :key="z.id">
        <path
          v-for="(d, i) in geometryPaths(z.geom)"
          :key="`${z.id}-${i}`"
          :d="d"
          :fill="zoneTone(z.loai_zone).fill"
          :stroke="zoneTone(z.loai_zone).stroke"
          stroke-width="1.5"
          fill-opacity="0.55"
        />
        <text
          v-if="geometryPaths(z.geom)[0]"
          :x="zonePos(z).x"
          :y="zonePos(z).y"
          text-anchor="middle"
          class="fill-slate-500"
          font-size="11"
        >{{ z.ma_zone }}</text>
      </g>
      <g v-for="p in parcels" :key="p.id">
        <circle
          v-if="parcelPos(p)"
          :cx="parcelPos(p)!.x"
          :cy="parcelPos(p)!.y"
          :r="selectedId === p.id ? 9 : 6"
          :fill="selectedId === p.id ? '#0E7C7B' : '#0F2A43'"
          stroke="#fff"
          stroke-width="2"
          class="cursor-pointer"
          tabindex="0"
          role="button"
          :aria-label="`Chọn thửa ${p.ma_thua_dat}`"
          @click="emit('select', p)"
          @keydown.enter="emit('select', p)"
          @mouseenter="hover = p.id"
          @mouseleave="hover = ''"
        />
        <text
          v-if="parcelPos(p)"
          :x="parcelPos(p)!.x + 10"
          :y="parcelPos(p)!.y + 4"
          font-size="11"
          class="fill-slate-700"
        >{{ p.ma_thua_dat }}</text>
      </g>
    </svg>
    <div class="flex flex-wrap gap-3 mt-2 goi-y">
      <span v-for="loai in ['o_do_thi', 'hanh_lang_giao_thong', 'cam_xay_dung']" :key="loai" class="inline-flex items-center gap-1">
        <span class="inline-block w-3 h-3 rounded-sm" :style="{ background: zoneTone(loai).fill, border: '1px solid ' + zoneTone(loai).stroke }"></span>
        {{ zoneTone(loai).ten }}
      </span>
      <span class="inline-flex items-center gap-1"><span class="inline-block w-3 h-3 rounded-full bg-[#0F2A43]"></span>Thửa đất</span>
    </div>
  </div>
</template>

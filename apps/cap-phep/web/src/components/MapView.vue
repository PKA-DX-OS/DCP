<!--
SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
SPDX-License-Identifier: AGPL-3.0-or-later
-->
<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const props = withDefaults(
  defineProps<{
    zones?: any[];
    parcels?: any[];
    works?: any[];
    selectedId?: string | null;
    title?: string;
  }>(),
  { zones: () => [], parcels: () => [], works: () => [], title: "Bản đồ dùng chung" },
);
const emit = defineEmits<{ (e: "select", parcel: any): void }>();

const el = ref<HTMLElement | null>(null);
const hienVung = ref(true);
const hienThua = ref(true);
const hienCongTrinh = ref(true);
let map: L.Map | null = null;
let lopVung: L.LayerGroup | null = null;
let lopThua: L.LayerGroup | null = null;
let lopCongTrinh: L.LayerGroup | null = null;
let doiGiaoDien: MutationObserver | null = null;

function geometry(obj: any): any {
  if (!obj) return null;
  if (obj.type === "Feature") return obj.geometry;
  return obj;
}
function geojson(obj: any): any {
  if (!obj) return null;
  if (obj.type === "Feature" || obj.type === "FeatureCollection") return obj;
  return { type: "Feature", properties: {}, geometry: geometry(obj) };
}
function zoneTone(loai: string): { fill: string; stroke: string; ten: string } {
  if (loai === "hanh_lang_giao_thong") return { fill: "#FEF3C7", stroke: "#D97706", ten: "Hành lang giao thông" };
  if (loai === "cam_xay_dung") return { fill: "#FEE2E2", stroke: "#DC2626", ten: "Vùng cấm xây dựng" };
  if (loai === "cong_vien") return { fill: "#DCFCE7", stroke: "#16A34A", ten: "Công viên" };
  return { fill: "#DBEAFE", stroke: "#2563EB", ten: "Ô đô thị / dân cư" };
}

function clearLayers() {
  lopVung?.clearLayers();
  lopThua?.clearLayers();
  lopCongTrinh?.clearLayers();
}

/** Màu theo giao diện sáng/tối, khai báo trong style.css. */
function mau(bien: string, duPhong: string): string {
  if (typeof window === "undefined") return duPhong;
  return getComputedStyle(document.documentElement).getPropertyValue(bien).trim() || duPhong;
}

function rebuild() {
  if (!map || !lopVung || !lopThua || !lopCongTrinh) return;
  clearLayers();

  if (hienVung.value) {
    for (const z of props.zones || []) {
      const gj = geojson(z.geom || z);
      if (!gj?.geometry) continue;
      const tone = zoneTone(z.loai_zone);
      L.geoJSON(gj, {
        style: { color: tone.stroke, weight: 1.5, fillColor: tone.fill, fillOpacity: 0.55 },
      })
        .bindPopup(`<b>${z.ma_zone || "Vùng quy hoạch"}</b><br>${tone.ten}`)
        .addTo(lopVung);
    }
  }

  if (hienThua.value) {
    for (const p of props.parcels || []) {
      const gj = geojson(p.geom || p);
      if (!gj?.geometry) continue;
      const chon = props.selectedId === p.id;
      const mauThua = mau("--ban-do-thua", "#0F2A43");
      L.geoJSON(gj, {
        pointToLayer: (_f, latlng) =>
          L.circleMarker(latlng, {
            radius: chon ? 9 : 6,
            color: "#fff",
            weight: 2,
            fillColor: chon ? "#0E7C7B" : mauThua,
            fillOpacity: 1,
          }),
        style: { color: mauThua, weight: 1.5, fillColor: mauThua, fillOpacity: 0.12 },
      })
        .bindPopup(`<b>Thửa ${p.ma_thua_dat || p.so_thua || ""}</b><br>${p.loai_dat || ""}`)
        .on("click", () => emit("select", p))
        .addTo(lopThua);
    }
  }

  if (hienCongTrinh.value) {
    for (const w of props.works || []) {
      const gj = geojson(w.geom || w.vi_tri || w.geometry);
      if (!gj?.geometry) continue;
      L.geoJSON(gj, {
        pointToLayer: (_f, latlng) => L.circleMarker(latlng, { radius: 7, color: "#fff", weight: 2, fillColor: "#D97706", fillOpacity: 1 }),
        style: { color: "#D97706", weight: 2, fillColor: "#D97706", fillOpacity: 0.3 },
      })
        .bindPopup(`<b>${w.ten || w.ma_cong_trinh || "Công trình"}</b><br>${w.dia_chi || ""}`)
        .addTo(lopCongTrinh);
    }
  }

  const bounds = L.latLngBounds([]);
  for (const lop of [lopVung, lopThua, lopCongTrinh]) {
    lop.eachLayer((layer: any) => {
      if (typeof layer.getBounds === "function") bounds.extend(layer.getBounds());
      else if (typeof layer.getLatLng === "function") bounds.extend(layer.getLatLng());
    });
  }
  if (bounds.isValid()) map.fitBounds(bounds.pad(0.15), { maxZoom: 17 });
}

onMounted(async () => {
  await nextTick();
  if (!el.value) return;
  map = L.map(el.value, {
    zoomControl: true,
    attributionControl: false,
    preferCanvas: true,
  }).setView([10.7769, 106.7009], 13);
  lopVung = L.layerGroup().addTo(map);
  lopThua = L.layerGroup().addTo(map);
  lopCongTrinh = L.layerGroup().addTo(map);
  rebuild();
  // Đổi giao diện sáng/tối thì vẽ lại để màu thửa đất đủ tương phản với nền
  doiGiaoDien = new MutationObserver(() => rebuild());
  doiGiaoDien.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
});

watch([() => props.zones, () => props.parcels, () => props.works, hienVung, hienThua, hienCongTrinh], rebuild, { deep: true });
onBeforeUnmount(() => {
  doiGiaoDien?.disconnect();
  map?.remove();
  map = null;
});
</script>

<template>
  <div class="rounded-[10px] border border-vien bg-mat p-3">
    <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
      <h4 class="text-[13px] font-semibold m-0">{{ title }}</h4>
      <span class="goi-y">Nền trơn offline, dữ liệu GeoJSON tổng hợp</span>
    </div>
    <div class="flex flex-wrap gap-3 mb-2 text-[12px] text-phu" aria-label="Lớp bản đồ">
      <label class="inline-flex min-h-[32px] items-center gap-1"><input v-model="hienVung" type="checkbox" /> Vùng quy hoạch</label>
      <label class="inline-flex min-h-[32px] items-center gap-1"><input v-model="hienThua" type="checkbox" /> Thửa đất</label>
      <label v-if="works.length" class="inline-flex min-h-[32px] items-center gap-1"><input v-model="hienCongTrinh" type="checkbox" /> Công trình</label>
    </div>
    <div ref="el" class="h-[360px] w-full rounded-md border border-vien" role="application" aria-label="Bản đồ thửa đất, vùng quy hoạch và công trình"></div>
    <p v-if="!zones.length && !parcels.length && !works.length" class="mt-2 mb-0 text-phu text-[13px]">Chưa có dữ liệu bản đồ.</p>
    <div class="flex flex-wrap gap-3 mt-2 goi-y">
      <span v-for="loai in ['o_do_thi', 'hanh_lang_giao_thong', 'cam_xay_dung']" :key="loai" class="inline-flex items-center gap-1">
        <span class="inline-block w-3 h-3 rounded-sm" :style="{ background: zoneTone(loai).fill, border: '1px solid ' + zoneTone(loai).stroke }"></span>
        {{ zoneTone(loai).ten }}
      </span>
      <span class="inline-flex items-center gap-1"><span class="inline-block w-3 h-3 rounded-full" style="background: var(--ban-do-thua)"></span>Thửa đất</span>
      <span v-if="works.length" class="inline-flex items-center gap-1"><span class="inline-block w-3 h-3 rounded-sm bg-[#D97706]"></span>Công trình</span>
    </div>
  </div>
</template>

<style scoped>
:deep(.leaflet-container) {
  font-family: inherit;
  background: var(--ban-do-nen);
}
:deep(.leaflet-popup-content) {
  margin: 8px 10px;
  font-size: 12px;
}
</style>

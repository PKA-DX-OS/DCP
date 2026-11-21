// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/** Phiếu kiểm tra hiện trường lưu trên thiết bị (PWA). */

export type FieldStatus = "nhap" | "da_gui" | "loi";
export type FieldChecklistValue = "dat" | "khong_dat" | "khong_ap_dung" | "";

export interface FieldPhoto {
  id: string;
  name: string;
  type: string;
  size: number;
  blob: Blob;
  addedAt: number;
}

export interface FieldGps {
  lat: number;
  lng: number;
  accuracy: number | null;
}

export interface FieldDraft {
  id: string;
  congTrinhId: string;
  maCongTrinh: string;
  diaChi: string;
  checklist: Record<string, FieldChecklistValue>;
  gps: FieldGps | null;
  ghiChu: string;
  photos: FieldPhoto[];
  signature: string | null;
  createdAt: number;
  updatedAt: number;
  status: FieldStatus;
  serverId?: string | null;
  serverMaPhieu?: string | null;
  syncError?: string | null;
  conflict?: string | null;
}

export interface CongTrinhCache {
  id: string;
  ma_cong_trinh: string;
  dia_chi: string;
}

export const CHECKLIST_HIEN_TRUONG: { key: string; label: string }[] = [
  { key: "giay_phep", label: "Có giấy phép xây dựng tại công trình" },
  { key: "vi_tri", label: "Xây dựng đúng vị trí, ranh giới" },
  { key: "quy_mo", label: "Đúng quy mô, số tầng, chiều cao" },
  { key: "an_toan", label: "Có biện pháp an toàn thi công" },
  { key: "ve_sinh", label: "Vệ sinh, che chắn, không lấn chiếm" },
  { key: "nghiem_thu_mong", label: "Đã nghiệm thu móng (nếu có)" },
];

export const NHAN_CHECKLIST: Record<string, string> = {
  dat: "Đạt",
  khong_dat: "Không đạt",
  khong_ap_dung: "Không áp dụng",
  "": "Chưa đánh giá",
};

function taoId(): string {
  return globalThis.crypto?.randomUUID?.() || `nhap-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function taoNhapMoi(c: CongTrinhCache, now = Date.now()): FieldDraft {
  const checklist: Record<string, FieldChecklistValue> = {};
  for (const item of CHECKLIST_HIEN_TRUONG) checklist[item.key] = "";
  return {
    id: taoId(),
    congTrinhId: c.id,
    maCongTrinh: c.ma_cong_trinh,
    diaChi: c.dia_chi || "",
    checklist,
    gps: null,
    ghiChu: "",
    photos: [],
    signature: null,
    createdAt: now,
    updatedAt: now,
    status: "nhap",
    serverId: null,
    serverMaPhieu: null,
    syncError: null,
    conflict: null,
  };
}

/** Lỗi chặn gửi phiếu. */
export function loiNhap(d: FieldDraft | null | undefined): string[] {
  if (!d) return ["Chưa chọn phiếu."];
  const loi: string[] = [];
  if (!d.congTrinhId) loi.push("Chọn công trình trước khi lưu phiếu.");
  for (const item of CHECKLIST_HIEN_TRUONG) {
    if (!d.checklist?.[item.key]) loi.push(`Chưa đánh giá: ${item.label}.`);
  }
  if (!d.signature) loi.push("Cần ký tay trước khi gửi phiếu.");
  return loi;
}

/** Cảnh báo không chặn gửi. */
export function canhBaoNhap(d: FieldDraft | null | undefined): string[] {
  if (!d) return [];
  const canhBao: string[] = [];
  if (!d.gps) canhBao.push("Chưa có vị trí GPS.");
  if (!d.photos.length) canhBao.push("Chưa có ảnh hiện trường.");
  if (!d.ghiChu.trim()) canhBao.push("Chưa có ghi chú.");
  return canhBao;
}

export function tomTatGhiChu(d: FieldDraft): string {
  const lines = [
    "[PWA hiện trường]",
    `Mã nháp: ${d.id}`,
    `Công trình: ${d.maCongTrinh || "—"} — ${d.diaChi || "—"}`,
  ];
  if (d.gps) {
    const doChinhXac = d.gps.accuracy !== null ? ` (±${Math.round(d.gps.accuracy)} m)` : "";
    lines.push(`GPS: ${d.gps.lat.toFixed(6)}, ${d.gps.lng.toFixed(6)}${doChinhXac}`);
  } else {
    lines.push("GPS: không có");
  }
  lines.push("Checklist:");
  for (const item of CHECKLIST_HIEN_TRUONG) {
    lines.push(`- ${item.label}: ${NHAN_CHECKLIST[d.checklist?.[item.key] || ""] || "Chưa đánh giá"}`);
  }
  lines.push(`Ghi chú: ${d.ghiChu.trim() || "(không)"}`);
  lines.push(`Ảnh: ${d.photos.length} (lưu trên thiết bị, chưa tải lên)`);
  lines.push(`Chữ ký: ${d.signature ? "có (lưu trên thiết bị)" : "không"}`);
  return lines.join("\n").slice(0, 4000);
}

/** Tìm phiếu trên máy chủ được lập sau bản nháp này cho cùng công trình. */
export function timXungDot(d: FieldDraft, dsPhieu: any[]): any | null {
  const moc = Number(d.createdAt) || 0;
  for (const p of dsPhieu || []) {
    if (!p || String(p.cong_trinh_id || "") !== d.congTrinhId) continue;
    if (d.serverId && String(p.id || "") === d.serverId) continue;
    const taoLuc = new Date(p.created_at || 0).getTime();
    if (Number.isFinite(taoLuc) && taoLuc > moc) return p;
  }
  return null;
}

export function moTaXungDot(p: any): string {
  const ma = p?.ma_phieu || p?.id || "không rõ mã";
  const luc = p?.created_at ? new Date(p.created_at).toLocaleString("vi-VN") : "không rõ thời điểm";
  return `Có phiếu ${ma} được lập lúc ${luc}, sau bản nháp này.`;
}

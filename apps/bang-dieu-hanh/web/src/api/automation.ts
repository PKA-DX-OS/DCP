// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { apiGet } from "../api";

/** Chỉ số H theo hợp đồng contracts/dh/automation.yaml. */
export interface ChiSoHieuQua {
  computed_at: string;
  period: { from: string | null; to: string | null };
  baseline_label: string | null;
  so_ho_so: number;
  metrics: {
    key: string;
    label: string;
    unit: string;
    better: "lower" | "higher";
    baseline: number | null;
    current: number | null;
    delta_pct: number | null;
    source: string;
  }[];
  ghi_chu?: string[];
}

export interface KetQuaHieuQua {
  data: ChiSoHieuQua;
  source: "api" | "mock";
}

/** Gọi API thật; chưa có API thì trả mốc v1.1 có ghi chú, không bịa số hiện tại. */
export async function taiHieuQua(from?: string, to?: string): Promise<KetQuaHieuQua> {
  const qs = new URLSearchParams();
  if (from) qs.set("from", from);
  if (to) qs.set("to", to);
  const query = qs.toString();
  const duongDan = `/automation/metrics${query ? `?${query}` : ""}`;
  try {
    const data = await apiGet<ChiSoHieuQua>(duongDan);
    return { data, source: "api" };
  } catch {
    return { data: MOC_V11, source: "mock" };
  }
}

const MOC_V11: ChiSoHieuQua = {
  computed_at: "2026-11-21T00:00:00+07:00",
  period: { from: null, to: null },
  baseline_label: "v1.1",
  so_ho_so: 0,
  metrics: [
    {
      key: "thao_tac_thu_cong_tb",
      label: "Thao tác thủ công / hồ sơ",
      unit: "",
      better: "lower",
      baseline: 8.14,
      current: null,
      delta_pct: null,
      source: "core.audit_log",
    },
    {
      key: "chuyen_tay_tb",
      label: "Lần chuyển tay / hồ sơ",
      unit: "",
      better: "lower",
      baseline: 0.17,
      current: null,
      delta_pct: null,
      source: "app_cap_phep.ho_so_lich_su",
    },
    {
      key: "ty_le_ho_so_phai_bo_sung_pct",
      label: "Hồ sơ phải bổ sung",
      unit: "%",
      better: "lower",
      baseline: 11.2,
      current: null,
      delta_pct: null,
      source: "core.audit_log",
    },
    {
      key: "thoi_gian_xu_ly_tb_ngay_lam_viec",
      label: "Thời gian nộp đến ký",
      unit: "ngày làm việc",
      better: "lower",
      baseline: null,
      current: null,
      delta_pct: null,
      source: "app_cap_phep.giay_phep",
    },
    {
      key: "ty_le_ky_dung_han_pct",
      label: "Ký đúng hạn",
      unit: "%",
      better: "higher",
      baseline: null,
      current: null,
      delta_pct: null,
      source: "app_cap_phep.giay_phep",
    },
    {
      key: "ty_le_tu_phuc_vu_pct",
      label: "Thao tác do chủ đầu tư tự làm",
      unit: "%",
      better: "higher",
      baseline: 29.6,
      current: null,
      delta_pct: null,
      source: "core.audit_log",
    },
    {
      key: "trich_xuat_tu_dong",
      label: "Trích xuất tự động (OCR)",
      unit: "",
      better: "higher",
      baseline: 0,
      current: null,
      delta_pct: null,
      source: "app_cap_phep.ocr_extractions",
    },
  ],
  ghi_chu: [
    "Chưa có API /api/v1/automation/metrics. Đang hiển thị mốc đo v1.1; không phải số hiện tại.",
    "Không công bố mức tiết kiệm khi chưa đo lại trên dữ liệu thật.",
  ],
};

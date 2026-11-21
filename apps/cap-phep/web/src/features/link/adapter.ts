// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Adapter mock cho H-LINK. D chưa có API external_refs, nên module này chỉ sinh
 * dữ liệu mẫu từ hồ sơ hiện tại. Không trả về CCCD/điện thoại đầy đủ và không
 * ghi bất kỳ dữ liệu nào xuống storage.
 */
import type { HoSo } from "../../types";
import { cheCccd } from "../../utils/labels";
import type { KetQuaTraCuu, NguonLienNganh, TruongDuLieu } from "./types";

/** `ma_dinh_danh_dia_diem`/`ma_cong_trinh` có thể có khi hồ sơ được mở đầy đủ. */
type HoSoLienNganh = Partial<HoSo> & {
  ma_dinh_danh_dia_diem?: string | null;
  ma_cong_trinh?: string | null;
};

export interface NguonMeta {
  value: NguonLienNganh;
  label: string;
  he_thong: string;
  goi_y: string;
}

export const NGUON_OPTIONS: readonly NguonMeta[] = [
  {
    value: "dan_cu",
    label: "Dân cư",
    he_thong: "CSDL dân cư (mẫu)",
    goi_y: "Nhập số CCCD 12 chữ số",
  },
  {
    value: "dat_dai",
    label: "Đất đai",
    he_thong: "CSDL đất đai (mẫu)",
    goi_y: "Nhập số thửa/tờ hoặc mã định danh địa điểm",
  },
  {
    value: "thue",
    label: "Thuế",
    he_thong: "CSDL thuế (mẫu)",
    goi_y: "Nhập mã số thuế hoặc CCCD",
  },
  {
    value: "pccc",
    label: "PCCC",
    he_thong: "CSDL PCCC (mẫu)",
    goi_y: "Nhập mã công trình hoặc số giấy chứng nhận",
  },
];

export function nguonMeta(nguon: NguonLienNganh): NguonMeta {
  return NGUON_OPTIONS.find((x) => x.value === nguon) || NGUON_OPTIONS[0];
}

/** Giá trị gợi ý lấy từ hồ sơ, chỉ dùng để điền sẵn ô tra cứu. */
export function giaTriMacDinh(dossier: HoSoLienNganh | null | undefined, nguon: NguonLienNganh): string {
  if (!dossier) return "";
  if (nguon === "dan_cu" || nguon === "thue") return String(dossier.cccd || "");
  if (nguon === "dat_dai") {
    return String(dossier.thua_dat || dossier.ma_dinh_danh_dia_diem || "");
  }
  return String(dossier.ma_cong_trinh || dossier.ma_ho_so || "");
}

function chuanHoa(value: unknown): string {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/gi, "")
    .toLowerCase();
}

function bam32(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** UUID xác định từ chuỗi, chỉ để mock; không phải ID thật của D. */
export function uuidTuChuoi(value: string): string {
  const hex = [0, 1, 2, 3]
    .map((i) => bam32(`${value}|${i}`).toString(16).padStart(8, "0"))
    .join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-8${hex.slice(17, 20)}-${hex.slice(20, 32)}`;
}

function cheDienThoai(value: unknown): string {
  const s = String(value || "");
  if (s.length < 7) return s || "—";
  return `${s.slice(0, 4)}***${s.slice(-3)}`;
}

function cheMaSo(value: string): string {
  const s = String(value || "");
  if (s.length <= 4) return s || "—";
  return `••••${s.slice(-4)}`;
}

function truong(nhan: string, giaTri: unknown): TruongDuLieu {
  const s = String(giaTri ?? "").trim();
  return { nhan, gia_tri: s || "—" };
}

function ketQuaKhop(nguon: NguonLienNganh, dossier: HoSoLienNganh, query: string): KetQuaTraCuu {
  const meta = nguonMeta(nguon);
  const maDinhDanh = uuidTuChuoi(`${nguon}:${chuanHoa(query)}`);
  if (nguon === "dan_cu") {
    return {
      nguon,
      he_thong: meta.he_thong,
      trang_thai: "khop",
      do_tin_cay: 0.96,
      mo_ta: "Thông tin khớp với hồ sơ hiện tại. Cán bộ đối chiếu và xác nhận.",
      mdm_id: maDinhDanh,
      truong: [
        truong("Họ tên", dossier.ho_ten || "Nguyễn Văn Mẫu"),
        truong("CCCD", cheCccd(query)),
        truong("Điện thoại", cheDienThoai(dossier.dien_thoai)),
        truong("Địa chỉ thường trú", dossier.dia_chi_cong_trinh || "Số 1 Đường Mẫu"),
        truong("Trạng thái", "Đang sinh sống tại địa bàn"),
      ],
    };
  }
  if (nguon === "dat_dai") {
    return {
      nguon,
      he_thong: meta.he_thong,
      trang_thai: "khop",
      do_tin_cay: 0.93,
      mo_ta: "Thửa đất khớp hồ sơ. Kiểm tra diện tích và mục đích sử dụng trước khi xác nhận.",
      mdm_id: maDinhDanh,
      truong: [
        truong("Thửa/tờ", dossier.thua_dat || query),
        truong("Mã định danh", dossier.ma_dinh_danh_dia_diem || "Chưa có"),
        truong("Diện tích", dossier.dien_tich_san_m2 ? `${dossier.dien_tich_san_m2} m²` : "—"),
        truong("Loại đất", "Đất ở đô thị"),
        truong("Chủ sử dụng", cheCccd(dossier.cccd || "")),
      ],
    };
  }
  if (nguon === "thue") {
    return {
      nguon,
      he_thong: meta.he_thong,
      trang_thai: "khop",
      do_tin_cay: 0.89,
      mo_ta: "Có nghĩa vụ thuế liên quan. Đối chiếu số tiền và trạng thái trước khi xác nhận.",
      mdm_id: maDinhDanh,
      truong: [
        truong("Mã số thuế", cheMaSo(query)),
        truong("Nghĩa vụ", "Lệ phí cấp phép xây dựng"),
        truong("Số tiền", "1.500.000 đ"),
        truong("Trạng thái", "Đã thanh toán"),
      ],
    };
  }
  return {
    nguon,
    he_thong: meta.he_thong,
    trang_thai: "khop",
    do_tin_cay: 0.84,
    mo_ta: "Có giấy chứng nhận PCCC còn hiệu lực. Đối chiếu số giấy và ngày cấp.",
    mdm_id: maDinhDanh,
    truong: [
      truong("Số giấy chứng nhận", `PCCC-2026-${String(bam32(query) % 10000).padStart(4, "0")}`),
      truong("Ngày cấp", "15/10/2026"),
      truong("Cơ quan cấp", "Phòng Cảnh sát PCCC&CNCH"),
      truong("Trạng thái", "Còn hiệu lực"),
    ],
  };
}

function ketQuaKhongKhop(nguon: NguonLienNganh, query: string): KetQuaTraCuu {
  const meta = nguonMeta(nguon);
  return {
    nguon,
    he_thong: meta.he_thong,
    trang_thai: "khong_khop",
    do_tin_cay: 0.41,
    mo_ta: "Thông tin trả về không khớp hồ sơ hiện tại. Kiểm tra lại trước khi xác nhận.",
    mdm_id: uuidTuChuoi(`${nguon}:${chuanHoa(query)}`),
    truong: [
      truong("Giá trị tra cứu", cheMaSo(query)),
      truong("Kết quả đối chiếu", "Không khớp hồ sơ"),
    ],
  };
}

function ketQuaKhongThay(nguon: NguonLienNganh): KetQuaTraCuu {
  const meta = nguonMeta(nguon);
  return {
    nguon,
    he_thong: meta.he_thong,
    trang_thai: "khong_thay",
    do_tin_cay: 0,
    mo_ta: "Không tìm thấy bản ghi phù hợp trong nguồn dữ liệu mẫu.",
    mdm_id: uuidTuChuoi(`${nguon}:khong-thay`),
    truong: [],
  };
}

/** Tra cứu mẫu, đồng bộ; UI tự thêm độ trễ để mô phỏng mạng. */
export function traCuuMock(nguon: NguonLienNganh, query: string, dossier: HoSoLienNganh | null | undefined): KetQuaTraCuu {
  const q = String(query || "").trim();
  if (!q) return ketQuaKhongThay(nguon);
  if (!dossier) return ketQuaKhongThay(nguon);

  if (nguon === "dan_cu" || nguon === "thue") {
    const soCccd = String(dossier.cccd || "").replace(/\D/g, "");
    const soTraCuu = q.replace(/\D/g, "");
    if (!soCccd || !soTraCuu) return ketQuaKhongThay(nguon);
    if (soTraCuu === soCccd) return ketQuaKhop(nguon, dossier, soTraCuu);
    if (soTraCuu.length === 12) return ketQuaKhongKhop(nguon, soTraCuu);
    return ketQuaKhongThay(nguon);
  }

  if (nguon === "dat_dai") {
    const cuaHoSo = chuanHoa(dossier.thua_dat || dossier.ma_dinh_danh_dia_diem);
    const nhap = chuanHoa(q);
    if (!cuaHoSo || !nhap) return ketQuaKhongThay(nguon);
    return nhap.includes(cuaHoSo) || cuaHoSo.includes(nhap)
      ? ketQuaKhop(nguon, dossier, q)
      : ketQuaKhongKhop(nguon, q);
  }

  const cuaHoSo = chuanHoa(dossier.ma_cong_trinh || dossier.ma_ho_so);
  const nhap = chuanHoa(q);
  if (!cuaHoSo || !nhap) return ketQuaKhongThay(nguon);
  return nhap.includes(cuaHoSo) || cuaHoSo.includes(nhap)
    ? ketQuaKhop(nguon, dossier, q)
    : ketQuaKhongKhop(nguon, q);
}

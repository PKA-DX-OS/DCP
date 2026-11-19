// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * API 5.2 giả lập bằng fixture, để làm giao diện khi backend chưa có. Chỉ bật khi build/dev với
 * VITE_MOCK_DESIGN_REVIEW=1; dữ liệu nằm trong bộ nhớ, tải lại trang là về như cũ.
 */
import boMon from "./fixtures/bo-mon.json";
import dsPhienBan from "./fixtures/ds-phien-ban.json";
import nhanXet from "./fixtures/nhan-xet.json";
import type {
  BanVe,
  BoMon,
  DanhSachBanVe,
  DesignReviewApi,
  NhanXet,
  PhienBan,
  PhienBanDayDu,
  TrangThaiThamDinh,
} from "./types";

export const MOCK_ENABLED: boolean = import.meta.env.VITE_MOCK_DESIGN_REVIEW === "1";

class LoiMock extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

const sao = <T>(x: T): T => JSON.parse(JSON.stringify(x));

export function createMockApi(nguoi = "Người dùng thử"): DesignReviewApi {
  const ds = {
    boMon: sao(boMon) as BoMon[],
    phienBan: sao(dsPhienBan) as PhienBanDayDu[],
    nhanXet: sao(nhanXet) as NhanXet[],
    khoa: new Map<string, unknown>(),
  };
  let seq = 900;
  const id = () => `7a1c2e00-0000-4000-8000-${String(++seq).padStart(12, "0")}`;
  const now = () => new Date().toISOString();

  function theoKhoa<T>(key: string | null | undefined, tao: () => T): T {
    if (key && ds.khoa.has(key)) return ds.khoa.get(key) as T;
    const kq = tao();
    if (key) ds.khoa.set(key, kq);
    return kq;
  }
  const timPhienBan = (pid: string) => {
    const pb = ds.phienBan.find((p) => p.id === pid);
    if (!pb) throw new LoiMock("PT404", "Không tìm thấy phiên bản");
    return pb;
  };
  const timBanVe = (bid: string) => {
    for (const pb of ds.phienBan) {
      const bv = pb.ban_ve.find((b) => b.id === bid);
      if (bv) return { pb, bv };
    }
    throw new LoiMock("PT404", "Không tìm thấy bản vẽ");
  };
  const moiNhat = (hoSo: string) =>
    ds.phienBan.filter((p) => p.ho_so_id === hoSo).sort((a, b) => b.so_phien_ban - a.so_phien_ban)[0] || null;
  const boPhienBan = ({ ban_ve: _bv, ...pb }: PhienBanDayDu): PhienBan => pb;

  return {
    async dsBoMon() {
      return sao(ds.boMon);
    },
    async taoPhienBan(b) {
      return theoKhoa(b.p_idempotency_key, () => {
        const truoc = moiNhat(b.p_ho_so_id);
        const pb: PhienBanDayDu = {
          id: id(),
          ho_so_id: b.p_ho_so_id,
          so_phien_ban: (truoc?.so_phien_ban || 0) + 1,
          mo_ta_thay_doi: b.p_mo_ta,
          trang_thai: "dang_soan",
          created_by: nguoi,
          created_at: now(),
          ban_ve: [],
        };
        ds.phienBan.push(pb);
        return boPhienBan(sao(pb));
      });
    },
    async themBanVe(b) {
      return theoKhoa(b.p_idempotency_key, () => {
        const pb = timPhienBan(b.p_phien_ban_id);
        if (pb.trang_thai !== "dang_soan") throw new LoiMock("PT409", "Phiên bản đã nộp, không thêm bản vẽ được");
        const bv: BanVe = {
          id: id(),
          phien_ban_id: pb.id,
          bo_mon: b.p_bo_mon,
          ten: b.p_ten,
          file_id: b.p_file_id,
          sha256: "0".repeat(64),
          kich_thuoc: null,
          trang_thai: "cho_tham_dinh",
          nguoi_tham_dinh: null,
          ngay_tham_dinh: null,
          so_nhan_xet_mo: 0,
          created_at: now(),
        };
        pb.ban_ve.push(bv);
        return sao(bv);
      });
    },
    async dsBanVe(b): Promise<DanhSachBanVe> {
      const pb = b.p_phien_ban_id ? timPhienBan(b.p_phien_ban_id) : moiNhat(b.p_ho_so_id);
      return {
        phien_ban: pb ? boPhienBan(sao(pb)) : null,
        nhom: ds.boMon.map((m) => ({
          bo_mon: m.ma,
          ten: m.ten,
          bat_buoc: m.bat_buoc,
          ban_ve: sao((pb?.ban_ve || []).filter((x) => x.bo_mon === m.ma)),
        })),
      };
    },
    async dsPhienBan(b) {
      return sao(ds.phienBan.filter((p) => p.ho_so_id === b.p_ho_so_id).sort((x, y) => y.so_phien_ban - x.so_phien_ban));
    },
    async danhGiaBanVe(b) {
      const { bv } = timBanVe(b.p_ban_ve_id);
      bv.trang_thai = b.p_ket_qua;
      bv.nguoi_tham_dinh = nguoi;
      bv.ngay_tham_dinh = now();
      return sao(bv);
    },
    async themNhanXet(b) {
      return theoKhoa(b.p_idempotency_key, () => {
        const { pb, bv } = timBanVe(b.p_ban_ve_id);
        const nx: NhanXet = {
          id: id(),
          ban_ve_id: bv.id,
          phien_ban_id: pb.id,
          bo_mon: bv.bo_mon,
          nguoi,
          noi_dung: b.p_noi_dung,
          muc_do: b.p_muc_do,
          trang_thai: "mo",
          ghi_chu_xu_ly: null,
          xu_ly_luc: null,
          created_at: now(),
        };
        ds.nhanXet.unshift(nx);
        bv.so_nhan_xet_mo = (bv.so_nhan_xet_mo || 0) + 1;
        return sao(nx);
      });
    },
    async xuLyNhanXet(b) {
      const nx = ds.nhanXet.find((x) => x.id === b.p_nhan_xet_id);
      if (!nx) throw new LoiMock("PT404", "Không tìm thấy nhận xét");
      if (nx.trang_thai === "da_xu_ly") throw new LoiMock("PT409", "Nhận xét đã được xử lý");
      nx.trang_thai = "da_xu_ly";
      nx.ghi_chu_xu_ly = b.p_ghi_chu ?? null;
      nx.xu_ly_luc = now();
      const { bv } = timBanVe(nx.ban_ve_id);
      bv.so_nhan_xet_mo = Math.max(0, (bv.so_nhan_xet_mo || 0) - 1);
      return sao(nx);
    },
    async dsNhanXet(b) {
      return sao(
        ds.nhanXet.filter(
          (x) =>
            x.phien_ban_id === b.p_phien_ban_id &&
            (!b.p_bo_mon || x.bo_mon === b.p_bo_mon) &&
            (!b.p_muc_do || x.muc_do === b.p_muc_do) &&
            (!b.p_trang_thai || x.trang_thai === b.p_trang_thai),
        ),
      );
    },
    async trangThaiThamDinh(b): Promise<TrangThaiThamDinh> {
      const pb = moiNhat(b.p_ho_so_id);
      const boMonTT = ds.boMon.map((m) => {
        const xs = (pb?.ban_ve || []).filter((x) => x.bo_mon === m.ma);
        const ket_qua = !xs.length
          ? "chua_co"
          : xs.some((x) => x.trang_thai === "khong_dat")
            ? "khong_dat"
            : xs.some((x) => x.trang_thai === "cho_tham_dinh")
              ? "cho_tham_dinh"
              : "dat";
        return { bo_mon: m.ma, ten: m.ten, bat_buoc: m.bat_buoc, so_ban_ve: xs.length, ket_qua } as const;
      });
      const thieu = boMonTT.filter((x) => x.bat_buoc && x.so_ban_ve === 0).map((x) => x.bo_mon);
      const mo = pb ? ds.nhanXet.filter((x) => x.phien_ban_id === pb.id && x.trang_thai === "mo").length : 0;
      const ket_luan = !pb
        ? "chua_nop"
        : thieu.length || boMonTT.some((x) => x.ket_qua === "khong_dat")
          ? "khong_dat"
          : boMonTT.some((x) => x.ket_qua === "cho_tham_dinh")
            ? "dang_tham_dinh"
            : "dat";
      return {
        ho_so_id: b.p_ho_so_id,
        phien_ban_id: pb?.id ?? null,
        so_phien_ban: pb?.so_phien_ban ?? 0,
        bo_mon: boMonTT,
        thieu_bo_mon: thieu,
        nhan_xet_mo: mo,
        ket_luan,
      };
    },
  };
}

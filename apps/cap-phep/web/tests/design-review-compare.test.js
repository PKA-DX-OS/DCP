// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import { moTaSoSanh, soSanhPhienBan } from "../src/features/design-review/compare";

function phienBan(so, banVe) {
  return {
    id: `pb-${so}`,
    ho_so_id: "hs-1",
    so_phien_ban: so,
    mo_ta_thay_doi: `v${so}`,
    trang_thai: "dang_tham_dinh",
    created_by: "cdt",
    created_at: "2026-11-20T00:00:00Z",
    ban_ve: banVe,
  };
}
function banVe(id, boMon, ten, sha) {
  return {
    id,
    phien_ban_id: "pb",
    bo_mon: boMon,
    ten,
    file_id: `f-${id}`,
    sha256: sha,
    kich_thuoc: 1000,
    trang_thai: "cho_tham_dinh",
    nguoi_tham_dinh: null,
    ngay_tham_dinh: null,
    so_nhan_xet_mo: 0,
    created_at: "2026-11-20T00:00:00Z",
  };
}

describe("so sánh phiên bản thiết kế", () => {
  test("phát hiện thêm, bỏ, đổi theo hash", () => {
    const cu = phienBan(1, [
      banVe("a", "kien_truc", "KT-01", "a".repeat(64)),
      banVe("b", "mep", "MEP-01", "b".repeat(64)),
    ]);
    const moi = phienBan(2, [
      banVe("a", "kien_truc", "KT-01", "c".repeat(64)),
      banVe("c", "ket_cau", "KC-01", "d".repeat(64)),
    ]);
    const kq = soSanhPhienBan(cu, moi, ["kien_truc", "ket_cau", "mep"]);
    expect(kq.them.map((x) => x.id)).toEqual(["c"]);
    expect(kq.bo.map((x) => x.id)).toEqual(["b"]);
    expect(kq.doi.map((x) => x.moi.id)).toEqual(["a"]);
    expect(kq.thieuBoMon).toEqual(["mep"]);
    expect(moTaSoSanh(kq)).toContain("thêm 1 bản vẽ");
  });

  test("không đổi metadata/hash", () => {
    const cu = phienBan(1, [banVe("a", "kien_truc", "KT-01", "a".repeat(64))]);
    const moi = phienBan(2, [banVe("a", "kien_truc", "KT-01", "a".repeat(64))]);
    const kq = soSanhPhienBan(cu, moi, ["kien_truc"]);
    expect(kq.them).toEqual([]);
    expect(kq.bo).toEqual([]);
    expect(kq.doi).toEqual([]);
    expect(kq.thieuBoMon).toEqual([]);
    expect(moTaSoSanh(kq)).toBe("không đổi metadata/hash");
  });

  test("cảnh báo thiếu bộ môn bắt buộc", () => {
    const cu = phienBan(1, []);
    const moi = phienBan(2, [banVe("a", "kien_truc", "KT-01", "a".repeat(64))]);
    const kq = soSanhPhienBan(cu, moi, ["kien_truc", "ket_cau", "mep"]);
    expect(kq.thieuBoMon).toEqual(["ket_cau", "mep"]);
    expect(moTaSoSanh(kq)).toContain("thiếu ket_cau, mep");
  });
});

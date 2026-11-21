// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { describe, expect, test } from "vitest";
import {
  CHECKLIST_HIEN_TRUONG,
  canhBaoNhap,
  loiNhap,
  moTaXungDot,
  taoNhapMoi,
  timXungDot,
  tomTatGhiChu,
} from "../src/utils/field-inspection";

const CONG_TRINH = {
  id: "ct-1",
  ma_cong_trinh: "CT-001",
  dia_chi: "12 Lê Lợi, Phường Mẫu",
};

function nhapDayDu() {
  const d = taoNhapMoi(CONG_TRINH, 1000);
  for (const item of CHECKLIST_HIEN_TRUONG) d.checklist[item.key] = "dat";
  d.signature = "data:image/png;base64,abc";
  d.gps = { lat: 10.123456, lng: 106.654321, accuracy: 8.2 };
  d.ghiChu = "Hiện trường bình thường";
  return d;
}

describe("phiếu hiện trường", () => {
  test("tạo nháp mới có đủ checklist và trạng thái nháp", () => {
    const d = taoNhapMoi(CONG_TRINH, 1000);
    expect(d.maCongTrinh).toBe("CT-001");
    expect(d.createdAt).toBe(1000);
    expect(d.status).toBe("nhap");
    expect(Object.keys(d.checklist)).toHaveLength(CHECKLIST_HIEN_TRUONG.length);
    expect(Object.values(d.checklist).every((v) => v === "")).toBe(true);
  });

  test("chặn gửi khi chưa đánh giá đủ checklist hoặc chưa ký", () => {
    const d = taoNhapMoi(CONG_TRINH);
    const loi = loiNhap(d);
    expect(loi.some((x) => x.includes("Chưa đánh giá"))).toBe(true);
    expect(loi).toContain("Cần ký tay trước khi gửi phiếu.");

    const du = nhapDayDu();
    expect(loiNhap(du)).toEqual([]);
  });

  test("cảnh báo không chặn khi thiếu GPS/ảnh/ghi chú", () => {
    const d = nhapDayDu();
    d.gps = null;
    d.ghiChu = "";
    expect(canhBaoNhap(d)).toEqual(["Chưa có vị trí GPS.", "Chưa có ảnh hiện trường.", "Chưa có ghi chú."]);
  });

  test("tóm tắt ghi chú có checklist, GPS, ảnh và chữ ký", () => {
    const d = nhapDayDu();
    d.photos.push({ id: "a1", name: "anh.jpg", type: "image/jpeg", size: 100, blob: new Blob(["x"]), addedAt: 1 });
    const text = tomTatGhiChu(d);
    expect(text).toContain("[PWA hiện trường]");
    expect(text).toContain("CT-001");
    expect(text).toContain("GPS: 10.123456, 106.654321");
    expect(text).toContain("Có giấy phép xây dựng tại công trình: Đạt");
    expect(text).toContain("Ảnh: 1");
    expect(text).toContain("Chữ ký: có");
  });

  test("phát hiện phiếu mới hơn cùng công trình", () => {
    const d = nhapDayDu();
    const cu = { id: "p-cu", cong_trinh_id: "ct-1", created_at: "1970-01-01T00:00:00Z" };
    const moi = { id: "p-moi", ma_phieu: "PK-002", cong_trinh_id: "ct-1", created_at: "2026-11-21T08:00:00+07:00" };
    const khac = { id: "p-3", cong_trinh_id: "ct-2", created_at: "2026-11-21T08:00:00+07:00" };
    expect(timXungDot(d, [cu, khac])).toBeNull();
    expect(timXungDot(d, [cu, khac, moi])?.id).toBe("p-moi");
    expect(moTaXungDot(moi)).toContain("PK-002");
  });
});

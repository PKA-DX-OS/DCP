// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, describe, expect, test, vi } from "vitest";
import { fetchDossier360, timKiemToanCuc } from "../src/api/dh";

function traLoi(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === null || body === undefined ? "" : JSON.stringify(body)),
  };
}

const HO_SO = [
  {
    id: "00000000-0000-4000-8000-000000000101",
    ma_ho_so: "CP-MAU-000001",
    ho_ten: "Nguyễn Văn Mẫu",
    cccd: "001099123456",
    dien_thoai: "0901234567",
    thua_dat: "125",
    dia_chi_cong_trinh: "12 Đường Mẫu, Phường Mẫu",
    trang_thai: "DA_CAP",
  },
  {
    id: "00000000-0000-4000-8000-000000000102",
    ma_ho_so: "CP-MAU-000002",
    ho_ten: "Trần Thị Mẫu",
    cccd: "001099654321",
    dien_thoai: "0912345678",
    thua_dat: "126",
    dia_chi_cong_trinh: "14 Đường Mẫu, Phường Mẫu",
    trang_thai: "DANG_THAM_DINH",
  },
];

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("tìm kiếm toàn cục H", () => {
  test("dùng API /search khi API đã có", async () => {
    const fetchMock = vi.fn(async () =>
      traLoi(200, {
        groups: [
          {
            type: "ho_so",
            total: 1,
            items: [
              {
                type: "ho_so",
                id: HO_SO[0].id,
                nhan: "CP-MAU-000001",
                phu: "Đã cấp phép · 12 Đường Mẫu",
                khop: "exact",
                diem: 1,
                dossier_id: HO_SO[0].id,
              },
            ],
          },
        ],
        took_ms: 4,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const kq = await timKiemToanCuc("token", "CP-MAU-000001");

    expect(kq.source).toBe("api");
    expect(kq.data.groups[0].items[0].nhan).toBe("CP-MAU-000001");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/search?q=CP-MAU-000001");
  });

  test("API thiếu thì tìm trong danh sách hồ sơ và không trả CCCD/điện thoại đầy đủ", async () => {
    const fetchMock = vi.fn(async (url) => {
      if (String(url).includes("/search")) return traLoi(404, { message: "not found" });
      return traLoi(200, HO_SO);
    });
    vi.stubGlobal("fetch", fetchMock);

    const kq = await timKiemToanCuc("token", "CP-MAU-000001");

    expect(kq.source).toBe("cuc-bo");
    expect(kq.data.groups).toHaveLength(1);
    expect(kq.data.groups[0].items).toHaveLength(1);
    expect(kq.data.groups[0].items[0].dossier_id).toBe(HO_SO[0].id);
    const json = JSON.stringify(kq.data);
    expect(json).not.toContain("001099123456");
    expect(json).not.toContain("0901234567");
  });

  test("tìm đúng CCCD 12 số trong danh sách dự phòng", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url) => {
        if (String(url).includes("/search")) return traLoi(404, { message: "not found" });
        return traLoi(200, HO_SO);
      }),
    );

    const kq = await timKiemToanCuc("token", "001099123456");

    expect(kq.source).toBe("cuc-bo");
    expect(kq.data.groups[0].items).toHaveLength(1);
    expect(kq.data.groups[0].items[0].nhan).toBe("CP-MAU-000001");
    expect(JSON.stringify(kq.data)).not.toContain("001099123456");
  });

  test("từ khóa dưới 2 ký tự không gọi mạng", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const kq = await timKiemToanCuc("token", "C");

    expect(kq.data.groups).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("360 hồ sơ H", () => {
  test("API 360 lỗi thì trả null để UI dùng dữ liệu hồ sơ hiện có", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => traLoi(404, { code: "MDM_NOT_FOUND" })));

    await expect(fetchDossier360("token", "00000000-0000-4000-8000-000000000101")).resolves.toBeNull();
  });
});

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, describe, expect, test, vi } from "vitest";
import { createMdmLink, fetchDossierLinks, searchMdmEntities } from "../src/api/mdm";

function traLoi(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === null || body === undefined ? "" : JSON.stringify(body)),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("liên kết MDM của hồ sơ", () => {
  test("dùng API khi đã có", async () => {
    const fetchMock = vi.fn(async () =>
      traLoi(200, {
        dossier_id: "11111111-1111-4111-8111-111111111111",
        subject: { type: "subject", id: "s1", nhan: "Trần Văn Minh", confidence: 0.9 },
        parcel: null,
        construction: null,
        permit: null,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const kq = await fetchDossierLinks("token", "11111111-1111-4111-8111-111111111111");

    expect(kq.source).toBe("api");
    expect(kq.data?.subject?.nhan).toBe("Trần Văn Minh");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/mdm/dossiers/");
  });

  test("404 thì trả nguồn khong_co, không ném lỗi", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => traLoi(404, { detail: { loi: "not found" } })));

    const kq = await fetchDossierLinks("token", "11111111-1111-4111-8111-111111111111");

    expect(kq).toEqual({ data: null, source: "khong_co" });
  });

  test("thiếu token/id thì không gọi mạng", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchDossierLinks("", "id")).resolves.toEqual({ data: null, source: "khong_co" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("tìm thực thể dữ liệu chủ đúng tham số và trả items", async () => {
    const fetchMock = vi.fn(async () =>
      traLoi(200, {
        items: [{ type: "parcel", id: "p1", nhan: "Thửa td-a-01", ma: "790101000001", confidence: 1 }],
        page: 1,
        page_size: 10,
        total: 1,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const kq = await searchMdmEntities("token", "td-a-01", "parcel");

    expect(kq.items[0].nhan).toBe("Thửa td-a-01");
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/api/v1/mdm/search?");
    expect(url).toContain("q=td-a-01");
    expect(url).toContain("type=parcel");
  });

  test("tạo liên kết gửi Idempotency-Key và body đúng", async () => {
    const fetchMock = vi.fn(async () =>
      traLoi(201, { dossier_id: "11111111-1111-4111-8111-111111111111" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createMdmLink("token", {
      dossier_id: "11111111-1111-4111-8111-111111111111",
      entity_type: "parcel",
      entity_id: "p1",
    });

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/api/v1/mdm/links");
    const opts = fetchMock.mock.calls[0][1];
    expect(opts.method).toBe("POST");
    expect(opts.headers["Idempotency-Key"].length).toBeGreaterThanOrEqual(8);
    expect(JSON.parse(opts.body)).toEqual({
      dossier_id: "11111111-1111-4111-8111-111111111111",
      entity_type: "parcel",
      entity_id: "p1",
    });
  });
});

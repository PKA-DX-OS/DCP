// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, describe, expect, test, vi } from "vitest";
import { fetchDossierLinks } from "../src/api/mdm";

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
});

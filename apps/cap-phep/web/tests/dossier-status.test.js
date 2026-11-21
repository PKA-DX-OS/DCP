// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, describe, expect, test, vi } from "vitest";
import { fetchDossierStatuses } from "../src/api/dossiers";

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

describe("trạng thái sống của hồ sơ", () => {
  test("gộp nhiều hồ sơ vào một lần gọi và trả map id → trạng thái", async () => {
    const fetchMock = vi.fn(async () =>
      traLoi(200, [
        { id: "11111111-1111-4111-8111-111111111111", trang_thai: "DA_CAP" },
        { id: "22222222-2222-4222-8222-222222222222", trang_thai: "DANG_THAM_DINH" },
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);

    const map = await fetchDossierStatuses("token", [
      "11111111-1111-4111-8111-111111111111",
      "22222222-2222-4222-8222-222222222222",
      "11111111-1111-4111-8111-111111111111",
    ]);

    expect(map).toEqual({
      "11111111-1111-4111-8111-111111111111": "DA_CAP",
      "22222222-2222-4222-8222-222222222222": "DANG_THAM_DINH",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/rest/v_ho_so?select=id,trang_thai&id=in.(");
    expect(url.split("11111111-1111-4111-8111-111111111111")).toHaveLength(2);
  });

  test("không có id thì không gọi mạng", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchDossierStatuses("token", [])).resolves.toEqual({});
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

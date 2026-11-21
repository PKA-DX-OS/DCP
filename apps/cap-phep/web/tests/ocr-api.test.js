// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  confirmOcr,
  datLaiMockOcr,
  fetchOcrDetail,
  fetchOcrQueue,
  mockConfirmOcr,
  mockRejectOcr,
} from "../src/api/ocr";

function traLoi(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === null || body === undefined ? "" : JSON.stringify(body)),
  };
}

beforeEach(() => datLaiMockOcr());
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("API OCR", () => {
  test("API thiếu thì trả hàng chờ mẫu đã lọc", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => traLoi(404, { code: "OCR_OFF" })));

    const kq = await fetchOcrQueue("token", { status: "needs_review", max_confidence: 0.8 });

    expect(kq.source).toBe("mock");
    expect(kq.data.items.length).toBeGreaterThan(0);
    expect(kq.data.items.every((x) => x.status === "needs_review")).toBe(true);
    expect(kq.data.items.every((x) => x.confidence !== null && x.confidence <= 0.8)).toBe(true);
  });

  test("API có thì dùng dữ liệu API", async () => {
    const fetchMock = vi.fn(async () =>
      traLoi(200, {
        items: [
          {
            id: "00000000-0000-4000-8000-000000009999",
            file_id: "00000000-0000-4000-8000-000000009998",
            dossier_id: null,
            doc_type: "cccd",
            status: "needs_review",
            confidence: 0.66,
            created_at: "2026-11-21T08:00:00+07:00",
          },
        ],
        page: 1,
        page_size: 20,
        total: 1,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const kq = await fetchOcrQueue("token", { status: "needs_review" });

    expect(kq.source).toBe("api");
    expect(kq.data.total).toBe(1);
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/ocr?status=needs_review");
  });

  test("chi tiết fallback mock khi hàng chờ đang mock, nhưng không fallback khi đã có API", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => traLoi(404, { code: "OCR_NOT_FOUND" })));

    const kq = await fetchOcrDetail("token", "00000000-0000-4000-8000-000000001001", true);
    expect(kq.source).toBe("mock");
    expect(kq.data.fields.length).toBeGreaterThan(0);

    await expect(fetchOcrDetail("token", "00000000-0000-4000-8000-000000001001", false)).rejects.toThrow();
  });

  test("xác nhận thật gửi đúng body và Idempotency-Key", async () => {
    const fetchMock = vi.fn(async () =>
      traLoi(200, {
        id: "00000000-0000-4000-8000-000000001001",
        file_id: "00000000-0000-4000-8000-000000001101",
        dossier_id: "00000000-0000-4000-8000-000000000101",
        doc_type: "giay_chung_nhan_qsdd",
        status: "confirmed",
        confidence: 0.71,
        created_at: "2026-11-20T09:00:00+07:00",
        fields: [],
        reviewed_by: "mc.mau",
        reviewed_at: "2026-11-20T09:10:00+07:00",
        reject_reason: null,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await confirmOcr("token", "00000000-0000-4000-8000-000000001001", [
      { name: "dien_tich_m2", value: "82.5" },
    ]);

    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe("POST");
    expect(init.headers["Idempotency-Key"]).toBeTruthy();
    expect(JSON.parse(init.body)).toEqual({ fields: [{ name: "dien_tich_m2", value: "82.5" }] });
  });

  test("bản mô phỏng cập nhật trường đã sửa và trạng thái", async () => {
    const kq = mockConfirmOcr("00000000-0000-4000-8000-000000001001", [
      { name: "so_thua", value: "125" },
      { name: "to_ban_do", value: "18" },
      { name: "dien_tich_m2", value: "82.5" },
    ]);
    const dienTich = kq.fields.find((f) => f.name === "dien_tich_m2");
    expect(kq.status).toBe("confirmed");
    expect(dienTich.value).toBe("82.5");
    expect(dienTich.edited).toBe(true);

    const tuChoi = mockRejectOcr("00000000-0000-4000-8000-000000001002", "Ảnh mờ");
    expect(tuChoi.status).toBe("rejected");
    expect(tuChoi.reject_reason).toBe("Ảnh mờ");
  });
});

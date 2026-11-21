// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { beforeEach, describe, expect, test } from "vitest";
import {
  docCacheCongTrinh,
  docNhap,
  luuCacheCongTrinh,
  luuNhap,
  taiDsNhap,
  xoaCacheCongTrinh,
  xoaNhap,
  xoaTatCaNhap,
} from "../src/utils/field-drafts";
import { taoNhapMoi } from "../src/utils/field-inspection";

const CONG_TRINH = { id: "ct-1", ma_cong_trinh: "CT-001", dia_chi: "12 Lê Lợi" };

beforeEach(async () => {
  await xoaTatCaNhap();
  await xoaCacheCongTrinh();
});

describe("kho nháp hiện trường", () => {
  test("lưu, đọc, liệt kê và xóa nháp", async () => {
    const a = taoNhapMoi(CONG_TRINH, 1000);
    a.updatedAt = 1000;
    const b = taoNhapMoi(CONG_TRINH, 2000);
    b.updatedAt = 2000;
    await luuNhap(a);
    await luuNhap(b);

    expect((await docNhap(a.id))?.id).toBe(a.id);
    const ds = await taiDsNhap();
    expect(ds.map((x) => x.id)).toEqual([b.id, a.id]);

    await xoaNhap(a.id);
    expect(await docNhap(a.id)).toBeNull();
    expect((await taiDsNhap()).map((x) => x.id)).toEqual([b.id]);
  });

  test("lưu và đọc cache công trình", async () => {
    await luuCacheCongTrinh([CONG_TRINH]);
    expect(await docCacheCongTrinh()).toEqual([CONG_TRINH]);
    await xoaCacheCongTrinh();
    expect(await docCacheCongTrinh()).toEqual([]);
  });
});

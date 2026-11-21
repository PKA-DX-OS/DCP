// @vitest-environment happy-dom
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import Dossier360Panel from "../src/components/Dossier360Panel.vue";
import { fetchDossier360 } from "../src/api/dh";

vi.mock("../src/api/dh", () => ({
  fetchDossier360: vi.fn(),
}));

const HO_SO = {
  id: "00000000-0000-4000-8000-000000000101",
  ma_ho_so: "CP-MAU-000001",
  ho_ten: "Nguyễn Văn Mẫu",
  cccd: "001099123456",
  dien_thoai: "0901234567",
  thua_dat: "125",
  dia_chi_cong_trinh: "12 Đường Mẫu, Phường Mẫu",
  trang_thai: "DA_CAP",
  buoc: "hoan_thanh",
  so_tang: 3,
  dien_tich_san_m2: 150,
};

const DU_LIEU_360 = {
  ho_so: {
    id: HO_SO.id,
    ma_ho_so: HO_SO.ma_ho_so,
    trang_thai: HO_SO.trang_thai,
    buoc: HO_SO.buoc,
    created_at: "2026-11-01T08:00:00+07:00",
  },
  chu_dau_tu: {
    subject_id: "00000000-0000-4000-8000-000000000201",
    ho_ten: HO_SO.ho_ten,
    cccd_mask: "0010******56",
    dien_thoai_mask: "0901***567",
    so_ho_so_khac: 2,
  },
  thua_dat: {
    parcel_id: "00000000-0000-4000-8000-000000000301",
    so_thua: "125",
    to_ban_do: "18",
    ma_dinh_danh_dia_diem: "790100000125",
    dien_tich_m2: 82.5,
  },
  cong_trinh: {
    construction_id: "00000000-0000-4000-8000-000000000401",
    ma_cong_trinh: "CT-MAU-01",
    dia_chi: HO_SO.dia_chi_cong_trinh,
  },
  giay_phep: {
    permit_id: "00000000-0000-4000-8000-000000000501",
    so_giay_phep: "MAU-001/2026",
    public_code: "MAU-001-2026",
    trang_thai: "valid",
    ngay_cap: "2026-11-15T08:00:00+07:00",
  },
  kiem_tra: [{ loai: "quy_hoach", ket_qua: "dat", thoi_diem: "2026-11-11T09:00:00+07:00", mo_ta: "Mật độ đạt" }],
  tai_chinh: [{ loai: "Lệ phí cấp phép", so_tien: 75000, trang_thai: "da_thu" }],
  canh_bao: [{ nguon: "dq", code: "DQ-HOSO-03", severity: "warn", message: "Điện thoại chưa đúng định dạng", field: "dien_thoai" }],
  audit: { so_su_kien: 24, gan_nhat: "2026-11-20T09:00:00+07:00" },
};

enableAutoUnmount(afterEach);

beforeEach(() => {
  vi.mocked(fetchDossier360).mockResolvedValue(null);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("Dossier360Panel", () => {
  test("API thiếu thì dùng dữ liệu hồ sơ hiện tại và ghi rõ nguồn", async () => {
    const w = mount(Dossier360Panel, { props: { dossier: HO_SO, token: "token" } });
    await flushPromises();

    expect(fetchDossier360).toHaveBeenCalledWith("token", HO_SO.id);
    expect(w.text()).toContain("API 360 chưa sẵn sàng");
    expect(w.text()).toContain("Từ hồ sơ hiện tại");
    expect(w.text()).toContain("Nguyễn Văn Mẫu");
    expect(w.text()).toContain("0010****3456");
    expect(w.text()).not.toContain("001099123456");
  });

  test("API có thì hiện liên kết MDM và giấy phép công khai", async () => {
    vi.mocked(fetchDossier360).mockResolvedValue(DU_LIEU_360);

    const w = mount(Dossier360Panel, { props: { dossier: HO_SO, token: "token" } });
    await flushPromises();

    expect(w.text()).toContain("Dữ liệu MDM");
    expect(w.text()).toContain("0010******56");
    expect(w.text()).toContain("790100000125");
    expect(w.text()).toContain("Hợp lệ");
    expect(w.text()).toContain("Đã thu");
    expect(w.text()).toContain("Chất lượng dữ liệu");
    expect(w.get("a[href='/kiem-tra/MAU-001-2026']").text()).toBe("MAU-001-2026");
  });
});

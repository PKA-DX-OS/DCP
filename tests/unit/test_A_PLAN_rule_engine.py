# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""A-PLAN-02: 10 quy tắc quy hoạch và các trường hợp biên."""

from construction.rules.planning_engine import check_planning, chon_zone, overall_pass, point_in_geometry

PARCEL = {
    "id": "parcel-1",
    "ma_thua_dat": "TD-TEST",
    "loai_dat": "dat_o",
    "geom": {"type": "Point", "coordinates": [106.7025, 10.7725]},
}

ZONE = {
    "id": "zone-1",
    "ma_zone": "QH-TEST",
    "ten": "Ô đô thị thử nghiệm",
    "loai_zone": "o_do_thi",
    "geom": {"type": "Polygon", "coordinates": [[[106.70, 10.77], [106.706, 10.77], [106.706, 10.776], [106.70, 10.776], [106.70, 10.77]]]},
}

QUOTAS = [
    {"chi_tieu": "max_height_m", "gia_tri_max": 12.0},
    {"chi_tieu": "max_floors", "gia_tri_max": 3.0},
    {"chi_tieu": "max_density_pct", "gia_tri_max": 70.0},
    {"chi_tieu": "max_far", "gia_tri_max": 2.0},
    {"chi_tieu": "setback_front_m", "gia_tri_min": 3.0},
    {"chi_tieu": "setback_side_m", "gia_tri_min": 1.0},
    {"chi_tieu": "setback_back_m", "gia_tri_min": 1.0},
    {"chi_tieu": "land_use", "don_vi": "dat_o"},
]

GOOD = {
    "so_tang": 3,
    "chieu_cao_m": 11.5,
    "mat_do_xay_dung_pct": 65,
    "far": 1.8,
    "khoang_lui_truoc_m": 3.5,
    "khoang_lui_hong_m": 1.2,
    "khoang_lui_sau_m": 1.2,
    "loai_dat": "dat_o",
}


def by_id(results):
    return {r["rule_id"]: r for r in results}


def test_point_in_polygon_va_multipolygon():
    assert point_in_geometry((106.7025, 10.7725), ZONE["geom"])
    assert not point_in_geometry((106.80, 10.80), ZONE["geom"])
    multi = {"type": "MultiPolygon", "coordinates": [ZONE["geom"]["coordinates"]]}
    assert point_in_geometry((106.7025, 10.7725), multi)


def test_du_10_rule_va_pass_khi_dat_het():
    results = check_planning(PARCEL, [ZONE], QUOTAS, GOOD)
    assert [r["rule_id"] for r in results] == [f"R{i:02d}" for i in range(1, 11)]
    assert overall_pass(results)
    assert not [r for r in results if r["severity"] == "error"]


def test_rule_01_thua_dat_ngoai_vung():
    results = by_id(check_planning(PARCEL, [], QUOTAS, GOOD))
    assert results["R01"]["passed"] is False
    assert results["R01"]["severity"] == "error"


def test_rule_02_sai_muc_dich_su_dung():
    proposal = dict(GOOD, loai_dat="dat_nong_nghiep")
    results = by_id(check_planning(PARCEL, [ZONE], QUOTAS, proposal))
    assert results["R02"]["passed"] is False


def test_rule_03_chieu_cao_vuot():
    results = by_id(check_planning(PARCEL, [ZONE], QUOTAS, dict(GOOD, chieu_cao_m=13)))
    assert results["R03"]["passed"] is False
    assert results["R03"]["severity"] == "error"


def test_rule_04_so_tang_vuot_khong_tu_dong_tu_choi_ho_so_hop_le():
    # Quy hoạch vùng chỉ cho 3 tầng: vượt là lỗi quy hoạch, không phải ngưỡng nội bộ 1-5.
    results = by_id(check_planning(PARCEL, [ZONE], QUOTAS, dict(GOOD, so_tang=5)))
    assert results["R04"]["passed"] is False
    assert results["R04"]["severity"] == "error"


def test_rule_05_mat_do_va_rule_06_far():
    results = by_id(check_planning(PARCEL, [ZONE], QUOTAS, dict(GOOD, mat_do_xay_dung_pct=75, far=2.5)))
    assert results["R05"]["passed"] is False
    assert results["R06"]["passed"] is False


def test_rule_07_08_khoang_lui():
    results = by_id(check_planning(PARCEL, [ZONE], QUOTAS, dict(GOOD, khoang_lui_truoc_m=2, khoang_lui_hong_m=0.5, khoang_lui_sau_m=0.5)))
    assert results["R07"]["passed"] is False
    assert results["R08"]["passed"] is False


def test_rule_09_hanh_lang_giao_thong():
    corridor = dict(ZONE, id="zone-2", ma_zone="QH-HL", loai_zone="hanh_lang_giao_thong")
    results = by_id(check_planning(PARCEL, [ZONE, corridor], QUOTAS, GOOD))
    assert results["R09"]["passed"] is False
    assert results["R09"]["severity"] == "error"


def test_rule_10_vung_cam_xay_dung():
    no_build = dict(ZONE, id="zone-3", ma_zone="QH-CAM", loai_zone="cam_xay_dung")
    results = by_id(check_planning(PARCEL, [ZONE, no_build], QUOTAS, GOOD))
    assert results["R10"]["passed"] is False
    assert results["R10"]["severity"] == "error"


def test_chon_zone_uu_tien_vung_cam_va_hanh_lang():
    corridor = dict(ZONE, id="zone-2", ma_zone="QH-HL", loai_zone="hanh_lang_giao_thong")
    assert chon_zone(PARCEL, [ZONE, corridor])["ma_zone"] == "QH-HL"


def test_thieu_chi_tieu_la_info_khong_chan():
    results = by_id(check_planning(PARCEL, [ZONE], [], GOOD))
    assert results["R03"]["passed"] is True
    assert results["R03"]["severity"] == "info"
    assert overall_pass(results.values())


def test_thieu_gia_tri_de_xuat_la_warning_khong_chan():
    results = by_id(check_planning(PARCEL, [ZONE], QUOTAS, {"loai_dat": "dat_o"}))
    assert results["R03"]["passed"] is True
    assert results["R03"]["severity"] == "warning"
    assert overall_pass(results.values())


def test_1000_ho_so_chay_nhanh_va_on_dinh():
    import time
    started = time.perf_counter()
    for _ in range(1000):
        assert overall_pass(check_planning(PARCEL, [ZONE], QUOTAS, GOOD))
    assert time.perf_counter() - started < 2.0


def test_1000_ho_so_100_vung_hieu_nang():
    import time

    zones = []
    for i in range(99):
        # Các vùng không chứa điểm, đặt lệch dần để buộc phải quét.
        offset = 0.01 * (i + 1)
        zones.append(dict(
            ZONE,
            id=f"z-{i}",
            ma_zone=f"QH-{i}",
            geom={"type": "Polygon", "coordinates": [[
                [106.70 + offset, 10.77], [106.706 + offset, 10.77],
                [106.706 + offset, 10.776], [106.70 + offset, 10.776],
                [106.70 + offset, 10.77],
            ]]},
        ))
    zones.append(ZONE)
    started = time.perf_counter()
    for _ in range(1000):
        assert overall_pass(check_planning(PARCEL, zones, QUOTAS, GOOD))
    assert time.perf_counter() - started < 3.0

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
A-PLAN-02 — 10 quy tắc kiểm tra quy hoạch.

Hàm thuần, không phụ thuộc DB để unit test được. Mỗi kết quả có:
rule_id, name, value, limit, passed, severity, reason, citation_key.

Nguyên tắc:
- Chỉ quy tắc pháp lý/quy hoạch rõ ràng mới trả severity='error'.
- Thiếu dữ liệu đề xuất hoặc thiếu chỉ tiêu cấu hình trả 'warning'/'info' và KHÔNG chặn.
- Không dùng ngưỡng nội bộ (diện tích, số tầng) để từ chối hồ sơ hợp pháp.
"""

from typing import Any, Iterable, Optional

RULES = [
    ("R01", "Thửa đất nằm trong vùng quy hoạch"),
    ("R02", "Mục đích sử dụng đất phù hợp"),
    ("R03", "Chiều cao công trình không vượt giới hạn"),
    ("R04", "Số tầng không vượt giới hạn"),
    ("R05", "Mật độ xây dựng không vượt giới hạn"),
    ("R06", "Hệ số sử dụng đất không vượt giới hạn"),
    ("R07", "Khoảng lùi trước đạt tối thiểu"),
    ("R08", "Khoảng lùi hông và sau đạt tối thiểu"),
    ("R09", "Không nằm trong hành lang giao thông"),
    ("R10", "Không nằm trong vùng cấm xây dựng"),
]

ZONE_NO_BUILD = "cam_xay_dung"
ZONE_CORRIDOR = "hanh_lang_giao_thong"


def _ring_contains(point: tuple[float, float], ring: Iterable[Iterable[float]]) -> bool:
    """Ray casting cho một vòng; trả True nếu điểm nằm trong/trên biên."""
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if len(pts) < 3:
        return False
    x, y = point
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        # Trên biên
        if (abs((xj - xi) * (y - yi) - (yj - yi) * (x - xi)) < 1e-12
                and min(xi, xj) - 1e-12 <= x <= max(xi, xj) + 1e-12
                and min(yi, yj) - 1e-12 <= y <= max(yi, yj) + 1e-12):
            return True
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _geometry_of(obj: Any) -> Optional[dict]:
    if not isinstance(obj, dict):
        return None
    if obj.get("type") == "Feature":
        return _geometry_of(obj.get("geometry"))
    if "geom" in obj:
        return _geometry_of(obj.get("geom"))
    if not obj.get("type"):
        return None
    return obj


def point_in_geometry(point: tuple[float, float], obj: Any) -> bool:
    geom = _geometry_of(obj)
    if not geom:
        return False
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return False
    if gtype == "Polygon":
        return _ring_contains(point, coords[0]) and not any(
            _ring_contains(point, hole) for hole in coords[1:]
        )
    if gtype == "MultiPolygon":
        return any(
            _ring_contains(point, poly[0]) and not any(_ring_contains(point, hole) for hole in poly[1:])
            for poly in coords
        )
    return False


def center_of(obj: Any) -> Optional[tuple[float, float]]:
    geom = _geometry_of(obj)
    if not geom:
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Point" and coords:
        return float(coords[0]), float(coords[1])
    ring = None
    if gtype == "Polygon" and coords:
        ring = coords[0]
    elif gtype == "MultiPolygon" and coords and coords[0]:
        ring = coords[0][0]
    if not ring:
        return None
    pts = [(float(p[0]), float(p[1])) for p in ring[:-1]] if len(ring) > 1 and ring[0] == ring[-1] else [(float(p[0]), float(p[1])) for p in ring]
    if not pts:
        return None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def zone_contains(parcel: Any, zone: dict) -> bool:
    center = center_of(parcel)
    if center is None:
        return False
    return point_in_geometry(center, zone.get("geom"))


def _zone_priority(zone: dict) -> int:
    loai = zone.get("loai_zone")
    if loai == ZONE_NO_BUILD:
        return 0
    if loai == ZONE_CORRIDOR:
        return 1
    return 2


def chon_zone(parcel: Any, zones: Iterable[dict]) -> Optional[dict]:
    """Chọn vùng quy hoạch chứa thửa đất; ưu tiên vùng cấm/hành lang để không bỏ sót rủi ro."""
    hits = [z for z in zones if zone_contains(parcel, z)]
    if not hits:
        return None
    hits.sort(key=lambda z: (_zone_priority(z), z.get("ma_zone") or ""))
    return hits[0]


def _quota_map(quotas: Iterable[dict]) -> dict[str, dict]:
    return {q.get("chi_tieu"): q for q in quotas if q.get("chi_tieu")}


def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _result(
    rule_id: str,
    value: Any,
    limit: Any,
    passed: bool,
    severity: str,
    reason: str,
    citation_key: Optional[str] = None,
) -> dict:
    name = dict(RULES)[rule_id]
    return {
        "rule_id": rule_id,
        "name": name,
        "value": value,
        "limit": limit,
        "passed": passed,
        "severity": severity,
        "reason": reason,
        "citation_key": citation_key,
    }


def _check_max(
    rule_id: str,
    proposal: dict,
    quota: Optional[dict],
    keys: tuple[str, ...],
    citation_key: Optional[str],
    label: str,
) -> dict:
    val = next((proposal.get(k) for k in keys if proposal.get(k) is not None), None)
    if quota is None:
        return _result(rule_id, val, None, True, "info", f"Chưa cấu hình chỉ tiêu {label} cho vùng; cần đối chiếu đồ án.", citation_key)
    limit = quota.get("gia_tri_max")
    if limit is None:
        return _result(rule_id, val, None, True, "info", f"Chỉ tiêu {label} không đặt giới hạn tối đa.", citation_key)
    num = _num(val)
    if num is None:
        return _result(rule_id, val, limit, True, "warning", f"Chưa có giá trị đề xuất cho {label}; cán bộ cần kiểm tra bổ sung.", citation_key)
    passed = num <= float(limit) + 1e-9
    reason = (
        f"{label.capitalize()} đề xuất {num:g} không vượt giới hạn {float(limit):g}."
        if passed else
        f"{label.capitalize()} đề xuất {num:g} vượt giới hạn {float(limit):g}."
    )
    return _result(rule_id, num, limit, passed, "error" if not passed else "info", reason, citation_key)


def _check_min(
    rule_id: str,
    proposal: dict,
    quota: Optional[dict],
    keys: tuple[str, ...],
    citation_key: Optional[str],
    label: str,
) -> dict:
    val = next((proposal.get(k) for k in keys if proposal.get(k) is not None), None)
    if quota is None:
        return _result(rule_id, val, None, True, "info", f"Chưa cấu hình chỉ tiêu {label} cho vùng; cần đối chiếu đồ án.", citation_key)
    limit = quota.get("gia_tri_min")
    if limit is None:
        return _result(rule_id, val, None, True, "info", f"Chỉ tiêu {label} không đặt giới hạn tối thiểu.", citation_key)
    num = _num(val)
    if num is None:
        return _result(rule_id, val, limit, True, "warning", f"Chưa có giá trị đề xuất cho {label}; cán bộ cần kiểm tra bổ sung.", citation_key)
    passed = num >= float(limit) - 1e-9
    reason = (
        f"{label.capitalize()} đề xuất {num:g} đạt tối thiểu {float(limit):g}."
        if passed else
        f"{label.capitalize()} đề xuất {num:g} nhỏ hơn tối thiểu {float(limit):g}."
    )
    return _result(rule_id, num, limit, passed, "error" if not passed else "info", reason, citation_key)


def check_planning(
    parcel: dict,
    zones: Iterable[dict],
    quotas: Iterable[dict],
    proposal: Optional[dict] = None,
) -> list[dict]:
    """Chạy 10 quy tắc; không truy cập DB."""
    proposal = dict(proposal or {})
    zones = list(zones or [])
    qmap = _quota_map(quotas or [])
    zone = chon_zone(parcel, zones)
    results: list[dict] = []

    # R01 — trong vùng quy hoạch
    if zone is None:
        results.append(_result("R01", None, None, False, "error", "Thửa đất không nằm trong vùng quy hoạch đã cập nhật; cần kiểm tra bản đồ và đồ án.", "LQH47-TOANVAN"))
    else:
        results.append(_result("R01", zone.get("ma_zone"), None, True, "info", f"Thửa đất thuộc vùng {zone.get('ma_zone')} — {zone.get('ten')}.", "LQH47-TOANVAN"))

    # R02 — mục đích sử dụng đất
    land_quota = qmap.get("land_use")
    allowed_land = (land_quota or {}).get("don_vi")
    parcel_land = proposal.get("loai_dat") or parcel.get("loai_dat")
    if land_quota is None or not allowed_land:
        results.append(_result("R02", parcel_land, None, True, "info", "Chưa cấu hình mục đích sử dụng đất được phép cho vùng; cần đối chiếu đồ án.", "LQH47-TOANVAN"))
    elif parcel_land == allowed_land:
        results.append(_result("R02", parcel_land, allowed_land, True, "info", f"Mục đích sử dụng đất {parcel_land} phù hợp vùng quy hoạch.", "LQH47-TOANVAN"))
    else:
        results.append(_result("R02", parcel_land, allowed_land, False, "error", f"Mục đích sử dụng đất {parcel_land} không phù hợp vùng quy hoạch ({allowed_land}).", "LQH47-TOANVAN"))

    # R03–R06 — giới hạn tối đa
    results.append(_check_max("R03", proposal, qmap.get("max_height_m"), ("chieu_cao_m", "height_m"), "LQH47-TOANVAN", "chiều cao"))
    results.append(_check_max("R04", proposal, qmap.get("max_floors"), ("so_tang", "floors"), "LQH47-TOANVAN", "số tầng"))
    results.append(_check_max("R05", proposal, qmap.get("max_density_pct"), ("mat_do_xay_dung_pct", "density_pct"), "LQH47-TOANVAN", "mật độ xây dựng"))
    results.append(_check_max("R06", proposal, qmap.get("max_far"), ("far", "he_so_su_dung_dat"), "LQH47-TOANVAN", "hệ số sử dụng đất"))

    # R07–R08 — khoảng lùi tối thiểu
    results.append(_check_min("R07", proposal, qmap.get("setback_front_m"), ("khoang_lui_truoc_m", "setback_front_m"), "LQH47-TOANVAN", "khoảng lùi trước"))
    side = _check_min("R08", proposal, qmap.get("setback_side_m"), ("khoang_lui_hong_m", "setback_side_m"), "LQH47-TOANVAN", "khoảng lùi hông")
    back = _check_min("R08", proposal, qmap.get("setback_back_m"), ("khoang_lui_sau_m", "setback_back_m"), "LQH47-TOANVAN", "khoảng lùi sau")
    if not side["passed"] or not back["passed"]:
        results.append(_result("R08", {"hong": side["value"], "sau": back["value"]}, {"hong": side["limit"], "sau": back["limit"]}, False, "error", side["reason"] + " " + back["reason"], "LQH47-TOANVAN"))
    elif side["severity"] == "warning" or back["severity"] == "warning":
        results.append(_result("R08", {"hong": side["value"], "sau": back["value"]}, {"hong": side["limit"], "sau": back["limit"]}, True, "warning", side["reason"] + " " + back["reason"], "LQH47-TOANVAN"))
    else:
        results.append(_result("R08", {"hong": side["value"], "sau": back["value"]}, {"hong": side["limit"], "sau": back["limit"]}, True, "info", side["reason"] + " " + back["reason"], "LQH47-TOANVAN"))

    # R09 — hành lang giao thông
    if zone and zone.get("loai_zone") == ZONE_CORRIDOR:
        results.append(_result("R09", zone.get("ma_zone"), None, False, "error", "Thửa đất nằm trong hành lang giao thông; không được xây dựng công trình kiên cố.", "LQH47-TOANVAN"))
    else:
        results.append(_result("R09", zone.get("ma_zone") if zone else None, None, True, "info", "Thửa đất không nằm trong hành lang giao thông đã cập nhật.", "LQH47-TOANVAN"))

    # R10 — vùng cấm xây dựng
    if zone and zone.get("loai_zone") == ZONE_NO_BUILD:
        results.append(_result("R10", zone.get("ma_zone"), None, False, "error", "Thửa đất nằm trong vùng cấm xây dựng.", "LQH47-TOANVAN"))
    else:
        results.append(_result("R10", zone.get("ma_zone") if zone else None, None, True, "info", "Thửa đất không nằm trong vùng cấm xây dựng đã cập nhật.", "LQH47-TOANVAN"))

    return results


def overall_pass(results: Iterable[dict]) -> bool:
    return not any(r.get("severity") == "error" for r in results)

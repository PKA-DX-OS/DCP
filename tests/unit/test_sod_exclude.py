# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import pytest
from fastapi import HTTPException


def enforce_sod_exclusion(actor_sub: str, variables: dict, sod_exclude_var: str = "nguoiThamDinh"):
    excluded_sub = variables.get(sod_exclude_var)
    if excluded_sub and actor_sub == excluded_sub:
        raise HTTPException(
            status_code=403,
            detail="Vi phạm quy tắc phân tách nhiệm vụ: Người thẩm định không thể tự mình phê duyệt cấp phép!",
        )


def test_sod_violation_raises_403():
    # Thẩm định viên 'td.binh' cố tình hoàn thành tác vụ phê duyệt
    variables = {"nguoiThamDinh": "td.binh", "quyet_dinh": "dong_y"}
    with pytest.raises(HTTPException) as exc:
        enforce_sod_exclusion(actor_sub="td.binh", variables=variables)
    assert exc.value.status_code == 403
    assert "phân tách nhiệm vụ" in exc.value.detail


def test_sod_compliance_allowed():
    # Lãnh đạo 'ld.hoa' hoàn thành tác vụ phê duyệt (khác với người thẩm định 'td.binh')
    variables = {"nguoiThamDinh": "td.binh", "quyet_dinh": "dong_y"}
    # Không xảy ra exception
    enforce_sod_exclusion(actor_sub="ld.hoa", variables=variables)

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Hạn của task khi BPMN không đặt dueDate: thời điểm tạo + SLA của bước trong flow_policies."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _flow():
    spec = importlib.util.spec_from_file_location("services_flow_due", ROOT / "services/flow/main.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["services_flow_due"] = mod
    spec.loader.exec_module(mod)
    return mod


flow = _flow()
POLICY = {"sla": {"taskKiemTraHopLe": "P3D", "taskPhanCong": "PT12H"}}


def test_giu_due_date_cua_flowable():
    t = {"taskDefinitionKey": "taskKiemTraHopLe", "createTime": "2026-11-20T01:00:00.000+0000", "dueDate": "2026-11-21T00:00:00Z"}
    assert flow.suy_ra_han_task(t, POLICY) == "2026-11-21T00:00:00Z"


def test_tinh_tu_sla_khi_thieu_due_date():
    t = {"taskDefinitionKey": "taskKiemTraHopLe", "createTime": "2026-11-20T01:00:00.000+0000", "dueDate": None}
    assert flow.suy_ra_han_task(t, POLICY) == "2026-11-23T01:00:00Z"
    t = {"taskDefinitionKey": "taskPhanCong", "createTime": "2026-11-20T08:30:00.000+07:00"}
    assert flow.suy_ra_han_task(t, POLICY) == "2026-11-20T13:30:00Z"


def test_buoc_khong_khai_bao_sla_thi_khong_co_han():
    t = {"taskDefinitionKey": "taskKhongCo", "createTime": "2026-11-20T01:00:00.000+0000"}
    assert flow.suy_ra_han_task(t, POLICY) is None
    assert flow.suy_ra_han_task({"taskDefinitionKey": "taskPhanCong"}, POLICY) is None
    assert flow.suy_ra_han_task({"taskDefinitionKey": "taskPhanCong", "createTime": "2026-11-20T01:00:00Z"}, {}) is None

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""B-REVIEW-03: BPMN thẩm định thiết kế đa bộ môn và khai báo trong app.yaml."""

from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "cap-phep"
BPMN = APP / "bpmn" / "tham-dinh-thiet-ke.bpmn20.xml"

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "flowable": "http://flowable.org/bpmn",
}


def _process():
    tree = ET.parse(BPMN)
    proc = tree.getroot().find("bpmn:process[@id='tham-dinh-thiet-ke']", NS)
    assert proc is not None
    return proc


def test_bpmn_hop_le_va_co_multi_instance_theo_bo_mon():
    proc = _process()
    task = proc.find("bpmn:userTask[@id='taskThamDinhBoMon']", NS)
    assert task is not None
    assert task.get("name") == "Thẩm định bộ môn ${bo_mon}"
    assert task.get("{%s}candidateGroups" % NS["flowable"]) == "app:cap-phep:tham-dinh"
    multi = task.find("bpmn:multiInstanceLoopCharacteristics", NS)
    assert multi is not None
    assert multi.get("isSequential") == "false"
    assert multi.get("{%s}collection" % NS["flowable"]) == "${bo_mon_can_tham_dinh}"
    assert multi.get("{%s}elementVariable" % NS["flowable"]) == "bo_mon"


def test_bpmn_co_tong_hop_va_gateway_bo_sung():
    proc = _process()
    hop = proc.find("bpmn:userTask[@id='taskTongHopThietKe']", NS)
    assert hop is not None
    assert "lanh-dao" in hop.get("{%s}candidateGroups" % NS["flowable"])

    gateway = proc.find("bpmn:exclusiveGateway[@id='gwThietKe']", NS)
    assert gateway is not None
    assert gateway.get("default") == "flowThietKeDat"

    fail_flow = proc.find("bpmn:sequenceFlow[@id='flowThietKeKhongDat']", NS)
    assert fail_flow is not None
    assert fail_flow.get("targetRef") == "taskBoSungThietKe"
    condition = fail_flow.find("bpmn:conditionExpression", NS)
    assert "khong_dat" in (condition.text or "")

    back = proc.find("bpmn:sequenceFlow[@id='flowBoSungXong']", NS)
    assert back is not None
    assert back.get("targetRef") == "taskThamDinhBoMon"


def test_app_yaml_khai_bao_bpmn_va_chinh_sach_tham_dinh():
    app = yaml.safe_load((APP / "app.yaml").read_text(encoding="utf-8"))
    assert "bpmn/tham-dinh-thiet-ke.bpmn20.xml" in app["bpmn"]

    policy = app["flow_policies"]
    assert policy["initial_tasks"]["tham-dinh-thiet-ke"] == "taskThamDinhBoMon"
    assert policy["default_process_variables"]["tham-dinh-thiet-ke"]["bo_mon_can_tham_dinh"] == [
        "kien_truc",
        "ket_cau",
        "mep",
        "pccc",
    ]
    assert "ket_qua_bo_mon" in policy["task_variables"]["taskThamDinhBoMon"]
    assert policy["task_transitions"]["taskThamDinhBoMon"] == "taskTongHopThietKe"
    assert policy["task_transitions"]["taskBoSungThietKe"] == "taskThamDinhBoMon"
    assert policy["sla"]["taskThamDinhBoMon"] == "P5D"
    assert "taskBoSungThietKe" in policy["submitter_tasks"]

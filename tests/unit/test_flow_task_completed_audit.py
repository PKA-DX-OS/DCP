# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""D-MET-00: Test ghi ho_so_id và process_instance_id vào audit flow.task_completed."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _flow():
    spec = importlib.util.spec_from_file_location("services_flow_audit", ROOT / "services/flow/main.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["services_flow_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


flow = _flow()


@pytest.mark.asyncio
async def test_tim_dossier_id_tu_req_variables():
    """Trường hợp 1: ho_so_id có sẵn trong req.variables khi hoàn thành task."""
    task = {"id": "task-1", "processInstanceId": "proc-100"}
    existing_vars = {}
    req_vars = {"ho_so_id": "hs-uuid-001"}
    policy = {}

    dossier_id = await flow._tim_dossier_id_cho_task(
        task=task,
        existing_vars=existing_vars,
        req_variables=req_vars,
        tenant="phuong-a",
        policy=policy,
    )
    assert dossier_id == "hs-uuid-001"


@pytest.mark.asyncio
async def test_tim_dossier_id_tu_existing_vars():
    """Trường hợp 2: ho_so_id có sẵn trong biến quy trình của task từ Flowable."""
    task = {"id": "task-2", "processInstanceId": "proc-200"}
    existing_vars = {"ho_so_id": "hs-uuid-002", "buoc": "tham_dinh"}
    req_vars = {"ketQuaThamDinh": "DAT"}
    policy = {}

    dossier_id = await flow._tim_dossier_id_cho_task(
        task=task,
        existing_vars=existing_vars,
        req_variables=req_vars,
        tenant="phuong-a",
        policy=policy,
    )
    assert dossier_id == "hs-uuid-002"


@pytest.mark.asyncio
async def test_tim_dossier_id_tu_database_lookup():
    """Trường hợp 3: Biến không có, tra bảng cơ sở dữ liệu theo processInstanceId."""
    task = {"id": "task-3", "processInstanceId": "proc-300"}
    existing_vars = {}
    req_vars = {"ketLuan": "dat"}
    policy = {}

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = "hs-uuid-003"
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch("services_flow_audit.get_db_pool", return_value=mock_pool):
        dossier_id = await flow._tim_dossier_id_cho_task(
            task=task,
            existing_vars=existing_vars,
            req_variables=req_vars,
            tenant="phuong-a",
            policy=policy,
        )
    assert dossier_id == "hs-uuid-003"
    mock_conn.fetchval.assert_awaited_once()


@pytest.mark.asyncio
async def test_tim_dossier_id_khong_co_ho_so():
    """Trường hợp 4: Không có trong biến và không tìm thấy trong DB -> trả về None, không lỗi."""
    task = {"id": "task-4", "processInstanceId": "proc-unknown"}
    existing_vars = {}
    req_vars = {}
    policy = {}

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = None
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch("services_flow_audit.get_db_pool", return_value=mock_pool):
        dossier_id = await flow._tim_dossier_id_cho_task(
            task=task,
            existing_vars=existing_vars,
            req_variables=req_vars,
            tenant="phuong-a",
            policy=policy,
        )
    assert dossier_id is None


@pytest.mark.asyncio
async def test_tim_dossier_id_khong_co_proc_id_va_db_loi():
    """Trường hợp 5: Task không có processInstanceId hoặc DB lỗi -> an toàn trả về None."""
    task = {"id": "task-5"}  # Không có processInstanceId
    dossier_id = await flow._tim_dossier_id_cho_task(
        task=task,
        existing_vars={},
        req_variables={},
        tenant="phuong-a",
        policy={},
    )
    assert dossier_id is None

    # Khi DB throw exception: không raise HTTPException, chỉ trả về None
    task_with_proc = {"id": "task-6", "processInstanceId": "proc-err"}
    with patch("services_flow_audit.get_db_pool", side_effect=RuntimeError("DB pool error")):
        dossier_id = await flow._tim_dossier_id_cho_task(
            task=task_with_proc,
            existing_vars={},
            req_variables={},
            tenant="phuong-a",
            policy={},
        )
    assert dossier_id is None


def test_baseline_task_chua_gan_ho_so_ve_khong():
    """Dữ liệu mới có ho_so_id thì chỉ số task_hoan_thanh_chua_gan_ho_so về 0."""
    spec_dh = importlib.util.spec_from_file_location("dh_base_test", ROOT / "scripts/dh_baseline.py")
    mod_dh = importlib.util.module_from_spec(spec_dh)
    spec_dh.loader.exec_module(mod_dh)

    raw_moi = {
        "tong_ho_so": 5,
        "thao_tac_moi_ho_so": [2, 3, 4],
        "thao_tac_nguoi_dung": 9,
        "task_hoan_thanh": 10,
        "task_hoan_thanh_chua_gan_ho_so": 0,
    }
    h = mod_dh.tinh(raw_moi)["h"]
    assert h["task_hoan_thanh_chua_gan_ho_so"] == 0


@pytest.mark.asyncio
async def test_complete_task_audit_detail_co_ho_so():
    """Kiểm tra complete_task ghi đúng ho_so_id và process_instance_id vào audit detail."""
    mock_claims = MagicMock()
    mock_claims.tenant = "phuong-a"
    mock_claims.sub = "user-1"
    mock_claims.preferred_username = "canbo1"
    mock_claims.roles = ["app:cap-phep:tham-dinh"]

    task_data = {
        "id": "t-10",
        "tenantId": "phuong-a",
        "assignee": "user-1",
        "processInstanceId": "proc-999",
        "taskDefinitionKey": "taskThamDinh",
    }

    mock_resp_task = MagicMock()
    mock_resp_task.status_code = 200
    mock_resp_task.json.return_value = task_data

    mock_resp_vars = MagicMock()
    mock_resp_vars.status_code = 200
    mock_resp_vars.json.return_value = [{"name": "ho_so_id", "value": "hs-999"}]

    mock_resp_complete = MagicMock()
    mock_resp_complete.status_code = 200

    def mock_get(url):
        if "identitylinks" in url:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = []
            return resp
        elif "variables" in url:
            return mock_resp_vars
        return mock_resp_task

    mock_client = AsyncMock()
    mock_client.get.side_effect = mock_get
    mock_client.post.return_value = mock_resp_complete
    mock_client.__aenter__.return_value = mock_client

    mock_audit = AsyncMock()

    with patch("services_flow_audit.verify_jwt_token", return_value=mock_claims), \
         patch("services_flow_audit.get_flowable_client", return_value=mock_client), \
         patch("services_flow_audit.log_audit_event", mock_audit), \
         patch("services_flow_audit.get_flow_policies", return_value={"manager_roles": [], "task_variables": {}, "variable_roles": {}, "sod_rules": {}, "task_transitions": {}}):

        req = flow.CompleteTaskRequest(variables={"ketQuaThamDinh": "DAT"})
        await flow.complete_task("t-10", req, authorization="Bearer test-token")

        mock_audit.assert_awaited()
        # Tìm lệnh gọi log_audit_event cho flow.task_completed
        completed_call = [c for c in mock_audit.call_args_list if c.kwargs.get("action") == "flow.task_completed"]
        assert len(completed_call) == 1
        detail = completed_call[0].kwargs.get("detail")
        assert detail["process_instance_id"] == "proc-999"
        assert detail["ho_so_id"] == "hs-999"
        assert detail["variables"] == {"ketQuaThamDinh": "DAT"}


@pytest.mark.asyncio
async def test_complete_task_audit_detail_khong_co_ho_so():
    """Kiểm tra complete_task khi không tìm thấy hồ sơ: audit vẫn ghi, chỉ thiếu ho_so_id."""
    mock_claims = MagicMock()
    mock_claims.tenant = "phuong-a"
    mock_claims.sub = "user-2"
    mock_claims.preferred_username = "canbo2"
    mock_claims.roles = ["app:cap-phep:tham-dinh"]

    task_data = {
        "id": "t-11",
        "tenantId": "phuong-a",
        "assignee": "user-2",
        "processInstanceId": "proc-none",
        "taskDefinitionKey": "taskThamDinh",
    }

    mock_resp_task = MagicMock()
    mock_resp_task.status_code = 200
    mock_resp_task.json.return_value = task_data

    mock_resp_vars = MagicMock()
    mock_resp_vars.status_code = 200
    mock_resp_vars.json.return_value = []

    mock_resp_complete = MagicMock()
    mock_resp_complete.status_code = 200

    def mock_get(url):
        if "identitylinks" in url:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = []
            return resp
        elif "variables" in url:
            return mock_resp_vars
        return mock_resp_task

    mock_client = AsyncMock()
    mock_client.get.side_effect = mock_get
    mock_client.post.return_value = mock_resp_complete
    mock_client.__aenter__.return_value = mock_client

    mock_audit = AsyncMock()

    with patch("services_flow_audit.verify_jwt_token", return_value=mock_claims), \
         patch("services_flow_audit.get_flowable_client", return_value=mock_client), \
         patch("services_flow_audit.log_audit_event", mock_audit), \
         patch("services_flow_audit.get_db_pool", return_value=None), \
         patch("services_flow_audit.get_flow_policies", return_value={"manager_roles": [], "task_variables": {}, "variable_roles": {}, "sod_rules": {}, "task_transitions": {}}):

        req = flow.CompleteTaskRequest(variables={"ketQuaThamDinh": "DAT"})
        await flow.complete_task("t-11", req, authorization="Bearer test-token")

        mock_audit.assert_awaited()
        completed_call = [c for c in mock_audit.call_args_list if c.kwargs.get("action") == "flow.task_completed"]
        assert len(completed_call) == 1
        detail = completed_call[0].kwargs.get("detail")
        assert detail["process_instance_id"] == "proc-none"
        assert "ho_so_id" not in detail
        assert detail["variables"] == {"ketQuaThamDinh": "DAT"}


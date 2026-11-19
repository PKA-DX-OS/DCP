# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
import httpx
import secrets
import time
from fastapi import FastAPI, Header, HTTPException, status, Request, APIRouter, Query
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from dxos_core.middleware import setup_standard_service
from dxos_core.jwt import verify_jwt_token
from dxos_core.config import settings
from dxos_core.audit import log_audit_event
from dxos_core.db import get_db_pool, get_db_connection

logger = logging.getLogger("dxos.flow")

def _sign_request_body(sign_cfg: dict, doc_type: str, doc_payload: dict) -> dict:
    """Thân yêu cầu ký: gắn văn bản với đối tượng nghiệp vụ khai báo trong app.yaml (sign.object_type, sign.object_id_field)."""
    body = {"doc_type": doc_type, "data": doc_payload}
    obj_type = (sign_cfg or {}).get("object_type")
    id_field = (sign_cfg or {}).get("object_id_field")
    if obj_type and id_field and doc_payload.get(id_field):
        body["object_type"] = obj_type
        body["object_id"] = str(doc_payload[id_field])
    return body

app = FastAPI(title="DX-OS Workflow Façade Service", version="1.0.0")
setup_standard_service(app, "flow")

# Bộ lưu trữ thông tin client SSE kết nối thời gian thực (R-02: queue, tenant, sub, roles)
_SSE_CLIENTS: List[Dict[str, Any]] = []

# Bộ lưu trữ vé dùng một lần cho SSE (S-03)
_SSE_TICKETS: Dict[str, Dict[str, Any]] = {}


def _is_officer(roles: List[str], policy: Optional[Dict[str, Any]] = None) -> bool:
    """Xác định vai trò cán bộ công vụ / điều hành (R-02, S-02)."""
    roles_str = [str(r) for r in (roles or [])]
    submitter_roles = set((policy or {}).get("submitter_roles", [])) | {"citizen", "cong-dan"}
    staff_roles = set((policy or {}).get("staff_roles", []))

    if any(r in submitter_roles for r in roles_str):
        has_admin = any(any(adm in r for adm in ("admin", "service", "auditor")) for r in roles_str)
        if not has_admin:
            return False

    has_admin = any(any(adm in r for adm in ("admin", "service", "auditor")) for r in roles_str)
    if has_admin:
        return True

    return any(r.startswith("dx:") or r in staff_roles for r in roles_str)

# S-06: Danh sách vai trò hệ thống / mặc định cần loại trừ khi truy vấn candidateGroup
EXCLUDED_ROLES: Set[str] = {
    "default-roles-dxos",
    "offline_access",
    "uma_authorization",
    "account",
}

async def get_flow_policies() -> Dict[str, Any]:
    """Tải cấu hình flow_policies từ bảng core.app_policies theo hợp đồng ứng dụng (V2-08)."""
    try:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT policy_data
                    FROM core.app_policies
                    WHERE policy_type = 'flow_policies'
                    LIMIT 1
                    """
                )
                if row and row["policy_data"]:
                    return json.loads(row["policy_data"]) if isinstance(row["policy_data"], str) else row["policy_data"]
    except Exception as e:
        logger.warning(f"Lỗi khi đọc flow_policies từ DB: {e}")
    return {}


def parse_iso_duration(duration_str: str) -> timedelta:
    """Chuyển đổi chuỗi ISO-8601 duration (P3D, P2D, PT1M, PT30S, ...) sang timedelta."""
    if not duration_str:
        return timedelta(days=3)
    duration_str = str(duration_str).strip()
    pattern = re.compile(
        r"^P(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
    )
    match = pattern.match(duration_str)
    if not match:
        return timedelta(days=3)
    parts = {k: int(v) for k, v in match.groupdict().items() if v is not None}
    return timedelta(**parts)


def calculate_task_sla_iso(task_def: str, policy: dict, variables: dict = None) -> tuple[str, str]:
    """Tính toán hạn bước dạng ISO-8601 và duration theo SLA và biến môi trường test (P-04)."""
    sla_cfg = policy.get("sla", {}) if isinstance(policy, dict) else {}
    env_keys = [
        f"TEST_SLA_{task_def}",
        f"SLA_OVERRIDE_{task_def}",
        f"TEST_SLA_{task_def.upper()}",
        f"SLA_OVERRIDE_{task_def.upper()}",
        f"SLA_{task_def.upper()}",
        f"SLA_{task_def}",
    ]
    raw_duration = None
    for k in env_keys:
        val = os.getenv(k)
        if val:
            raw_duration = val
            break

    if not raw_duration and variables:
        test_overrides = variables.get("_test_sla") or variables.get("sla_overrides") or {}
        if isinstance(test_overrides, dict) and task_def in test_overrides:
            raw_duration = test_overrides[task_def]

    if not raw_duration:
        raw_duration = sla_cfg.get(task_def, "P3D")

    delta = parse_iso_duration(raw_duration)
    deadline = datetime.now(timezone.utc) + delta
    iso_str = deadline.strftime("%Y-%m-%dT%H:%M:%SZ")
    return iso_str, raw_duration


class FlowTimerRequest(BaseModel):
    process_instance_id: Optional[str] = None
    task_def: Optional[str] = None


class CompleteTaskRequest(BaseModel):
    variables: Dict[str, Any] = {}


class StartProcessRequest(BaseModel):
    process_key: str
    business_key: Optional[str] = None
    variables: Dict[str, Any] = {}


class RetryHookRequest(BaseModel):
    process_instance_id: str
    task_def: str


def get_flowable_client() -> httpx.AsyncClient:
    # O-05: Timeout kết nối ngắn (<= 3 giây) để trả 503 nhanh thay vì treo tới 504
    return httpx.AsyncClient(
        base_url=settings.flowable_url,
        auth=(settings.flowable_user, settings.flowable_password),
        timeout=3.0,
    )


@app.get("/api/v1/flow/tasks")
async def list_user_tasks(
    authorization: str = Header(...),
):
    """
    Lấy danh sách nhiệm vụ được giao cho người dùng hiện tại (theo tenant và vai trò).
    Fail-closed: Nếu Flowable không phản hồi trong 3s, trả 503 Service Unavailable.
    """
    claims = verify_jwt_token(authorization)
    tasks: List[Dict[str, Any]] = []
    seen_ids = set()

    # S-06: Lọc bỏ vai trò mặc định Keycloak, chỉ giữ lại vai trò nghiệp vụ thực tế
    business_roles = [r for r in claims.roles if r not in EXCLUDED_ROLES]

    try:
        async with get_flowable_client() as client:
            # 1. Truy vấn các task được giao trực tiếp cho người dùng (assignee = sub hoặc preferred_username)
            resp = await client.get(
                "/service/runtime/tasks",
                params={"tenantId": claims.tenant, "assignee": str(claims.sub), "size": 1000, "includeProcessVariables": "true"},
            )
            if resp.status_code == 200:
                for t in resp.json().get("data", []):
                    if t.get("tenantId") == claims.tenant and t["id"] not in seen_ids:
                        tasks.append(t)
                        seen_ids.add(t["id"])

            if claims.preferred_username:
                resp = await client.get(
                    "/service/runtime/tasks",
                    params={"tenantId": claims.tenant, "assignee": str(claims.preferred_username), "size": 1000, "includeProcessVariables": "true"},
                )
                if resp.status_code == 200:
                    for t in resp.json().get("data", []):
                        if t.get("tenantId") == claims.tenant and t["id"] not in seen_ids:
                            tasks.append(t)
                            seen_ids.add(t["id"])

            # 2. Truy vấn Flowable theo candidate groups của người dùng
            for role in business_roles:
                resp = await client.get(
                    "/service/runtime/tasks",
                    params={"tenantId": claims.tenant, "candidateGroup": role, "size": 1000, "includeProcessVariables": "true"},
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for t in data:
                        if t.get("tenantId") != claims.tenant:
                            continue
                        # Nếu task đã có assignee khác người dùng này, không hiển thị trong danh sách của họ
                        assignee = t.get("assignee")
                        if assignee and str(assignee) != str(claims.sub) and (not claims.preferred_username or str(assignee) != str(claims.preferred_username)):
                            continue
                        if t["id"] not in seen_ids:
                            tasks.append(t)
                            seen_ids.add(t["id"])
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": "Dịch vụ quy trình BPMN Flowable phản hồi quá hạn (timeout <= 3s)"},
        )
    except Exception as e:
        logger.error(f"Lỗi kết nối Flowable engine: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": f"Dịch vụ quy trình BPMN Flowable không sẵn sàng: {e}"},
        )

    # U-07: chỉ trả các biến quy trình app khai báo là cần cho giao diện (flow_policies.task_list_variables)
    policy = await get_flow_policies()
    visible_vars = set(policy.get("task_list_variables", []))
    for t in tasks:
        t["variables"] = [v for v in (t.get("variables") or []) if v.get("name") in visible_vars]

    return {"tasks": tasks, "count": len(tasks), "tenant": claims.tenant}


@app.get("/api/v1/flow/tasks/{task_id}")
async def get_task_detail(
    task_id: str,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    try:
        async with get_flowable_client() as client:
            resp = await client.get(f"/service/runtime/tasks/{task_id}")
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail={"loi": "Không tìm thấy nhiệm vụ"})

            task = resp.json()

            # F-33 / S-08: Kiểm tra cách ly tenant (Fail-Closed: tenant rỗng hoặc sai đều từ chối)
            is_admin = "dx:platform-admin" in claims.roles or "dx:service" in claims.roles
            task_tenant = task.get("tenantId")
            if not is_admin:
                if not task_tenant or task_tenant != claims.tenant:
                    await log_audit_event(
                        tenant=claims.tenant,
                        action="access.denied",
                        actor_sub=claims.sub,
                        object_type="task",
                        object_id=task_id,
                        detail={"loi": "Truy cập trái phép nhiệm vụ của tenant khác", "task_tenant": task_tenant},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={"loi": "Bạn không có quyền truy cập nhiệm vụ thuộc địa bàn khác"},
                    )

            # Lấy identitylinks để kiểm tra thẩm quyền xem nhiệm vụ
            links_resp = await client.get(f"/service/runtime/tasks/{task_id}/identitylinks")
            links = links_resp.json() if links_resp.status_code == 200 else []
            candidate_groups = [lnk.get("group") for lnk in links if lnk.get("type") == "candidate" and lnk.get("group")]

            task_assignee = task.get("assignee")
            is_assignee = bool(
                task_assignee and (
                    str(task_assignee) == str(claims.sub) or
                    (claims.preferred_username and str(task_assignee) == str(claims.preferred_username))
                )
            )
            is_candidate = any(g in claims.roles for g in candidate_groups)

            if not (is_admin or is_assignee or (not task_assignee and is_candidate)):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"loi": "Bạn không có quyền xem chi tiết nhiệm vụ này"},
                )

            # Lấy biến quy trình từ Flowable
            var_resp = await client.get(f"/service/runtime/tasks/{task_id}/variables")
            task["variables"] = var_resp.json() if var_resp.status_code == 200 else []
            return task
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": "Dịch vụ quy trình BPMN Flowable phản hồi quá hạn (timeout <= 3s)"},
        )
    except Exception as e:
        logger.error(f"Lỗi lấy chi tiết nhiệm vụ từ Flowable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": f"Lỗi kết nối Flowable: {e}"},
        )


@app.post("/api/v1/flow/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    req: CompleteTaskRequest,
    authorization: str = Header(...),
):
    """
    Hoàn thành nhiệm vụ công việc.
    Tuân thủ nguyên tắc Fail-Closed và phân tách nhiệm vụ (SoD).
    """
    claims = verify_jwt_token(authorization)
    is_admin = "dx:platform-admin" in claims.roles or "dx:service" in claims.roles
    policy = await get_flow_policies()
    allowed_task_vars = policy.get("task_variables", {})
    required_var_roles = policy.get("variable_roles", {})
    sod_rules = policy.get("sod_rules", {})
    sync_state_sql = policy.get("sync_state_sql")

    # 1. Lấy thông tin task và biến quy trình từ Flowable để xác thực quyền
    try:
        async with get_flowable_client() as client:
            task_resp = await client.get(f"/service/runtime/tasks/{task_id}")
            if task_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"loi": "Không tìm thấy nhiệm vụ cần hoàn thành"},
                )
            task = task_resp.json()

            # F-33 / S-08: Kiểm tra cách ly tenant (Fail-closed: tenant rỗng hoặc sai đều chặn)
            task_tenant = task.get("tenantId")
            if not is_admin:
                if not task_tenant or task_tenant != claims.tenant:
                    await log_audit_event(
                        tenant=claims.tenant,
                        action="access.denied",
                        actor_sub=claims.sub,
                        object_type="task",
                        object_id=task_id,
                        detail={"loi": "Cố gắng hoàn thành nhiệm vụ của tenant khác", "task_tenant": task_tenant},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={"loi": "Nhiệm vụ thuộc địa bàn khác, bạn không có quyền xử lý"},
                    )

            # S-08: Kiểm tra người gọi có thẩm quyền với task (assignee hoặc candidateGroup)
            links_resp = await client.get(f"/service/runtime/tasks/{task_id}/identitylinks")
            links = links_resp.json() if links_resp.status_code == 200 else []
            candidate_groups = [lnk.get("group") for lnk in links if lnk.get("type") == "candidate" and lnk.get("group")]

            task_assignee = task.get("assignee")
            is_assignee = bool(
                task_assignee and (
                    str(task_assignee) == str(claims.sub) or
                    (claims.preferred_username and str(task_assignee) == str(claims.preferred_username))
                )
            )
            is_candidate = any(g in claims.roles for g in candidate_groups)

            if not is_admin:
                if task_assignee:
                    if not is_assignee:
                        await log_audit_event(
                            tenant=claims.tenant,
                            action="access.denied",
                            actor_sub=claims.sub,
                            object_type="task",
                            object_id=task_id,
                            detail={"loi": "Nhiệm vụ đã được phân công cho người khác", "assignee": task_assignee},
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail={"loi": "Nhiệm vụ này đã được phân công cho cán bộ khác, bạn không có quyền xử lý"},
                        )
                else:
                    if not is_candidate:
                        await log_audit_event(
                            tenant=claims.tenant,
                            action="access.denied",
                            actor_sub=claims.sub,
                            object_type="task",
                            object_id=task_id,
                            detail={"loi": "Không thuộc nhóm ứng viên có thẩm quyền", "candidate_groups": candidate_groups},
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail={"loi": "Bạn không thuộc nhóm chức vụ được phân công xử lý nhiệm vụ này"},
                        )

            # Lấy biến quy trình từ Flowable (F-32: đọc từ DB Flowable, không tin dữ liệu client gửi)
            vars_resp = await client.get(f"/service/runtime/tasks/{task_id}/variables")
            existing_vars = {}
            if vars_resp.status_code == 200:
                for item in vars_resp.json():
                    existing_vars[item.get("name")] = item.get("value")

            submitter_var_names = policy.get(
                "submitter_var_names",
                ["submitter_sub", "object_owner_sub", "owner_sub"]
            )
            existing_submitter = None
            for var_name in submitter_var_names:
                val = existing_vars.get(var_name)
                if val:
                    existing_submitter = val
                    break

            owner_var_names = policy.get(
                "owner_var_names",
                ["submitter_sub", "object_owner_sub", "owner_sub", "initiator"]
            )
            existing_owner = existing_submitter
            if not existing_owner:
                for var_name in owner_var_names:
                    val = existing_vars.get(var_name)
                    if val:
                        existing_owner = val
                        break

            # F-32: Kiểm tra SoD từ biến lưu trữ trong Flowable
            # 1. Người nộp hồ sơ không được tham gia xử lý các tác vụ nội bộ (trừ các tác vụ dành cho người nộp như taskChoBoSung)
            task_def_key = task.get("taskDefinitionKey", "")
            submitter_tasks = policy.get("submitter_tasks", ["taskChoBoSung"])
            if (
                existing_submitter
                and (str(claims.sub) == str(existing_submitter) or (claims.preferred_username and str(claims.preferred_username) == str(existing_submitter)))
                and "dx:service" not in claims.roles
                and task_def_key not in submitter_tasks
            ):
                await log_audit_event(
                    tenant=claims.tenant,
                    action="sod.violation_prevented",
                    actor_sub=claims.sub,
                    object_type="task",
                    object_id=task_id,
                    detail={"loi": "Người nộp cố gắng tham gia xử lý hồ sơ của mình", "task": task_def_key},
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"loi": "Vi phạm quy tắc phân tách nhiệm vụ: Người nộp không thể tham gia xử lý/phê duyệt hồ sơ của chính mình!"},
                )

            # 2. Kiểm tra SoD theo sod_rules từ flow_policies (V2-08)
            sod_config = sod_rules.get(task_def_key, {})
            exclude_var_name = sod_config.get("exclude_variable")
            if exclude_var_name:
                excluded_sub = existing_vars.get(exclude_var_name)
                if excluded_sub and str(claims.sub) == str(excluded_sub) and "dx:service" not in claims.roles:
                    await log_audit_event(
                        tenant=claims.tenant,
                        action="sod.violation_prevented",
                        actor_sub=claims.sub,
                        object_type="task",
                        object_id=task_id,
                        detail={"loi": f"Vi phạm phân tách nhiệm vụ: Cán bộ '{claims.sub}' bị loại trừ bởi biến {exclude_var_name}"},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={"loi": "Vi phạm quy tắc phân tách nhiệm vụ: Cán bộ không thể tự mình phê duyệt!"},
                    )

            # S-08: Kiểm tra tính hợp lệ của biến gửi lên theo từng loại nhiệm vụ (V2-08)
            if task_def_key in allowed_task_vars and not is_admin:
                allowed = set(allowed_task_vars[task_def_key])
                invalid_vars = set(req.variables.keys()) - allowed
                if invalid_vars:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"loi": f"Các biến không được phép tại bước '{task_def_key}': {list(invalid_vars)}"},
                    )

            # Kiểm tra quyền đối với từng biến nhạy cảm (V2-08)
            for var_name in req.variables:
                req_roles = required_var_roles.get(var_name)
                if req_roles and not any(r in claims.roles for r in req_roles) and not is_admin:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={"loi": f"Bạn không có thẩm quyền gửi biến quy trình '{var_name}'"},
                    )

            # P-04: Xác định bước tiếp theo và cập nhật han_buoc_at trong quy trình
            task_transitions = policy.get("task_transitions", {})
            next_task_def = task_transitions.get(task_def_key)
            if next_task_def:
                next_han_buoc_iso, _ = calculate_task_sla_iso(next_task_def, policy, req.variables)
                req.variables["han_buoc_at"] = next_han_buoc_iso

            # 2. Gửi lệnh hoàn thành sang Flowable
            flowable_vars = [{"name": k, "value": v} for k, v in req.variables.items()]
            resp = await client.post(
                f"/service/runtime/tasks/{task_id}",
                json={"action": "complete", "variables": flowable_vars},
            )
            if resp.status_code not in (200, 204):
                logger.error(f"Flowable trả mã lỗi khi hoàn thành task: {resp.status_code} - {resp.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"loi": f"Lỗi từ hệ thống quy trình Flowable: HTTP {resp.status_code}"},
                )
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": "Dịch vụ quy trình BPMN Flowable phản hồi quá hạn (timeout <= 3s)"},
        )
    except Exception as e:
        logger.error(f"Lỗi giao tiếp Flowable khi hoàn thành task: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": f"Dịch vụ Flowable không sẵn sàng: {e}"},
        )

    # F-19: Chỉ ghi log audit khi Flowable đã xác nhận hoàn tất thành công
    await log_audit_event(
        tenant=claims.tenant,
        action="flow.task_completed",
        actor_sub=claims.sub,
        object_type="task",
        object_id=task_id,
        detail={"variables": req.variables},
    )

    # V2-08: Gọi hàm SQL đồng bộ trạng thái do ứng dụng đăng ký trong flow_policies
    proc_id = task.get("processInstanceId")
    task_def = task.get("taskDefinitionKey", "")

    if sync_state_sql and proc_id:
        try:
            pool = await get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    await conn.execute(
                        f"SELECT {sync_state_sql}($1, $2, $3::jsonb)",
                        proc_id,
                        task_def,
                        json.dumps(req.variables),
                    )
        except Exception as e:
            logger.error(f"Lỗi khi gọi hàm đồng bộ quy trình {sync_state_sql}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"loi": f"Lỗi cập nhật cơ sở dữ liệu quy trình: {e}"},
            )

    # Z-04, N-03: Hook ký số và hoàn tất sau khi task hoàn thành (on_task_complete)
    on_complete_hooks = policy.get("on_task_complete", {})
    if task_def in on_complete_hooks:
        hook_cfg = on_complete_hooks[task_def]
        when_clause = hook_cfg.get("when", {})
        # Kiểm tra điều kiện biến gửi lên
        is_matched = all(req.variables.get(k) == v for k, v in when_clause.items())
        if is_matched:
            pool = await get_db_pool()
            # P-02, Q-04: Kiểm tra guard_sql trước khi ký trong luồng complete_task
            guard_sql = hook_cfg.get("guard_sql")
            if guard_sql and pool:
                try:
                    async with pool.acquire() as conn:
                        raw_guard = await conn.fetchval(f"SELECT {guard_sql}($1)", proc_id)
                        guard_res = json.loads(raw_guard) if isinstance(raw_guard, str) else (raw_guard or {})
                        if not guard_res or guard_res.get("found") is False:
                            raise HTTPException(
                                status_code=status.HTTP_404_NOT_FOUND,
                                detail={"loi": "Không tìm thấy hồ sơ liên quan để ký duyệt", "ma_loi": "NOT_FOUND"},
                            )
                        if guard_res.get("tenant") != claims.tenant:
                            await log_audit_event(
                                tenant=claims.tenant,
                                action="flow.hook_complete_denied",
                                actor_sub=claims.sub,
                                object_type="process",
                                object_id=proc_id,
                                detail={"reason": "Tenant mismatch in guard_sql", "target_tenant": guard_res.get("tenant"), "task_def": task_def},
                            )
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail={"loi": "Bạn không có quyền thực hiện cho hồ sơ của phường khác", "ma_loi": "FORBIDDEN"},
                            )
                        if guard_res.get("trang_thai") != "CHO_KY":
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail={"loi": f"Trạng thái không hợp lệ để ký duyệt (hiện tại: {guard_res.get('trang_thai')})", "ma_loi": "CONFLICT"},
                            )
                        if guard_res.get("tham_quyen_ok") is False:
                            raise HTTPException(
                                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail={
                                    "loi": "Không xác định được thẩm quyền cấp phép theo Điều 53; không được ký duyệt",
                                    "ma_loi": "AUTHORITY_UNRESOLVED",
                                    "ly_do": guard_res.get("ly_do_tham_quyen"),
                                },
                            )
                except HTTPException:
                    raise
                except Exception as ge:
                    logger.error(f"Lỗi kiểm tra guard_sql {guard_sql} trong complete_task: {ge}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail={"loi": f"Lỗi kiểm tra guard_sql: {ge}"},
                    )

            sign_cfg = hook_cfg.get("sign")
            after_sql = hook_cfg.get("after_sql")
            signed_doc_id = None
            public_code = None
            hook_run_id = None

            if pool:
                try:
                    async with pool.acquire() as conn:
                        hook_run_id = await conn.fetchval(
                            """
                            INSERT INTO core.hook_runs (tenant, process_instance_id, task_def, status)
                            VALUES ($1, $2, $3, 'PENDING')
                            RETURNING id
                            """,
                            claims.tenant, proc_id, task_def,
                        )
                except Exception as he:
                    logger.warning(f"Lỗi khởi tạo hook_runs: {he}")

            if sign_cfg:
                doc_type = sign_cfg.get("doc_type")
                data_sql = sign_cfg.get("data_sql")
                doc_payload = {}

                # 1. Gọi data_sql qua pool dịch vụ để lấy nội dung dữ liệu văn bản
                if data_sql and pool:
                    try:
                        async with pool.acquire() as conn:
                            try:
                                raw_data = await conn.fetchval(f"SELECT {data_sql}($1, $2)", proc_id, claims.tenant)
                            except Exception:
                                raw_data = await conn.fetchval(f"SELECT {data_sql}($1)", proc_id)
                            if raw_data:
                                doc_payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                    except Exception as de:
                        logger.error(f"Lỗi khi thực thi data_sql {data_sql}: {de}")
                        if hook_run_id and pool:
                            try:
                                async with pool.acquire() as conn:
                                    await conn.execute("UPDATE core.hook_runs SET status = 'FAILED', error = $1, updated_at = now() WHERE id = $2", f"data_sql failed: {de}", hook_run_id)
                            except Exception as he:
                                logger.warning(f"Lỗi cập nhật hook_runs FAILED: {he}")
                        await log_audit_event(
                            tenant=claims.tenant,
                            action="flow.hook_failed",
                            actor_sub=claims.sub,
                            object_type="task",
                            object_id=task_id,
                            detail={"reason": f"data_sql failed: {de}", "task_def": task_def},
                        )
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail={"loi": f"Không thể trích xuất dữ liệu ký số: {de}"},
                        )

                # 2. Gọi POST http://doc-sign:8000/api/v1/docs/sign bằng chính Bearer token của lãnh đạo
                doc_sign_url = os.environ.get("DOC_SIGN_URL", "http://doc-sign:8000")
                try:
                    async with httpx.AsyncClient(timeout=8.0) as sign_client:
                        sign_resp = await sign_client.post(
                            f"{doc_sign_url}/api/v1/docs/sign",
                            headers={"Authorization": authorization},
                            json=_sign_request_body(sign_cfg, doc_type, doc_payload),
                        )
                        if sign_resp.status_code in (200, 201):
                            sign_data = sign_resp.json()
                            signed_doc_id = sign_data.get("doc_id")
                            public_code = sign_data.get("public_code")
                            if hook_run_id and pool:
                                try:
                                    async with pool.acquire() as conn:
                                        await conn.execute(
                                            """
                                            UPDATE core.hook_runs
                                            SET signed_doc_id = $1, public_code = $2, status = 'SIGNED', updated_at = now()
                                            WHERE id = $3
                                            """,
                                            uuid.UUID(str(signed_doc_id)), public_code, hook_run_id,
                                        )
                                except Exception as he:
                                    logger.warning(f"Lỗi cập nhật hook_runs SIGNED: {he}")
                        else:
                            logger.error(f"Dịch vụ doc-sign trả mã lỗi {sign_resp.status_code}: {sign_resp.text}")
                            if hook_run_id and pool:
                                try:
                                    async with pool.acquire() as conn:
                                        await conn.execute("UPDATE core.hook_runs SET status = 'FAILED', error = $1, updated_at = now() WHERE id = $2", f"doc-sign status {sign_resp.status_code}", hook_run_id)
                                except Exception as he:
                                    logger.warning(f"Lỗi cập nhật hook_runs FAILED: {he}")
                            await log_audit_event(
                                tenant=claims.tenant,
                                action="flow.hook_failed",
                                actor_sub=claims.sub,
                                object_type="task",
                                object_id=task_id,
                                detail={"reason": f"doc-sign status {sign_resp.status_code}", "task_def": task_def},
                            )
                            sign_err_body = {}
                            try:
                                sign_err_body = sign_resp.json()
                            except Exception as ex_json:
                                logger.debug("Không thể phân tích json lỗi doc-sign: %s", ex_json)
                            detail_obj = sign_err_body.get("detail") if isinstance(sign_err_body.get("detail"), dict) else {}
                            ma_loi = detail_obj.get("ma_loi") or sign_err_body.get("ma_loi")
                            if not ma_loi and "sealed" in sign_resp.text.lower():
                                ma_loi = "KMS_SEALED"
                            thong_bao_loi = detail_obj.get("loi") or sign_err_body.get("loi") or f"Dịch vụ ký số phản hồi lỗi HTTP {sign_resp.status_code}: {sign_resp.text}"
                            status_code_out = status.HTTP_503_SERVICE_UNAVAILABLE if sign_resp.status_code == 503 else status.HTTP_502_BAD_GATEWAY
                            raise HTTPException(
                                status_code=status_code_out,
                                detail={"loi": thong_bao_loi, "ma_loi": ma_loi or "DOC_SIGN_FAILED"},
                            )
                except HTTPException:
                    raise
                except Exception as se:
                    logger.error(f"Lỗi kết nối dịch vụ ký số doc-sign: {se}")
                    if hook_run_id and pool:
                        try:
                            async with pool.acquire() as conn:
                                await conn.execute("UPDATE core.hook_runs SET status = 'FAILED', error = $1, updated_at = now() WHERE id = $2", f"doc-sign connection error: {se}", hook_run_id)
                        except Exception as he:
                            logger.warning(f"Lỗi cập nhật hook_runs FAILED: {he}")
                    await log_audit_event(
                        tenant=claims.tenant,
                        action="flow.hook_failed",
                        actor_sub=claims.sub,
                        object_type="task",
                        object_id=task_id,
                        detail={"reason": f"doc-sign connection error: {se}", "task_def": task_def},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={"loi": f"Dịch vụ ký số không thể kết nối: {se}"},
                    )

            # 3. Gọi after_sql qua pool dịch vụ
            if after_sql and signed_doc_id:
                if pool:
                    try:
                        async with pool.acquire() as conn:
                            try:
                                await conn.execute(
                                    f"SELECT {after_sql}($1, $2::uuid, $3, $4)",
                                    proc_id,
                                    uuid.UUID(str(signed_doc_id)),
                                    public_code,
                                    claims.tenant,
                                )
                            except Exception:
                                await conn.execute(
                                    f"SELECT {after_sql}($1, $2::uuid, $3)",
                                    proc_id,
                                    uuid.UUID(str(signed_doc_id)),
                                    public_code,
                                )
                            if hook_run_id:
                                await conn.execute("UPDATE core.hook_runs SET status = 'COMPLETED', error = NULL, updated_at = now() WHERE id = $1", hook_run_id)
                    except Exception as ae:
                        logger.error(f"Lỗi khi thực thi after_sql {after_sql}: {ae}")
                        if hook_run_id:
                            try:
                                async with pool.acquire() as conn:
                                    await conn.execute("UPDATE core.hook_runs SET status = 'FAILED', error = $1, updated_at = now() WHERE id = $2", f"after_sql failed: {ae}", hook_run_id)
                            except Exception as he:
                                logger.warning(f"Lỗi cập nhật hook_runs FAILED: {he}")
                        await log_audit_event(
                            tenant=claims.tenant,
                            action="flow.hook_failed",
                            actor_sub=claims.sub,
                            object_type="task",
                            object_id=task_id,
                            detail={"reason": f"after_sql failed: {ae}", "task_def": task_def},
                        )
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail={"loi": f"Lỗi hoàn tất phát hành văn bản sau ký: {ae}"},
                        )

    # Z-10: Duyệt truy cập khẩn cấp qua RPC core_api.duyet_truy_cap_khan dưới claims của người duyệt
    if task_def == "taskPheDuyetTruyCapKhan":
        quyet_dinh = req.variables.get("quyetDinh", "dong_y")
        dong_y = (quyet_dinh == "dong_y")
        target_obj_type = req.variables.get("object_type", "record")
        target_object_id = req.variables.get("p_object_id") or req.variables.get("object_id")
        requester_sub = req.variables.get("requester_sub")

        # Lấy requester_sub và object_id từ biến quy trình Flowable nếu chưa có trong req
        if not requester_sub or not target_object_id:
            try:
                flowable_user = settings.flowable_user if hasattr(settings, "flowable_user") else os.environ.get("FLOWABLE_USER", "rest-admin")
                flowable_pass = settings.flowable_password if hasattr(settings, "flowable_password") else os.environ.get("FLOWABLE_PASSWORD", "")
                flowable_url = settings.flowable_url if hasattr(settings, "flowable_url") else os.environ.get("FLOWABLE_URL", "http://flowable:8080/flowable-rest")
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp_vars = await client.get(
                        f"{flowable_url}/service/runtime/process-instances/{proc_id}/variables",
                        auth=(flowable_user, flowable_pass),
                    )
                    if resp_vars.status_code == 200:
                        for item in resp_vars.json():
                            name = item.get("name")
                            val = item.get("value")
                            if name == "requester_sub":
                                requester_sub = val
                            elif name in ("object_id", "p_object_id"):
                                target_object_id = val
                            elif name == "object_type":
                                target_obj_type = val
            except Exception as fe:
                logger.warning(f"Không thể lấy biến quy trình từ Flowable: {fe}")

        if target_object_id and requester_sub:
            try:
                async with get_db_connection(claims) as conn:
                    await conn.execute(
                        """
                        SELECT core_api.duyet_truy_cap_khan($1, $2::uuid, $3, $4)
                        """,
                        target_obj_type,
                        uuid.UUID(str(target_object_id)),
                        requester_sub,
                        dong_y,
                    )
                    logger.info(f"Đã duyệt truy cập khẩn cấp qua RPC cho requester={requester_sub}, object={target_object_id}")
            except Exception as be:
                logger.error(f"Lỗi gọi core_api.duyet_truy_cap_khan: {be}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"loi": f"Lỗi xử lý duyệt truy cập khẩn cấp: {be}"},
                )

    # R-02: Xác định chủ thể sở hữu tiến trình để cô lập sự kiện SSE
    object_owner_sub = req.variables.get("object_owner_sub") or existing_owner or existing_submitter
    if not object_owner_sub and proc_id:
        try:
            async with get_flowable_client() as fl_c:
                fl_res = await fl_c.get(f"/service/runtime/process-instances/{proc_id}/variables")
                if fl_res.status_code == 200:
                    fl_vars = fl_res.json()
                    owner_var_names = set(policy.get(
                        "owner_var_names",
                        ["submitter_sub", "object_owner_sub", "owner_sub", "initiator"]
                    ))
                    for v in fl_vars:
                        if v.get("name") in owner_var_names:
                            object_owner_sub = v.get("value")
                            break
        except Exception as ex_vars:
            logger.debug("Không thể lấy biến quy trình từ Flowable: %s", ex_vars)

    # Thông báo SSE cho các client đang kết nối (R-02: cô lập theo phường và chủ thể)
    await notify_sse(claims.tenant, {
        "event": "task_completed",
        "task_id": task_id,
        "actor_sub": claims.sub,
        "task_def": task_def,
        "object_owner_sub": object_owner_sub,
    })

    return {"status": "success", "task_id": task_id}


@app.post("/api/v1/flow/processes/start")
@app.post("/api/v1/flow/process-instances")
async def start_process(
    req: StartProcessRequest,
    authorization: str = Header(...),
):
    claims = verify_jwt_token(authorization)
    flowable_vars = [{"name": k, "value": v} for k, v in req.variables.items()]
    flowable_vars.append({"name": "initiator", "value": claims.sub})
    flowable_vars.append({"name": "tenantId", "value": claims.tenant})

    # V2-08: Nạp các biến mặc định cho quy trình từ flow_policies nếu có
    policy = await get_flow_policies()
    default_vars = policy.get("default_process_variables", {}).get(req.process_key, {})
    var_names = {v["name"] for v in flowable_vars}
    for k, v in default_vars.items():
        if k not in var_names:
            flowable_vars.append({"name": k, "value": v})

    # P-04: Tính hạn bước cho bước đầu tiên theo SLA nếu có cấu hình trong flow_policies
    initial_task = policy.get("initial_tasks", {}).get(req.process_key) or policy.get("initial_task")
    if initial_task:
        han_buoc_iso, _ = calculate_task_sla_iso(initial_task, policy, req.variables)
        flowable_vars.append({"name": "han_buoc_at", "value": han_buoc_iso})

    try:
        async with get_flowable_client() as client:
            resp = await client.post(
                "/service/runtime/process-instances",
                json={
                    "processDefinitionKey": req.process_key,
                    "businessKey": req.business_key,
                    "variables": flowable_vars,
                    "tenantId": claims.tenant,
                },
            )
            if resp.status_code not in (200, 201):
                logger.error(f"Flowable từ chối khởi động quy trình: {resp.status_code} - {resp.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"loi": f"Lỗi từ Flowable khi khởi động quy trình: HTTP {resp.status_code}"},
                )
            proc_id = resp.json().get("id")
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": "Dịch vụ quy trình BPMN Flowable phản hồi quá hạn (timeout <= 3s)"},
        )
    except Exception as e:
        logger.error(f"Lỗi kết nối Flowable khi khởi động quy trình: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": f"Dịch vụ Flowable không sẵn sàng: {e}"},
        )

    # V2-08 / V3-10: Gọi hàm SQL đồng bộ trạng thái khi khởi động quy trình nếu app khai báo
    sync_state_sql = policy.get("sync_state_sql")
    if sync_state_sql and proc_id:
        try:
            pool = await get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    init_vars = dict(req.variables)
                    init_vars["business_key"] = req.business_key
                    init_vars["han_buoc_at"] = han_buoc_iso
                    await conn.execute(
                        f"SELECT {sync_state_sql}($1, $2, $3::jsonb)",
                        proc_id,
                        "process_started",
                        json.dumps(init_vars),
                    )
        except Exception as e:
            logger.error(f"Lỗi khi gọi hàm đồng bộ quy trình khi khởi tạo {sync_state_sql}: {e}")

    await log_audit_event(
        tenant=claims.tenant,
        action="flow.process_started",
        actor_sub=claims.sub,
        object_type="process",
        object_id=proc_id,
        detail={"process_key": req.process_key, "business_key": req.business_key},
    )

    biz_code = req.variables.get("maHoSo") or req.variables.get("code") or req.business_key
    await notify_sse(claims.tenant, {
        "event": "process_started",
        "process_id": proc_id,
        "process_key": req.process_key,
        "business_key": req.business_key,
        "business_code": biz_code,
        "actor_sub": claims.sub,
        "object_owner_sub": claims.sub,
    })

    return {"status": "started", "process_id": proc_id, "process_key": req.process_key}


@app.post("/api/v1/flow/hooks/retry")
async def retry_hook(
    req: RetryHookRequest,
    authorization: str = Header(...),
):
    """N-03, P-02: Thử lại hook quy trình khi doc-sign hoặc after_sql gặp sự cố."""
    claims = verify_jwt_token(authorization)
    policy = await get_flow_policies()
    on_complete_hooks = policy.get("on_task_complete", {})
    hook_cfg = on_complete_hooks.get(req.task_def)
    if not hook_cfg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"loi": f"Không tìm thấy cấu hình hook cho nhiệm vụ {req.task_def}"},
        )

    pool = await get_db_pool()
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": "Cơ sở dữ liệu không sẵn sàng"},
        )

    # 1. Kiểm tra vai trò ký số doc_signers trong core.app_policies
    sign_cfg = hook_cfg.get("sign")
    doc_type = sign_cfg.get("doc_type") if sign_cfg else None
    allowed_roles = set()
    if doc_type:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT policy_data FROM core.app_policies WHERE policy_type = 'doc_signers' AND policy_key = $1 LIMIT 1",
                doc_type,
            )
            if row and row["policy_data"]:
                pd = json.loads(row["policy_data"]) if isinstance(row["policy_data"], str) else row["policy_data"]
                allowed_roles.update(pd.get("sign_roles", []))
    if not allowed_roles:
        allowed_roles = {"dx:tenant-admin", "dx:platform-admin"}

    user_roles = set(claims.roles)
    if not (user_roles & allowed_roles or "dx:platform-admin" in user_roles):
        await log_audit_event(
            tenant=claims.tenant,
            action="flow.hook_retry_denied",
            actor_sub=claims.sub,
            object_type="process",
            object_id=req.process_instance_id,
            detail={"reason": "Caller lacks sign_roles for retry", "task_def": req.task_def},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Bạn không có quyền thực hiện ký lại cho văn bản này", "ma_loi": "FORBIDDEN"},
        )

    # 2. P-02: Kiểm tra guard_sql
    guard_sql = hook_cfg.get("guard_sql")
    if guard_sql:
        try:
            async with pool.acquire() as conn:
                raw_guard = await conn.fetchval(f"SELECT {guard_sql}($1)", req.process_instance_id)
                guard_res = json.loads(raw_guard) if isinstance(raw_guard, str) else (raw_guard or {})
                if not guard_res or guard_res.get("found") is False:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail={"loi": "Không tìm thấy hồ sơ liên quan để ký lại", "ma_loi": "NOT_FOUND"},
                    )
                if guard_res.get("tenant") != claims.tenant:
                    await log_audit_event(
                        tenant=claims.tenant,
                        action="flow.hook_retry_denied",
                        actor_sub=claims.sub,
                        object_type="process",
                        object_id=req.process_instance_id,
                        detail={"reason": "Tenant mismatch in guard_sql", "target_tenant": guard_res.get("tenant"), "task_def": req.task_def},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={"loi": "Bạn không có quyền ký lại hồ sơ của phường khác", "ma_loi": "FORBIDDEN"},
                    )
                if guard_res.get("trang_thai") != "CHO_KY":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"loi": f"Trạng thái hồ sơ không hợp lệ để ký lại (hiện tại: {guard_res.get('trang_thai')})", "ma_loi": "CONFLICT"},
                    )
                if guard_res.get("tham_quyen_ok") is False:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "loi": "Không xác định được thẩm quyền cấp phép theo Điều 53; không được ký lại",
                            "ma_loi": "AUTHORITY_UNRESOLVED",
                            "ly_do": guard_res.get("ly_do_tham_quyen"),
                        },
                    )
        except HTTPException:
            raise
        except Exception as ge:
            logger.error(f"Lỗi kiểm tra guard_sql {guard_sql}: {ge}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"loi": f"Lỗi kiểm tra guard_sql: {ge}"})

    # 3. P-02: Tìm vết chạy hook_runs trước đó (không tự tạo hook_runs mới nếu chưa có)
    hook_run_id = None
    signed_doc_id = None
    public_code = None

    async with pool.acquire() as conn:
        hook_row = await conn.fetchrow(
            """
            SELECT id, signed_doc_id, public_code, status
            FROM core.hook_runs
            WHERE tenant = $1 AND process_instance_id = $2 AND task_def = $3
            ORDER BY created_at DESC
            LIMIT 1
            """,
            claims.tenant, req.process_instance_id, req.task_def,
        )
        if not hook_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"loi": "Không tìm thấy phiên chạy hook trước đó cho quy trình này", "ma_loi": "HOOK_RUN_NOT_FOUND"},
            )
        hook_run_id = hook_row["id"]
        if hook_row["signed_doc_id"]:
            signed_doc_id = hook_row["signed_doc_id"]
            public_code = hook_row["public_code"]

    # 4. Ký số nếu chưa có signed_doc_id
    if not signed_doc_id and sign_cfg:
        data_sql = sign_cfg.get("data_sql")
        doc_payload = {}
        if data_sql:
            try:
                async with pool.acquire() as conn:
                    try:
                        raw_data = await conn.fetchval(f"SELECT {data_sql}($1, $2)", req.process_instance_id, claims.tenant)
                    except Exception:
                        raw_data = await conn.fetchval(f"SELECT {data_sql}($1)", req.process_instance_id)
                    if raw_data:
                        doc_payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            except Exception as de:
                logger.error(f"Lỗi retry khi trích xuất dữ liệu ký {data_sql}: {de}")
                if hook_run_id:
                    async with pool.acquire() as conn:
                        await conn.execute("UPDATE core.hook_runs SET status = 'FAILED', error = $1, updated_at = now() WHERE id = $2", str(de), hook_run_id)
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"loi": f"Không thể trích xuất dữ liệu ký: {de}"})

        doc_sign_url = os.environ.get("DOC_SIGN_URL", "http://doc-sign:8000")
        try:
            async with httpx.AsyncClient(timeout=8.0) as sign_client:
                sign_resp = await sign_client.post(
                    f"{doc_sign_url}/api/v1/docs/sign",
                    headers={"Authorization": authorization},
                    json=_sign_request_body(sign_cfg, doc_type, doc_payload),
                )
                if sign_resp.status_code in (200, 201):
                    sign_data = sign_resp.json()
                    signed_doc_id = sign_data.get("doc_id")
                    public_code = sign_data.get("public_code")
                    if hook_run_id:
                        async with pool.acquire() as conn:
                            await conn.execute(
                                """
                                UPDATE core.hook_runs
                                SET signed_doc_id = $1, public_code = $2, status = 'SIGNED', updated_at = now()
                                WHERE id = $3
                                """,
                                uuid.UUID(str(signed_doc_id)), public_code, hook_run_id,
                            )
                else:
                    if hook_run_id:
                        async with pool.acquire() as conn:
                            await conn.execute("UPDATE core.hook_runs SET status = 'FAILED', error = $1, updated_at = now() WHERE id = $2", f"doc-sign status {sign_resp.status_code}", hook_run_id)
                    sign_err_body = {}
                    try:
                        sign_err_body = sign_resp.json()
                    except Exception as ex_json2:
                        logger.debug("Không thể phân tích json lỗi doc-sign khi retry: %s", ex_json2)
                    detail_obj = sign_err_body.get("detail") if isinstance(sign_err_body.get("detail"), dict) else {}
                    ma_loi = detail_obj.get("ma_loi") or sign_err_body.get("ma_loi")
                    if not ma_loi and "sealed" in sign_resp.text.lower():
                        ma_loi = "KMS_SEALED"
                    thong_bao_loi = detail_obj.get("loi") or sign_err_body.get("loi") or f"Dịch vụ ký số lỗi HTTP {sign_resp.status_code}: {sign_resp.text}"
                    status_code_out = status.HTTP_503_SERVICE_UNAVAILABLE if sign_resp.status_code == 503 else status.HTTP_502_BAD_GATEWAY
                    raise HTTPException(status_code=status_code_out, detail={"loi": thong_bao_loi, "ma_loi": ma_loi or "DOC_SIGN_FAILED"})
        except HTTPException:
            raise
        except Exception as se:
            if hook_run_id:
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE core.hook_runs SET status = 'FAILED', error = $1, updated_at = now() WHERE id = $2", f"doc-sign connection error: {se}", hook_run_id)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"loi": f"Không thể kết nối doc-sign: {se}"})

    # 5. Thực thi after_sql
    after_sql = hook_cfg.get("after_sql")
    if after_sql and signed_doc_id:
        try:
            async with pool.acquire() as conn:
                try:
                    await conn.execute(
                        f"SELECT {after_sql}($1, $2::uuid, $3, $4)",
                        req.process_instance_id,
                        uuid.UUID(str(signed_doc_id)),
                        public_code,
                        claims.tenant,
                    )
                except Exception:
                    await conn.execute(
                        f"SELECT {after_sql}($1, $2::uuid, $3)",
                        req.process_instance_id,
                        uuid.UUID(str(signed_doc_id)),
                        public_code,
                    )
        except Exception as ae:
            logger.error(f"Lỗi retry after_sql {after_sql}: {ae}")
            if hook_run_id:
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE core.hook_runs SET status = 'FAILED', error = $1, updated_at = now() WHERE id = $2", f"after_sql failed: {ae}", hook_run_id)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"loi": f"Lỗi hoàn tất phát hành văn bản sau ký: {ae}"})

    # 6. Cập nhật hook_runs sang COMPLETED và ghi audit
    if hook_run_id:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE core.hook_runs SET status = 'COMPLETED', error = NULL, updated_at = now() WHERE id = $1",
                hook_run_id,
            )

    await log_audit_event(
        tenant=claims.tenant,
        action="flow.hook_retry",
        actor_sub=claims.sub,
        object_type="process",
        object_id=req.process_instance_id,
        detail={"task_def": req.task_def, "signed_doc_id": str(signed_doc_id) if signed_doc_id else None},
    )

    return {
        "status": "success",
        "process_instance_id": req.process_instance_id,
        "task_def": req.task_def,
        "signed_doc_id": str(signed_doc_id) if signed_doc_id else None,
        "public_code": public_code,
    }


# Router nội bộ dành cho các tiến trình hệ thống nội bộ gọi trực tiếp (Q-01)
# APISIX không định tuyến tới /internal/*
internal_router = APIRouter(prefix="/internal", tags=["Internal"])


@internal_router.post("/timer")
async def handle_flow_timer(
    request: Request,
    req: Optional[FlowTimerRequest] = None,
    process_instance_id: Optional[str] = None,
    task_def: Optional[str] = None,
):
    """Q-01: Xử lý sự kiện boundary timer quá hạn từ BPMN Flowable HTTP service task qua cổng nội bộ."""
    # 1. Xác thực header X-DXOS-Internal-Token
    token_header = request.headers.get("X-DXOS-Internal-Token")
    expected_token = os.getenv("FLOW_INTERNAL_TOKEN")
    if not expected_token:
        for p in [Path("/app/secrets/flow_internal_token"), Path("secrets/flow_internal_token")]:
            if p.exists():
                try:
                    expected_token = p.read_text(encoding="utf-8").strip()
                    break
                except Exception as read_err:
                    logger.debug("Không thể đọc secrets/flow_internal_token: %s", read_err)

    if not token_header or not expected_token or not secrets.compare_digest(token_header, expected_token):
        logger.warning("Truy cập /internal/timer bị từ chối: thiếu hoặc sai X-DXOS-Internal-Token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"loi": "Yêu cầu token nội bộ hợp lệ", "ma_loi": "FORBIDDEN"},
        )

    proc_id = (req.process_instance_id if req and req.process_instance_id else None) or process_instance_id
    t_def = (req.task_def if req and req.task_def else None) or task_def

    if not proc_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"loi": "Thiếu process_instance_id cho sự kiện timer"},
        )

    # 2. Đối chiếu sự kiện với Flowable REST
    proc_tenant = None
    try:
        async with get_flowable_client() as client:
            resp = await client.get(f"/service/runtime/process-instances/{proc_id}")
            if resp.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"loi": f"Quy trình {proc_id} không tồn tại trong Flowable", "ma_loi": "NOT_FOUND"},
                )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"loi": f"Lỗi truy vấn Flowable: {resp.status_code}"},
                )
            proc_data = resp.json()
            if proc_data.get("ended"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"loi": f"Quy trình {proc_id} đã kết thúc", "ma_loi": "NOT_FOUND"},
                )
            proc_tenant = proc_data.get("tenantId")
    except HTTPException:
        raise
    except Exception as fe:
        logger.error(f"Lỗi kết nối Flowable khi xác thực timer: {fe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": f"Flowable không khả dụng: {fe}"},
        )

    # 3. Lấy policy và thực thi hook on_timer
    policy = await get_flow_policies()
    on_timer = policy.get("on_timer")
    if not on_timer:
        logger.warning(f"Không có cấu hình on_timer trong flow_policies cho tiến trình {proc_id}")
        return {"status": "ignored", "reason": "no_on_timer_configured"}

    pool = await get_db_pool()
    if not pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"loi": "Cơ sở dữ liệu không khả dụng"},
        )

    try:
        async with pool.acquire() as conn:
            raw_res = await conn.fetchval(f"SELECT {on_timer}($1, $2, $3)", proc_id, t_def or "", proc_tenant)
            res = json.loads(raw_res) if isinstance(raw_res, str) else (raw_res or {})
            if res.get("reason") == "not_found" or str(res.get("reason", "")).endswith("_not_found"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"loi": "Không tìm thấy bản ghi quy trình hoặc tenant không khớp", "ma_loi": "NOT_FOUND"},
                )
            logger.info(f"Đã xử lý timer quá hạn cho quy trình {proc_id} (task={t_def}, tenant={proc_tenant}): {res}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lỗi khi thực thi hook timer {on_timer}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"loi": f"Lỗi thực thi timer hook: {e}"},
        )

    return {"status": "ok", "process_id": proc_id, "task_def": t_def, "result": res}


app.include_router(internal_router)


async def notify_sse(tenant: str, payload: Dict[str, Any]):
    """Đẩy thông báo thời gian thực có cô lập đa phường và bảo mật chủ thể (R-02, S-02)."""
    event_owner_sub = payload.get("object_owner_sub")
    try:
        policy = await get_flow_policies()
    except Exception:
        policy = {}
    for client in list(_SSE_CLIENTS):
        try:
            client_tenant = client.get("tenant")
            client_roles = client.get("roles", [])

            # 1. Chỉ gửi tới client cùng phường (hoặc platform-admin)
            if client_tenant != tenant and "dx:platform-admin" not in client_roles:
                continue

            client_is_officer = _is_officer(client_roles, policy)

            # 2. Với vai không phải cán bộ, chỉ gửi sự kiện liên quan tới hồ sơ của chính họ
            if not client_is_officer:
                client_sub = str(client.get("sub", ""))
                client_username = str(client.get("username", ""))
                matches_owner = (
                    event_owner_sub
                    and (str(event_owner_sub) == client_sub or (client_username and str(event_owner_sub) == client_username))
                )
                if not matches_owner:
                    continue

            # 3. Bỏ actor_sub khỏi payload gửi tới người không phải cán bộ
            client_payload = dict(payload)
            client_payload["tenant"] = tenant
            if not client_is_officer:
                client_payload.pop("actor_sub", None)

            message = json.dumps(client_payload, ensure_ascii=False)
            await client["queue"].put(message)
        except Exception as e:
            logger.debug(f"Lỗi gửi tin SSE tới client: {e}")


@app.post("/api/v1/events/ticket")
async def create_sse_ticket(
    authorization: Optional[str] = Header(None),
):
    """
    Tạo vé dùng một lần cho kết nối SSE (thời hạn 30 giây) (S-03).
    Loại bỏ việc truyền Bearer token trực tiếp trong query string.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"loi": "Yêu cầu mã xác thực Bearer token để tạo vé SSE"},
        )
    claims = verify_jwt_token(authorization)
    ticket_id = secrets.token_urlsafe(32)
    now = time.time()
    _SSE_TICKETS[ticket_id] = {
        "tenant": claims.tenant,
        "sub": claims.sub,
        "username": getattr(claims, "preferred_username", None),
        "roles": claims.roles or [],
        "expires_at": now + 30.0,
    }
    # Dọn dẹp vé hết hạn
    for tid in list(_SSE_TICKETS.keys()):
        if _SSE_TICKETS[tid]["expires_at"] < now:
            _SSE_TICKETS.pop(tid, None)

    return {"ticket": ticket_id, "expires_in": 30}


@app.get("/api/v1/events")
async def sse_events(
    request: Request,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    ticket: Optional[str] = Query(None),
):
    """
    Luồng sự kiện thời gian thực đẩy qua Server-Sent Events (SSE) (R-02, S-03).
    Xác thực qua JWT Keycloak (Header Authorization hoặc vé dùng một lần ?ticket=).
    (T-05) Từ chối token qua query string để ngăn rò rỉ JWT trong URL và access log.
    """
    if token is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"loi": "Không chấp nhận token qua tham số URL, vui lòng dùng ticket hoặc header Authorization"},
        )

    tenant: Optional[str] = None
    sub: Optional[str] = None
    username: Optional[str] = None
    roles: List[str] = []

    if ticket:
        ticket_data = _SSE_TICKETS.pop(ticket, None)
        if not ticket_data or ticket_data["expires_at"] < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"loi": "Vé SSE không hợp lệ hoặc đã hết hạn"},
            )
        tenant = ticket_data["tenant"]
        sub = ticket_data["sub"]
        username = ticket_data.get("username")
        roles = ticket_data["roles"]
    else:
        auth_header = authorization or request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"loi": "Yêu cầu mã xác thực Bearer token hoặc vé SSE"},
            )

        claims = verify_jwt_token(auth_header)
        tenant = claims.tenant
        sub = claims.sub
        username = getattr(claims, "preferred_username", None)
        roles = claims.roles or []

    queue: asyncio.Queue = asyncio.Queue()
    client_entry = {
        "queue": queue,
        "tenant": tenant,
        "sub": sub,
        "username": username,
        "roles": roles,
    }
    _SSE_CLIENTS.append(client_entry)

    async def event_generator():
        try:
            yield {"event": "connected", "data": "DX-OS SSE Event Stream Connected"}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=10.0)
                    yield {"event": "notification", "data": data}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "heartbeat"}
        finally:
            if client_entry in _SSE_CLIENTS:
                _SSE_CLIENTS.remove(client_entry)

    return EventSourceResponse(event_generator())

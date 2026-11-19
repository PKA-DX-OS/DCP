// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { FlowTask } from "../types";
import { apiJson } from "./client";

export async function fetchTasks(token: string): Promise<FlowTask[]> {
  const data = await apiJson<{ tasks?: FlowTask[] }>("/flow/tasks", { token }, "Lỗi tải danh sách nhiệm vụ");
  return data?.tasks || [];
}

export async function completeTask(token: string, taskId: string, variables: Record<string, any>): Promise<any> {
  return apiJson(
    `/flow/tasks/${encodeURIComponent(taskId)}/complete`,
    { token, method: "POST", body: { variables } },
    "Lỗi hoàn thành nhiệm vụ",
  );
}

export async function fetchOfficers(token: string, vai = "tham-dinh"): Promise<any[]> {
  return apiJson<any[]>(
    "/rest/rpc/ds_can_bo",
    { token, method: "POST", body: { p_vai: vai } },
    "Lỗi tải danh sách cán bộ",
  );
}

export async function assignTask(
  token: string,
  taskId: string,
  userSub: string,
  reason = "",
): Promise<any> {
  return apiJson(
    `/flow/tasks/${encodeURIComponent(taskId)}/assign`,
    { token, method: "POST", body: { user_sub: userSub, reason } },
    "Lỗi phân công lại việc",
  );
}

export async function remindTask(token: string, taskId: string, message = ""): Promise<any> {
  return apiJson(
    `/flow/tasks/${encodeURIComponent(taskId)}/remind`,
    { token, method: "POST", body: { message } },
    "Lỗi gửi nhắc việc",
  );
}

export async function fetchEscalations(token: string, windowHours = 24): Promise<any> {
  return apiJson<any>(
    `/flow/escalations?window_hours=${windowHours}`,
    { token },
    "Lỗi tải danh sách quá hạn",
  );
}

export async function startWorkflow(token: string, processKey: string, businessKey: string, variables: Record<string, any>): Promise<any> {
  return apiJson(
    "/flow/processes/start",
    { token, method: "POST", body: { process_key: processKey, business_key: businessKey, variables } },
    "Lỗi khởi động quy trình",
  );
}

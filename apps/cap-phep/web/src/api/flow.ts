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

export async function startWorkflow(token: string, processKey: string, businessKey: string, variables: Record<string, any>): Promise<any> {
  return apiJson(
    "/flow/processes/start",
    { token, method: "POST", body: { process_key: processKey, business_key: businessKey, variables } },
    "Lỗi khởi động quy trình",
  );
}

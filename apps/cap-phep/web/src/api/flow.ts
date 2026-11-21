// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { FlowTask } from "../types";
import { apiJson } from "./client";

/**
 * Mở một hồ sơ, thanh hành động, phần quy hoạch và phần nghiệm thu cùng cần danh sách việc. Gộp các
 * lần gọi trùng trong TASKS_TTL_MS thành một request; bỏ bộ nhớ đệm khi việc thay đổi.
 */
const TASKS_TTL_MS = 2000;
let tasksCache: { token: string; at: number; promise: Promise<FlowTask[]> } | null = null;

export function invalidateTasks(): void {
  tasksCache = null;
}

if (typeof window !== "undefined") {
  window.addEventListener("dxos:tasks-changed", invalidateTasks);
}

export async function fetchTasks(token: string): Promise<FlowTask[]> {
  const now = Date.now();
  if (tasksCache && tasksCache.token === token && now - tasksCache.at < TASKS_TTL_MS) {
    return tasksCache.promise;
  }
  const promise = apiJson<{ tasks?: FlowTask[] }>("/flow/tasks", { token }, "Lỗi tải danh sách nhiệm vụ").then(
    (data) => data?.tasks || [],
  );
  tasksCache = { token, at: now, promise };
  promise.catch(() => {
    if (tasksCache?.promise === promise) tasksCache = null;
  });
  return promise;
}

export async function completeTask(token: string, taskId: string, variables: Record<string, any>): Promise<any> {
  invalidateTasks();
  try {
    return await apiJson(
      `/flow/tasks/${encodeURIComponent(taskId)}/complete`,
      { token, method: "POST", body: { variables } },
      "Lỗi hoàn thành nhiệm vụ",
    );
  } finally {
    invalidateTasks();
  }
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
  invalidateTasks();
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

export interface WorkloadItem {
  user_sub: string;
  ho_ten?: string | null;
  so_ho_so_duoc_giao: number;
  dang_xu_ly: number;
}

/** Tải việc theo cán bộ để gợi ý phân công. */
export async function fetchWorkload(token: string): Promise<WorkloadItem[]> {
  const data = await apiJson<{ items?: WorkloadItem[] }>(
    "/metrics/workload",
    { token, timeoutMs: 8_000, retries: 0 },
    "Lỗi tải tải việc cán bộ",
  );
  return data?.items || [];
}

export async function fetchEscalations(token: string, windowHours = 24): Promise<any> {
  return apiJson<any>(
    `/flow/escalations?window_hours=${windowHours}`,
    { token },
    "Lỗi tải danh sách quá hạn",
  );
}

export async function startWorkflow(token: string, processKey: string, businessKey: string, variables: Record<string, any>): Promise<any> {
  invalidateTasks();
  return apiJson(
    "/flow/processes/start",
    { token, method: "POST", body: { process_key: processKey, business_key: businessKey, variables } },
    "Lỗi khởi động quy trình",
  );
}

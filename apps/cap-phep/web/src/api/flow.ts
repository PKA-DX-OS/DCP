// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

export async function fetchTasks(token: string): Promise<any[]> {
  const resp = await fetch("/api/v1/flow/tasks", {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  });
  if (!resp.ok) {
    if (resp.status === 401) {
      throw new Error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
    }
    throw new Error(`Lỗi tải danh sách nhiệm vụ: HTTP ${resp.status}`);
  }
  const data = await resp.json();
  return data.tasks || [];
}

export async function completeTask(token: string, taskId: string, variables: Record<string, any>): Promise<any> {
  const resp = await fetch(`/api/v1/flow/tasks/${taskId}/complete`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ variables }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail?.loi || `Lỗi hoàn thành nhiệm vụ: HTTP ${resp.status}`);
  }
  return await resp.json();
}

export async function startWorkflow(token: string, processKey: string, businessKey: string, variables: Record<string, any>): Promise<any> {
  const resp = await fetch("/api/v1/flow/processes/start", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      process_key: processKey,
      business_key: businessKey,
      variables,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail?.loi || `Lỗi khởi động quy trình: HTTP ${resp.status}`);
  }
  return await resp.json();
}

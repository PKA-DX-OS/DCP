// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

export async function fetchCongTrinh(token: string): Promise<any[]> {
  let resp = await fetch("/api/v1/rest/v_cong_trinh?order=created_at.desc", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!resp.ok) {
    resp = await fetch("/api/v1/rest/cong_trinh?order=created_at.desc", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  }
  if (!resp.ok) {
    return [];
  }
  return await resp.json();
}

export async function fetchPhieuKiemTra(token: string): Promise<any[]> {
  let resp = await fetch("/api/v1/rest/v_phieu_kiem_tra?order=created_at.desc", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!resp.ok) {
    resp = await fetch("/api/v1/rest/phieu_kiem_tra?order=created_at.desc", {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  }
  if (!resp.ok) {
    return [];
  }
  return await resp.json();
}

export async function createInspection(
  token: string,
  congTrinhId: string,
  ghiChu?: string
): Promise<any> {
  const resp = await fetch("/api/v1/rest/rpc/lap_phieu_kiem_tra", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      p_cong_trinh_id: congTrinhId,
      p_ghi_chu: ghiChu || "Kiểm tra chủ động hiện trường",
    }),
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(errText);
  }
  return await resp.json();
}

export async function triggerDemoSensor(
  token: string,
  maCongTrinh: string,
  laeqDba: number = 86.5
): Promise<any> {
  const resp = await fetch("/api/v1/ingest/demo-sensor", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      site_id: maCongTrinh,
      metric: "laeq_dba",
      value: laeqDba,
    }),
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(errText);
  }
  return await resp.json();
}

export async function fetchSensorAlerts(token: string): Promise<any[]> {
  const resp = await fetch("/api/v1/rest/canh_bao_cam_bien?order=created_at.desc", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!resp.ok) {
    return [];
  }
  return await resp.json();
}

// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import "@fontsource/inter/400.css";
import "@fontsource/inter/600.css";
import "./styles.css";
import { canViewDashboard, getUser, login, logout, readRoles } from "./auth";
import { ApiError, apiGet } from "./api";
import { dinhDangGiaTri, formatThoiDiem, nhanChiSo } from "./utils/metrics";

interface MetricItem {
  code: string;
  name?: string;
  unit?: string;
  value: number | null;
  error?: string;
}

interface MetricsResponse {
  tenant: string;
  computed_at: string;
  metrics: MetricItem[];
}

const root = document.getElementById("app");
if (!root) throw new Error("Thiếu phần tử #app");

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => {
    const map: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return map[c];
  });
}

function renderMessage(title: string, body: string, actionLabel?: string, actionId?: string): void {
  const button = actionLabel && actionId
    ? `<button id="${actionId}" class="mt-4 rounded bg-slate-800 px-4 py-2 text-white">${escapeHtml(actionLabel)}</button>`
    : "";
  root!.innerHTML = `<div class="rounded-lg bg-white p-6 shadow">
    <h1 class="text-xl font-semibold">${escapeHtml(title)}</h1>
    <p class="mt-2 text-slate-600">${escapeHtml(body)}</p>${button}</div>`;
}

async function renderDashboard(): Promise<void> {
  root!.innerHTML = `<p class="text-slate-500">Đang tải chỉ số...</p>`;
  try {
    const data = await apiGet<MetricsResponse>("/metrics");
    const cards = data.metrics
      .map((m) => `<div class="rounded-lg bg-white p-4 shadow">
        <div class="text-sm text-slate-500">${escapeHtml(nhanChiSo(m.code))}</div>
        <div class="mt-1 text-2xl font-semibold">${escapeHtml(dinhDangGiaTri(m))}</div>
        ${m.error ? `<div class="mt-1 text-xs text-amber-700">Không có số liệu (${escapeHtml(m.error)})</div>` : ""}
      </div>`)
      .join("");
    root!.innerHTML = `<header class="mb-4 flex items-center justify-between">
        <h1 class="text-xl font-semibold">Bảng điều hành lãnh đạo</h1>
        <button id="btn-logout" class="text-sm text-slate-600 underline">Đăng xuất</button>
      </header>
      <p class="mb-4 text-sm text-slate-500">Thời điểm tính: ${escapeHtml(formatThoiDiem(data.computed_at))}</p>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">${cards}</div>`;
    document.getElementById("btn-logout")?.addEventListener("click", () => void logout());
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return;
    if (e instanceof ApiError && e.status === 403) {
      renderMessage("Không có quyền", "Bảng điều hành chỉ dành cho lãnh đạo.");
      return;
    }
    renderMessage("Không tải được số liệu", e instanceof Error ? e.message : "Lỗi không xác định", "Thử lại", "btn-retry");
    document.getElementById("btn-retry")?.addEventListener("click", () => void renderDashboard());
  }
}

async function start(): Promise<void> {
  const user = await getUser();
  if (!user || user.expired) {
    renderMessage("Cần đăng nhập", "Đăng nhập bằng tài khoản lãnh đạo để xem bảng điều hành.", "Đăng nhập", "btn-login");
    document.getElementById("btn-login")?.addEventListener("click", () => void login());
    return;
  }
  if (!canViewDashboard(readRoles(user.access_token))) {
    renderMessage("Không có quyền",
      "Tài khoản của bạn không có vai trò lãnh đạo. Bảng điều hành chỉ đọc chỉ số.",
      "Đăng xuất", "btn-logout");
    document.getElementById("btn-logout")?.addEventListener("click", () => void logout());
    return;
  }
  await renderDashboard();
}

void start();
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { onBeforeUnmount, ref } from "vue";
import { getValidToken } from "../auth";
import { apiJson } from "../api/client";
import { notify } from "./useToast";

export type TrangThaiKetNoi = "dang_ket_noi" | "da_ket_noi" | "mat_ket_noi";
export interface ThongBao {
  id: string;
  title: string;
  body: string;
  link: string | null;
  read_at: string | null;
  created_at: string | null;
}

/**
 * Nhận sự kiện SSE của đúng người dùng và đúng tenant.
 * Vé dùng một lần lấy từ /events/ticket vì EventSource không gửi được header Authorization.
 * Server đã lọc theo người nhận; phía client kiểm tra thêm sub nếu sự kiện có gắn sub.
 */
export function useNotifications(getUserSub: () => string | undefined) {
  const trangThai = ref<TrangThaiKetNoi>("dang_ket_noi");
  const chuaDoc = ref(0);
  const danhSach = ref<ThongBao[]>([]);
  let es: EventSource | null = null;
  let lanThu = 0;
  let hen: number | undefined;
  let dangChay = false;

  async function layVe(): Promise<string | null> {
    const token = await getValidToken();
    if (!token) return null;
    const r = await apiJson<{ ticket: string }>("/events/ticket", { token, method: "POST" }, "Không lấy được vé thông báo");
    return r?.ticket ?? null;
  }

  async function ketNoi(): Promise<void> {
    if (!dangChay) return;
    trangThai.value = "dang_ket_noi";
    try {
      const ticket = await layVe();
      if (!ticket) throw new Error("het phien");
      es = new EventSource(`/api/v1/events?ticket=${encodeURIComponent(ticket)}`);
      es.onopen = () => {
        trangThai.value = "da_ket_noi";
        lanThu = 0;
      };
      // Server gửi sự kiện có tên "notification" (kèm "connected", "ping"); onmessage chỉ nhận sự kiện không tên
      es.addEventListener("notification", (ev) => {
        try {
          xuLy(JSON.parse((ev as MessageEvent).data));
        } catch {
          /* sự kiện không đúng định dạng: bỏ qua */
        }
      });
      es.onerror = () => {
        es?.close();
        es = null;
        trangThai.value = "mat_ket_noi";
        lenLich();
      };
    } catch {
      trangThai.value = "mat_ket_noi";
      lenLich();
    }
  }

  /** Thử lại sau 1, 2, 4... giây, tối đa 30 giây. */
  function lenLich(): void {
    if (!dangChay) return;
    const ms = Math.min(30_000, 1000 * 2 ** lanThu);
    lanThu += 1;
    hen = window.setTimeout(() => void ketNoi(), ms);
  }

  async function taiDanhSach(): Promise<void> {
    const token = await getValidToken();
    if (!token) return;
    try {
      const r = await apiJson<{ items: ThongBao[]; unread: number }>(
        "/flow/notifications?limit=20",
        { token },
        "Không tải được thông báo",
      );
      danhSach.value = r.items || [];
      chuaDoc.value = Number(r.unread ?? 0);
    } catch {
      /* giữ danh sách cũ; SSE vẫn hoạt động */
    }
  }

  function xuLy(d: any): void {
    const sub = getUserSub();
    if (d?.sub && sub && d.sub !== sub) return;
    chuaDoc.value += 1;
    notify(String(d?.message ?? d?.noi_dung ?? "Có cập nhật hồ sơ"), "tin");
    void taiDanhSach();
    window.dispatchEvent(new CustomEvent("dxos:tasks-changed"));
  }

  function batDau(): void {
    if (dangChay) return;
    dangChay = true;
    void taiDanhSach();
    void ketNoi();
  }

  function dungLai(): void {
    dangChay = false;
    es?.close();
    es = null;
    window.clearTimeout(hen);
  }

  /** Đánh dấu tất cả đã đọc trên server và đặt lại bộ đếm. */
  async function danhDauDaDoc(): Promise<void> {
    chuaDoc.value = 0;
    danhSach.value = danhSach.value.map((x) => ({ ...x, read_at: x.read_at || new Date().toISOString() }));
    const token = await getValidToken();
    if (!token) return;
    try {
      await apiJson("/flow/notifications/read-all", { token, method: "POST" }, "Không đánh dấu được thông báo");
    } catch {
      /* lần tải sau sẽ đồng bộ lại */
    }
  }

  async function danhDauMot(id: string): Promise<void> {
    const item = danhSach.value.find((x) => x.id === id);
    if (item && !item.read_at) {
      item.read_at = new Date().toISOString();
      chuaDoc.value = Math.max(0, chuaDoc.value - 1);
    }
    const token = await getValidToken();
    if (!token) return;
    try {
      await apiJson(`/flow/notifications/${encodeURIComponent(id)}/read`, { token, method: "POST" }, "Không đánh dấu được thông báo");
    } catch {
      /* lần tải sau sẽ đồng bộ lại */
    }
  }

  onBeforeUnmount(dungLai);
  return { trangThai, chuaDoc, danhSach, batDau, dungLai, danhDauDaDoc, danhDauMot, taiDanhSach };
}
// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { onBeforeUnmount, ref } from "vue";
import { getValidToken } from "../auth";
import { apiJson } from "../api/client";
import { notify } from "./useToast";

export type TrangThaiKetNoi = "dang_ket_noi" | "da_ket_noi" | "mat_ket_noi";

/**
 * Nhận sự kiện SSE của đúng người dùng và đúng tenant.
 * Vé dùng một lần lấy từ /events/ticket vì EventSource không gửi được header Authorization.
 * Server đã lọc theo người nhận; phía client kiểm tra thêm sub nếu sự kiện có gắn sub.
 */
export function useNotifications(getUserSub: () => string | undefined) {
  const trangThai = ref<TrangThaiKetNoi>("dang_ket_noi");
  const chuaDoc = ref(0);
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
      es.onmessage = (ev) => {
        try {
          xuLy(JSON.parse(ev.data));
        } catch {
          /* sự kiện không đúng định dạng: bỏ qua */
        }
      };
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

  function xuLy(d: any): void {
    const sub = getUserSub();
    if (d?.sub && sub && d.sub !== sub) return;
    chuaDoc.value += 1;
    notify(String(d?.message ?? d?.noi_dung ?? "Có cập nhật hồ sơ"), "tin");
  }

  function batDau(): void {
    if (dangChay) return;
    dangChay = true;
    void ketNoi();
  }

  function dungLai(): void {
    dangChay = false;
    es?.close();
    es = null;
    window.clearTimeout(hen);
  }

  /** Đánh dấu đã đọc: đặt lại bộ đếm trên màn hình. */
  function danhDauDaDoc(): void {
    chuaDoc.value = 0;
  }

  onBeforeUnmount(dungLai);
  return { trangThai, chuaDoc, batDau, dungLai, danhDauDaDoc };
}
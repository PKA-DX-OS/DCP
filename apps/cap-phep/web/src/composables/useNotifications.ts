// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { ref, type Ref } from "vue";
import type { HoSo } from "../types";

const TASK_LABELS: Record<string, string> = {
  taskKiemTraHopLe: "Kiểm tra tính hợp lệ hồ sơ",
  taskPhanCong: "Phân công cán bộ thẩm định",
  taskThamDinh: "Thẩm định hồ sơ",
  taskThamDinhNhanh: "Thẩm định nhanh",
  taskThamDinhChuyenSau: "Thẩm định chuyên sâu",
  taskThamDinhDonGian: "Thẩm định đơn giản",
  taskPheDuyet: "Phê duyệt hồ sơ",
  taskDuyetCapPhep: "Duyệt cấp giấy phép",
  taskPheDuyetTruyCapKhan: "Phê duyệt truy cập khẩn cấp",
  taskChoBoSung: "Chờ bổ sung giấy tờ",
  taskBanGiao: "Bàn giao kết quả",
};

export function useNotifications(
  user: Ref<any>,
  dossiers: Ref<HoSo[]>,
  refreshData: () => Promise<void>,
  openDossierByCode: (code: string) => Promise<void>,
  viewDossierDetail: (d: HoSo) => void
) {
  const notifications = ref<Array<any>>([]);
  const unreadCount = ref(0);
  let sseSource: EventSource | null = null;
  let sseReconnectTimer: any = null;
  let sseReconnectDelay = 1000;
  let sseRefreshTimer: any = null;

  function closeSSE() {
    if (sseRefreshTimer) {
      clearTimeout(sseRefreshTimer);
      sseRefreshTimer = null;
    }
    if (sseReconnectTimer) {
      clearTimeout(sseReconnectTimer);
      sseReconnectTimer = null;
    }
    if (sseSource) {
      sseSource.close();
      sseSource = null;
    }
  }

  async function initSSE() {
    closeSSE();
    const token = user.value?.access_token;
    if (!token) return;

    try {
      const res = await fetch("/api/v1/events/ticket", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        console.warn("Không lấy được vé SSE:", res.status);
        if (!sseReconnectTimer && user.value?.access_token) {
          sseReconnectTimer = setTimeout(() => {
            sseReconnectTimer = null;
            sseReconnectDelay = Math.min(sseReconnectDelay * 2, 30000);
            initSSE();
          }, sseReconnectDelay);
        }
        return;
      }
      const data = await res.json();
      const ticket = data.ticket;
      const url = `/api/v1/events?ticket=${encodeURIComponent(ticket)}`;
      sseSource = new EventSource(url);

      sseSource.addEventListener("notification", (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.event === "process_started") {
            const maHoSo = payload.ma_ho_so || payload.business_code || payload.business_key || "";
            notifications.value.unshift({
              id: payload.process_id,
              title: `Hồ sơ mới ${maHoSo}`.trim(),
              body: `Hồ sơ ${maHoSo} vừa được nộp, chờ một cửa tiếp nhận.`,
              link: payload.business_key,
              ma_ho_so: maHoSo,
              read_at: null,
              time: "Vừa xong",
            });
            unreadCount.value++;
          } else {
            const taskLabel = (payload.task_def && TASK_LABELS[payload.task_def]) || payload.task_def || "Hồ sơ";
            notifications.value.unshift({
              id: payload.task_id,
              title: "Hồ sơ có bước mới",
              body: `Bước "${taskLabel}" vừa hoàn thành.`,
              link: payload.task_id,
              read_at: null,
              time: "Vừa xong",
            });
            unreadCount.value++;
          }
          if (!sseRefreshTimer) {
            sseRefreshTimer = setTimeout(() => {
              sseRefreshTimer = null;
              refreshData();
            }, 1500);
          }
        } catch (err) {
          console.debug("SSE parse error", err);
        }
      });

      sseSource.onopen = () => {
        sseReconnectDelay = 1000;
      };

      sseSource.onerror = (err) => {
        console.debug("SSE connection error, retrying...", err);
        if (sseSource) {
          sseSource.close();
          sseSource = null;
        }
        if (!sseReconnectTimer && user.value?.access_token) {
          sseReconnectTimer = setTimeout(() => {
            sseReconnectTimer = null;
            sseReconnectDelay = Math.min(sseReconnectDelay * 2, 30000);
            initSSE();
          }, sseReconnectDelay);
        }
      };
    } catch (err) {
      console.debug("SSE error", err);
    }
  }

  async function loadNotifications() {
    if (!user.value?.access_token) return;
    try {
      const res = await fetch("/api/v1/rest/rpc/lay_thong_bao", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${user.value.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          notifications.value = data;
          unreadCount.value = data.filter((n: any) => !n.read_at).length;
        }
      }
    } catch (err) {
      console.debug("Lỗi tải thông báo:", err);
    }
  }

  async function handleMarkAllRead() {
    if (!user.value?.access_token) return;
    try {
      await fetch("/api/v1/rest/rpc/danh_dau_da_doc", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${user.value.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ p_id: null }),
      });
      notifications.value.forEach((n: any) => {
        n.read_at = new Date().toISOString();
      });
      unreadCount.value = 0;
    } catch (err) {
      console.debug("Lỗi đánh dấu đã đọc tất cả:", err);
    }
  }

  async function handleSelectNotification(n: any) {
    if (!user.value?.access_token) return;
    if (!n.read_at && n.id) {
      try {
        await fetch("/api/v1/rest/rpc/danh_dau_da_doc", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${user.value.access_token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ p_id: n.id }),
        });
        n.read_at = new Date().toISOString();
        if (unreadCount.value > 0) unreadCount.value--;
      } catch (err) {
        console.debug("Lỗi cập nhật đọc thông báo:", err);
      }
    }

    if (n.ma_ho_so) {
      await openDossierByCode(n.ma_ho_so);
    } else if (n.link) {
      const matched = dossiers.value.find((d: any) => d.id === n.link || d.ma_ho_so === n.link);
      if (matched) {
        viewDossierDetail(matched);
      }
    }
  }

  return {
    notifications,
    unreadCount,
    initSSE,
    closeSSE,
    loadNotifications,
    handleMarkAllRead,
    handleSelectNotification,
  };
}

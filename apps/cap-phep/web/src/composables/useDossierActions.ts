// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { completeTask } from "../api/flow";
import { nopHoSo, supplementHoSo } from "../api/dossiers";
import type { DocPayload, FlowTask, NopHoSoPayload } from "../types";
import { notify } from "./useToast";

export interface NguoiDung {
  sub?: string;
  roles: string[];
}

/**
 * Thao tác hồ sơ. Giao diện chỉ hiện nút khi đúng quyền; server vẫn kiểm tra lại.
 * Không có hàm nào cho phép chọn bước tùy ý: chỉ hoàn thành đúng việc đang được giao.
 * Không có thao tác ký trên giao diện: ký do dịch vụ doc-sign thực hiện khi cấp giấy.
 */
export function useDossierActions(getToken: () => Promise<string | null>, getUser: () => NguoiDung | null) {
  async function token(): Promise<string> {
    const t = await getToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    return t;
  }

  function laNguoiDuocGiao(task: FlowTask): boolean {
    const sub = getUser()?.sub;
    return !!sub && task.assignee === sub;
  }

  async function hoanThanhViec(task: FlowTask, variables: Record<string, any> = {}): Promise<boolean> {
    if (!laNguoiDuocGiao(task)) {
      notify("Việc này không được giao cho bạn", "loi");
      return false;
    }
    try {
      await completeTask(await token(), task.id, variables);
      notify("Đã hoàn thành việc", "ok");
      return true;
    } catch (e) {
      notify(e instanceof Error ? e.message : "Không hoàn thành được việc", "loi");
      return false;
    }
  }

  async function boSung(payload: any): Promise<boolean> {
    try {
      await supplementHoSo(await token(), payload);
      notify("Đã gửi bổ sung hồ sơ", "ok");
      return true;
    } catch (e) {
      notify(e instanceof Error ? e.message : "Không bổ sung được hồ sơ", "loi");
      return false;
    }
  }

  async function nop(payload: NopHoSoPayload, hoSoId: string, tep: DocPayload[]): Promise<boolean> {
    try {
      await nopHoSo(await token(), payload, hoSoId, tep);
      notify("Đã nộp hồ sơ", "ok");
      return true;
    } catch (e) {
      notify(e instanceof Error ? e.message : "Không nộp được hồ sơ", "loi");
      return false;
    }
  }

  return { laNguoiDuocGiao, hoanThanhViec, boSung, nop };
}
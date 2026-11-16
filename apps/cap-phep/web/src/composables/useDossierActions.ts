// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import type { Ref } from "vue";
import type { DocEntry, DocError, HoSo, NopHoSoPayload } from "../types";
import { nopHoSo, supplementHoSo, uploadFile, linkDossierFile, startWorkflow, fetchTasks, completeTask } from "../api";
import { notify } from "./useToast";

export function useDossierActions(
  user: Ref<any>,
  submitting: Ref<boolean>,
  refreshData: () => Promise<void>,
  onDocErrors?: (errors: DocError[]) => void
) {
  async function submitHoSo(form: NopHoSoPayload, docs: DocEntry[], onDone: () => void): Promise<boolean> {
    if (!user.value?.access_token) return false;
    submitting.value = true;
    onDocErrors?.([]);
    try {
      const token = user.value.access_token;
      // Sinh mã hồ sơ trước để tải tệp vào vùng nháp, rồi nộp một bước; máy chủ kiểm tra lại danh mục giấy tờ.
      const hoSoId = crypto.randomUUID();
      const tep = [];
      for (const doc of docs) {
        if (!doc.file) continue;
        const fileRes = await uploadFile(token, doc.file, "draft.ho_so", hoSoId);
        if (!fileRes?.file_id) {
          throw new Error(`Không tải được tệp ${doc.loai}`);
        }
        tep.push({
          file_id: fileRes.file_id,
          loai: doc.loai,
          ngay_cap: doc.ngay_cap || null,
          ngay_het_han: doc.ngay_het_han || null,
          thong_tin: doc.thong_tin || {},
        });
      }

      const res = await nopHoSo(token, form, hoSoId, tep);

      try {
        await startWorkflow(token, "cap-phep", res.ma_ho_so, {
          ma_ho_so: res.ma_ho_so,
          ho_so_id: hoSoId,
          chu_dau_tu_sub: user.value.profile.sub,
          dien_tich_san_m2: form.dien_tich_san_m2,
          khu_quan_ly_kien_truc: form.khu_quan_ly_kien_truc,
        });
      } catch (wfErr) {
        console.warn("Lỗi khởi tạo quy trình:", wfErr);
      }

      onDone();
      await refreshData();
      notify(`Đã nộp hồ sơ ${res.ma_ho_so}. Phường sẽ kiểm tra và tiếp nhận.`);
      return true;
    } catch (err: any) {
      const docErrors: DocError[] = err?.docErrors || [];
      if (docErrors.length) {
        onDocErrors?.(docErrors);
        notify(`Hồ sơ chưa đủ điều kiện nộp: ${docErrors[0]?.reason || "kiểm tra lại giấy tờ"}.`, "loi");
      } else {
        notify(`Không nộp được hồ sơ: ${err.message}`, "loi");
      }
      return false;
    } finally {
      submitting.value = false;
    }
  }

  async function handleSupplementHoSo(supplementingHoSo: Ref<HoSo | null>, payload: any) {
    if (!user.value?.access_token || !supplementingHoSo.value) return;
    const hoso = supplementingHoSo.value;
    submitting.value = true;
    try {
      const token = user.value.access_token;
      const formValues = payload.form || payload;

      if (payload.file) {
        try {
          const fileRes = await uploadFile(token, payload.file, "ho_so", hoso.id);
          const fId = fileRes?.file_id || fileRes?.id;
          if (fId) {
            await linkDossierFile(token, hoso.id, fId, "tai_lieu_bo_sung");
          }
        } catch (fileErr) {
          console.warn("Lỗi tải tệp bổ sung:", fileErr);
        }
      }

      // U-06: tìm nhiệm vụ chờ bổ sung trước; chỉ khi có nhiệm vụ mới cập nhật dữ liệu rồi hoàn thành nhiệm vụ
      const userTasks = await fetchTasks(token);
      const boSungTask = userTasks.find(
        (t: any) =>
          t.taskDefinitionKey === "taskChoBoSung" &&
          (t.processInstanceId === hoso.process_instance_id ||
            t.variables?.some((v: any) => v.name === "ho_so_id" && v.value === hoso.id))
      );
      if (!boSungTask) {
        throw new Error("KHONG_CO_NHIEM_VU_BO_SUNG");
      }

      await supplementHoSo(token, {
        p_ho_so_id: hoso.id,
        p_dia_chi_cong_trinh: formValues.dia_chi_cong_trinh,
        p_thua_dat: formValues.thua_dat,
        p_so_tang: formValues.so_tang,
        p_dien_tich_san_m2: formValues.dien_tich_san_m2,
        p_khu_quan_ly_kien_truc: formValues.khu_quan_ly_kien_truc,
      });

      await completeTask(token, boSungTask.id, {
        noiDungBoSung: formValues.ghi_chu || "Chủ đầu tư đã bổ sung hồ sơ",
      });

      supplementingHoSo.value = null;
      await refreshData();
      notify("Đã gửi bổ sung. Hồ sơ chuyển lại cho một cửa kiểm tra.");
    } catch (err: any) {
      const rawMsg = err.message || "";
      let friendlyMsg = "Có lỗi xảy ra khi bổ sung hồ sơ. Vui lòng thử lại.";
      if (rawMsg.includes("KHONG_CO_NHIEM_VU_BO_SUNG")) {
        friendlyMsg = "Hồ sơ này hiện không có yêu cầu bổ sung đang chờ bạn.";
      } else if (rawMsg.includes("42501") || rawMsg.includes("Chỉ chủ đầu tư")) {
        friendlyMsg = "Bạn không có quyền bổ sung cho hồ sơ này.";
      } else if (rawMsg.includes("CAN_BO_SUNG")) {
        friendlyMsg = "Hồ sơ hiện không ở trạng thái Cần bổ sung.";
      }
      notify(friendlyMsg, "loi");
    } finally {
      submitting.value = false;
    }
  }

  return { submitHoSo, handleSupplementHoSo };
}

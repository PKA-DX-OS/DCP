// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

import { ref } from "vue";
import { ApiError } from "../api/client";
import { fetchDocumentRequirements, fetchHoSo, nopHoSo, openHoSo, supplementHoSo, updateSubjectAuthority } from "../api/dossiers";
import { linkDossierFile, uploadFile } from "../api/files";
import { completeTask, fetchTasks, startWorkflow } from "../api/flow";
import { fetchConsents, fetchDsarRequests, grantConsent, submitDsarRequest, withdrawConsent } from "../api/dsar";
import { requestBreakGlass } from "../api/break_glass";
import type { DocEntry, DocError, DocPayload, DocRequirement, HoSo, NopHoSoPayload } from "../types";
import { notify } from "./useToast";

/** Kết quả mở hồ sơ: có quyền thì trả hồ sơ, bị chặn thì trả mã để xin truy cập khẩn. */
export type KetQuaMo = { hoSo: HoSo } | { biChan: { id: string; ma: string } } | null;

/**
 * Thao tác của chủ đầu tư (nộp, bổ sung, dữ liệu cá nhân) và mở hồ sơ có kiểm quyền.
 * Mọi kiểm tra quyền và giấy tờ vẫn do server làm lại; ở đây chỉ dẫn luồng và báo lỗi dễ hiểu.
 */
export function useCongDan(getToken: () => Promise<string | null>, getSub: () => string | undefined) {
  const dossiers = ref<HoSo[]>([]);
  const requirements = ref<DocRequirement[]>([]);
  const docErrors = ref<DocError[]>([]);
  const consents = ref<{ purpose: string; withdrawn_at?: string | null }[]>([]);
  const dsarList = ref<any[]>([]);
  const dangTai = ref(false);
  const dangTaiGiayTo = ref(false);
  const dangGui = ref(false);
  const loi = ref("");

  async function token(): Promise<string> {
    const t = await getToken();
    if (!t) throw new Error("Hết phiên, vui lòng đăng nhập lại");
    return t;
  }

  function thongDiep(e: unknown, macDinh: string): string {
    return e instanceof Error && e.message ? e.message : macDinh;
  }

  async function taiHoSo(): Promise<void> {
    dangTai.value = true;
    loi.value = "";
    try {
      dossiers.value = await fetchHoSo(await token());
    } catch (e) {
      loi.value = thongDiep(e, "Không tải được danh sách hồ sơ");
    } finally {
      dangTai.value = false;
    }
  }

  async function taiGiayTo(): Promise<void> {
    dangTaiGiayTo.value = true;
    try {
      requirements.value = await fetchDocumentRequirements(await token());
    } catch (e) {
      notify(thongDiep(e, "Không tải được danh mục giấy tờ"), "loi");
    } finally {
      dangTaiGiayTo.value = false;
    }
  }

  /** Tải tệp vào vùng nháp, nộp một lần, rồi khởi động quy trình cấp phép. */
  async function nop(form: NopHoSoPayload, docs: DocEntry[]): Promise<boolean> {
    dangGui.value = true;
    docErrors.value = [];
    try {
      const t = await token();
      const hoSoId = crypto.randomUUID();
      const tep: DocPayload[] = [];
      for (const d of docs) {
        if (!d.file) continue;
        const r = await uploadFile(t, d.file, "draft.ho_so", hoSoId);
        tep.push({
          file_id: r.file_id,
          loai: d.loai,
          ngay_cap: d.ngay_cap || null,
          ngay_het_han: d.ngay_het_han || null,
          thong_tin: d.thong_tin || {},
        });
      }
      const res = await nopHoSo(t, form, hoSoId, tep);
      try {
        await updateSubjectAuthority(t, res.id, {
          doi_tuong: form.doi_tuong,
          trong_kcn: form.trong_kcn,
          cap_hanh_chinh: form.cap_hanh_chinh,
        });
      } catch {
        notify("Đã nộp hồ sơ nhưng chưa lưu được thông tin thẩm quyền; cán bộ sẽ bổ sung.", "canh_bao");
      }
      try {
        await startWorkflow(t, "cap-phep", res.ma_ho_so, {
          ho_so_id: res.id,
          ma_ho_so: res.ma_ho_so,
          chu_dau_tu_sub: getSub(),
          dien_tich_san_m2: Number(form.dien_tich_san_m2) || 100,
          khu_quan_ly_kien_truc: Boolean(form.khu_quan_ly_kien_truc),
          dia_chi_cong_trinh: form.dia_chi_cong_trinh,
          trang_thai_ho_so: "DA_NOP",
          do_uu_tien: "binh_thuong",
        });
      } catch {
        notify(`Đã nộp hồ sơ ${res.ma_ho_so} nhưng chưa chuyển được tới một cửa. Phường sẽ xử lý thủ công.`, "canh_bao");
      }
      notify(`Đã nộp hồ sơ ${res.ma_ho_so}. Phường sẽ kiểm tra và tiếp nhận.`, "ok");
      await taiHoSo();
      return true;
    } catch (e) {
      const ds = e instanceof ApiError ? (e.docErrors as DocError[] | undefined) : undefined;
      if (ds?.length) {
        docErrors.value = ds;
        notify(`Hồ sơ chưa đủ điều kiện nộp: ${ds[0].reason}`, "loi");
      } else {
        notify(thongDiep(e, "Không nộp được hồ sơ"), "loi");
      }
      return false;
    } finally {
      dangGui.value = false;
    }
  }

  /** Bổ sung: chỉ khi có việc taskChoBoSung đang chờ; cập nhật dữ liệu rồi hoàn thành việc đó. */
  async function boSung(hoSo: HoSo, payload: { form: any; file?: File | null }): Promise<boolean> {
    dangGui.value = true;
    try {
      const t = await token();
      const viec = (await fetchTasks(t)).find(
        (x) =>
          x.taskDefinitionKey === "taskChoBoSung" &&
          (x.processInstanceId === hoSo.process_instance_id ||
            ((x.variables as any[] | undefined) || []).some((v: any) => v.name === "ho_so_id" && v.value === hoSo.id)),
      );
      if (!viec) {
        notify("Hồ sơ này hiện không có yêu cầu bổ sung đang chờ bạn.", "canh_bao");
        return false;
      }
      if (payload.file) {
        const r = await uploadFile(t, payload.file, "ho_so", hoSo.id);
        await linkDossierFile(t, hoSo.id, r.file_id, "tai_lieu_bo_sung");
      }
      const f = payload.form || {};
      await supplementHoSo(t, {
        p_ho_so_id: hoSo.id,
        p_dia_chi_cong_trinh: f.dia_chi_cong_trinh,
        p_thua_dat: f.thua_dat,
        p_so_tang: f.so_tang,
        p_dien_tich_san_m2: f.dien_tich_san_m2,
        p_khu_quan_ly_kien_truc: f.khu_quan_ly_kien_truc,
      });
      await completeTask(t, viec.id, { noiDungBoSung: f.ghi_chu || "Chủ đầu tư đã bổ sung hồ sơ" });
      notify("Đã gửi bổ sung. Hồ sơ chuyển lại cho một cửa kiểm tra.", "ok");
      await taiHoSo();
      return true;
    } catch (e) {
      notify(thongDiep(e, "Không bổ sung được hồ sơ"), "loi");
      return false;
    } finally {
      dangGui.value = false;
    }
  }

  /** Mở hồ sơ qua RPC mo_ho_so (có ghi nhật ký). 403 thì trả về để giao diện mời xin truy cập khẩn. */
  async function moHoSo(idHoacMa: string, maHienThi = ""): Promise<KetQuaMo> {
    try {
      return { hoSo: (await openHoSo(await token(), idHoacMa)) as HoSo };
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        return { biChan: { id: e.data?.ho_so_id || idHoacMa, ma: e.data?.ma_ho_so || maHienThi || idHoacMa } };
      }
      notify(thongDiep(e, "Không mở được hồ sơ"), "loi");
      return null;
    }
  }

  async function xinTruyCapKhan(hoSoId: string, lyDo: string): Promise<boolean> {
    dangGui.value = true;
    try {
      await requestBreakGlass(await token(), hoSoId, lyDo);
      notify("Đã gửi yêu cầu truy cập khẩn. Lãnh đạo phường sẽ duyệt.", "ok");
      return true;
    } catch (e) {
      notify(thongDiep(e, "Không gửi được yêu cầu truy cập khẩn"), "loi");
      return false;
    } finally {
      dangGui.value = false;
    }
  }

  async function taiDuLieuCaNhan(): Promise<void> {
    try {
      const t = await token();
      [consents.value, dsarList.value] = await Promise.all([fetchConsents(t), fetchDsarRequests(t)]);
    } catch (e) {
      notify(thongDiep(e, "Không tải được dữ liệu cá nhân"), "loi");
    }
  }

  /** Lưu lựa chọn đồng ý: bật mục mới chọn, rút mục bị bỏ chọn. */
  async function luuDongY(chon: Record<string, boolean>): Promise<void> {
    try {
      const t = await token();
      const dangBat = new Set(consents.value.filter((c) => !c.withdrawn_at).map((c) => c.purpose));
      for (const [muc, bat] of Object.entries(chon)) {
        if (bat && !dangBat.has(muc)) await grantConsent(t, muc);
        if (!bat && dangBat.has(muc)) await withdrawConsent(t, muc);
      }
      await taiDuLieuCaNhan();
    } catch (e) {
      notify(thongDiep(e, "Không lưu được lựa chọn"), "loi");
    }
  }

  async function guiYeuCauDuLieu(loai: string, ghiChu?: string): Promise<void> {
    try {
      // loai: access | rectify | erase | restrict | withdraw (khớp core_api.gui_yeu_cau_dsar)
      await submitDsarRequest(await token(), loai, ghiChu || "");
      notify("Đã gửi yêu cầu. Phường sẽ xác nhận trong 2 ngày làm việc.", "ok");
      await taiDuLieuCaNhan();
    } catch (e) {
      notify(thongDiep(e, "Không gửi được yêu cầu"), "loi");
    }
  }

  return {
    dossiers, requirements, docErrors, consents, dsarList, dangTai, dangTaiGiayTo, dangGui, loi,
    taiHoSo, taiGiayTo, nop, boSung, moHoSo, xinTruyCapKhan, taiDuLieuCaNhan, luuDongY, guiYeuCauDuLieu,
  };
}

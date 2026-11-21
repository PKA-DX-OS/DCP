// SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Điểm vào lớp API của web cấp phép. Mọi lời gọi đi qua client chung `api/client.ts`
 * (gốc API từ cấu hình, timeout, thử lại có giới hạn, xử lý 401 và lỗi mạng thống nhất).
 * Hợp đồng chính (đường dẫn sau gốc API):
 *  - /rest/v_ho_so, /rest/v_ho_so_tep, /rest/document_requirements
 *  - /rest/rpc/nop_ho_so, bo_sung_ho_so, dinh_kem_tep, danh_gia_tep, mo_ho_so
 *  - /rest/rpc/xin_truy_cap_khan, duyet_truy_cap_khan, ds_truy_cap_khan
 *  - /rest/rpc/lay_nhat_ky_ho_so, thong_tin_giay_phep
 *  - /rest/v_cong_trinh, /rest/v_phieu_kiem_tra, /rest/rpc/lap_phieu_kiem_tra
 *  - /rest/consents, /rest/dsar_requests, /rest/rpc/dong_y_du_lieu, rut_dong_y_du_lieu, gui_yeu_cau_dsar
 *  - /flow/tasks, /flow/tasks/{id}/complete, /flow/processes/start
 *  - /files (tải lên, tải về)
 */

export * from "./client";
export * from "./dossiers";
export * from "./flow";
export * from "./break_glass";
export * from "./files";
export * from "./construction";
export * from "./dsar";
export * from "./legal";
export * from "./dh";
export * from "./ocr";

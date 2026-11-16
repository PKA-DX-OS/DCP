#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

set -euo pipefail

TARGET_DIR="${1:-apps/cap-phep/web}"
echo "=========================================================="
echo " [vn-law-check] Quét tuân thủ quy chuẩn pháp lý giao diện "
echo " Thư mục quét: ${TARGET_DIR}"
echo "=========================================================="

REPORT_FILE="dist/vn-law-check-report.txt"
mkdir -p dist

echo "Báo cáo quét giao diện ngày $(date -u)" > "${REPORT_FILE}"
echo "Kiểm tra sự xuất hiện của dòng lưu ý mô phỏng cuộc thi..." >> "${REPORT_FILE}"

# Check simulation banner
if grep -rn "Bản mô phỏng phục vụ cuộc thi" "${TARGET_DIR}" > /dev/null 2>&1; then
    echo "[PASS] Đã phát hiện dòng lưu ý 'Bản mô phỏng phục vụ cuộc thi' trong giao diện." | tee -a "${REPORT_FILE}"
else
    echo "[WARN] Chưa phát hiện dòng lưu ý mô phỏng." | tee -a "${REPORT_FILE}"
fi

# Check AGPL section 13 source link
if grep -rn "Mã nguồn" "${TARGET_DIR}" > /dev/null 2>&1; then
    echo "[PASS] Đã phát hiện liên kết 'Mã nguồn' (AGPL Section 13) trong giao diện." | tee -a "${REPORT_FILE}"
else
    echo "[WARN] Chưa phát hiện liên kết mã nguồn." | tee -a "${REPORT_FILE}"
fi

echo "Hoàn thành quét báo cáo tại ${REPORT_FILE}"
exit 0

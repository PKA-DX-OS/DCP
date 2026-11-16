# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Thư viện chia sẻ lõi DX-OS (dxos_core):
Cung cấp các tiện ích dùng chung cho các microservices Tầng 1:
- Xác thực và giải mã JWT OIDC qua JWKS.
- Kết nối cơ sở dữ liệu asyncpg và gán ngữ cảnh RLS.
- Tương tác kho lưu trữ đối tượng S3 SeaweedFS.
- Kết nối OpenBao Transit ký số và xác minh Ed25519.
- Quét mã độc ClamAV INSTREAM.
- Ghi nhận nhật ký kiểm toán và Transactional Outbox.
"""

__version__ = "1.0.0"

#!/bin/sh
# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Khởi tạo SoftHSM2 + test CA cho chế độ SIGNING_MODE=pkcs11.
# Đây là mô phỏng kỹ thuật, không phải CA/HSM có giá trị pháp lý.
# Chạy lại an toàn: token đã có (.initialized) thì bỏ qua, không tạo lại khóa.

set -eu

TOKEN_LABEL="${SOFTHSM_TOKEN:-dxos}"
PIN="${SOFTHSM_PIN:-1234}"
# SO PIN riêng nếu có; mặc định dùng PIN người dùng (môi trường demo). Không in PIN ra log.
SO_PIN="${SOFTHSM_SO_PIN:-$PIN}"
TOKEN_DIR="/var/lib/softhsm/tokens"
CERT_DIR="/certs"
LIB="$(find /usr/lib -name 'libsofthsm2.so' 2>/dev/null | head -n 1)"

if [ -z "$LIB" ]; then
  echo "[softhsm-init] Không tìm thấy libsofthsm2.so"
  exit 1
fi

mkdir -p "$TOKEN_DIR" "$CERT_DIR"

if [ ! -f "$TOKEN_DIR/.initialized" ]; then
  echo "[softhsm-init] Khởi tạo token $TOKEN_LABEL..."
  softhsm2-util --init-token --free --label "$TOKEN_LABEL" --so-pin "$SO_PIN" --pin "$PIN"

  echo "[softhsm-init] Tạo test CA + leaf certificate..."
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$CERT_DIR/ca.key" -out "$CERT_DIR/ca.crt" \
    -subj "/CN=DXOS Test CA/O=DX-OS Demo" -days 3650 \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign"
  openssl req -newkey rsa:2048 -nodes \
    -keyout /tmp/leaf.key -out /tmp/leaf.csr \
    -subj "/CN=DXOS Doc Sign/O=DX-OS Demo"
  cat > /tmp/leaf.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,nonRepudiation
extendedKeyUsage=emailProtection
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF
  openssl x509 -req -in /tmp/leaf.csr -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial -out /tmp/leaf.crt -days 3650 -sha256 -extfile /tmp/leaf.ext

  # softhsm2-util chỉ nhận khóa PKCS#8 không mã hóa
  openssl pkcs8 -topk8 -nocrypt -in /tmp/leaf.key -out /tmp/leaf-pkcs8.key

  echo "[softhsm-init] Import private key vào token..."
  softhsm2-util --import /tmp/leaf-pkcs8.key --token "$TOKEN_LABEL" --label doc-sign --id 01 --pin "$PIN"

  echo "[softhsm-init] Import certificate vào token..."
  openssl x509 -in /tmp/leaf.crt -outform DER -out /tmp/leaf.der
  pkcs11-tool --module "$LIB" --token-label "$TOKEN_LABEL" --login --pin "$PIN" \
    --write-object /tmp/leaf.der --type cert --id 01 --label doc-sign

  # Khóa riêng đã nằm trong token; xóa bản tạm trên đĩa
  rm -f /tmp/leaf.key /tmp/leaf-pkcs8.key /tmp/leaf.csr /tmp/leaf.ext /tmp/leaf.der
  touch "$TOKEN_DIR/.initialized"
  echo "[softhsm-init] Hoàn tất."
else
  echo "[softhsm-init] Token đã tồn tại, bỏ qua khởi tạo."
fi

chown -R 10001:10001 "$TOKEN_DIR" "$CERT_DIR" || true
chmod 600 "$CERT_DIR/ca.key" || true

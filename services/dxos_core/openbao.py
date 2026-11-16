# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import base64
import logging
import httpx
from pathlib import Path
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException, status
from dxos_core.config import settings

logger = logging.getLogger("dxos.openbao")


class OpenBaoClient:
    """
    Client tương tác với OpenBao KMS Transit Engine.
    Tuân thủ nguyên tắc Fail-Closed: Ký số và xác thực chữ ký hoàn toàn qua Transit KMS,
    không dùng khóa giả lập trong bộ nhớ RAM hay tiến trình cục bộ.
    """

    def __init__(self):
        self.addr = settings.openbao_addr
        self.token = settings.openbao_token

    def _get_token(self) -> str:
        token_path = Path("/app/secrets/bao-doc-sign.token")
        if token_path.exists():
            try:
                t = token_path.read_text(encoding="utf-8").strip()
                if t:
                    return t
            except (OSError, UnicodeDecodeError) as e:
                logger.debug(f"Không thể đọc tệp token OpenBao: {e}")
        return settings.openbao_token

    def _headers(self):
        return {
            "X-Vault-Token": self._get_token(),
            "Content-Type": "application/json",
        }

    def get_status(self) -> dict:
        """Kiểm tra trạng thái niêm phong và sẵn sàng của OpenBao KMS."""
        try:
            with httpx.Client(base_url=self.addr, timeout=3.0) as client:
                resp = client.get("/v1/sys/seal-status")
                if resp.status_code == 200:
                    data = resp.json()
                    sealed = bool(data.get("sealed", False))
                    return {
                        "status": "sealed" if sealed else "ok",
                        "sealed": sealed,
                        "initialized": bool(data.get("initialized", True)),
                        "progress": data.get("progress", 0),
                        "threshold": data.get("t", 3),
                    }
                elif resp.status_code == 503:
                    return {"status": "sealed", "sealed": True, "initialized": True}
                else:
                    return {"status": "error", "sealed": True, "code": resp.status_code}
        except Exception as e:
            return {"status": "unavailable", "sealed": True, "error": str(e)}

    def sign(self, key_name: str, data: bytes) -> Tuple[str, int]:
        """
        Ký số dữ liệu bằng khóa Transit (Ed25519).
        Trả về tuple (signature, key_version). Lỗi KMS -> 503 Service Unavailable kèm ma_loi.
        """
        b64_data = base64.b64encode(data).decode("utf-8")
        try:
            with httpx.Client(base_url=self.addr, timeout=5.0) as client:
                resp = client.post(
                    f"/v1/transit/sign/{key_name}",
                    headers=self._headers(),
                    json={"input": b64_data},
                )
                if resp.status_code == 200:
                    data_resp = resp.json().get("data", {})
                    signature = data_resp.get("signature")
                    key_version = data_resp.get("key_version", 1)
                    return signature, key_version

                logger.error(f"OpenBao trả lỗi ký số: HTTP {resp.status_code} - {resp.text}")
                is_sealed = "sealed" in resp.text.lower() or resp.status_code == 503
                ma_loi = "KMS_SEALED" if is_sealed else "KMS_UNAVAILABLE"
                thong_bao = "Dịch vụ ký số KMS OpenBao đang bị khóa (Sealed)" if is_sealed else f"Dịch vụ ký số KMS OpenBao từ chối: HTTP {resp.status_code}"
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"loi": thong_bao, "ma_loi": ma_loi},
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Lỗi kết nối tới OpenBao KMS khi ký số: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"loi": f"Dịch vụ ký số KMS OpenBao không sẵn sàng: {e}", "ma_loi": "KMS_UNAVAILABLE"},
            )

    def get_public_key_pem(self, key_name: str = "doc-sign") -> str:
        """
        Lấy khóa công khai Ed25519 định dạng PEM từ Transit KMS.
        Lỗi -> 503 Service Unavailable.
        """
        try:
            with httpx.Client(base_url=self.addr, timeout=5.0) as client:
                resp = client.get(f"/v1/transit/keys/{key_name}", headers=self._headers())
                if resp.status_code == 200:
                    data_resp = resp.json().get("data", {})
                    keys = data_resp.get("keys", {})
                    latest_ver = str(data_resp.get("latest_version", 1))
                    pub_key_b64 = keys.get(latest_ver, {}).get("public_key")
                    if not pub_key_b64:
                        raise ValueError("Không tìm thấy khóa công khai trong phản hồi của OpenBao")
                    pub_bytes = base64.b64decode(pub_key_b64)
                    ed_pub = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
                    return ed_pub.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    ).decode("utf-8")

                logger.error(f"OpenBao trả lỗi lấy khóa công khai: HTTP {resp.status_code} - {resp.text}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Dịch vụ KMS từ chối cung cấp khóa công khai: HTTP {resp.status_code}",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Lỗi kết nối tới OpenBao KMS khi lấy khóa công khai: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Dịch vụ ký số KMS OpenBao không sẵn sàng: {e}",
            )

    def verify(self, key_name: str, data: bytes, signature: str) -> bool:
        """
        Xác minh tính hợp lệ của chữ ký Ed25519 trực tiếp qua OpenBao Transit.
        Không xác thực bằng khóa cục bộ. Lỗi -> 503 Service Unavailable.
        """
        b64_data = base64.b64encode(data).decode("utf-8")
        try:
            with httpx.Client(base_url=self.addr, timeout=5.0) as client:
                resp = client.post(
                    f"/v1/transit/verify/{key_name}",
                    headers=self._headers(),
                    json={"input": b64_data, "signature": signature},
                )
                if resp.status_code == 200:
                    return resp.json().get("data", {}).get("valid", False)
                logger.error(f"OpenBao trả lỗi xác thực chữ ký: HTTP {resp.status_code} - {resp.text}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Dịch vụ ký số KMS không phản hồi hợp lệ khi xác minh chữ ký",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Lỗi kết nối OpenBao KMS khi xác minh chữ ký: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Dịch vụ ký số KMS OpenBao không sẵn sàng: {e}",
            )


openbao_client = OpenBaoClient()

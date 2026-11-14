# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import time
import httpx
import jwt
from fastapi import HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from dxos_core.config import settings

_JWKS_CACHE: Dict[str, Any] = {}
_JWKS_LAST_FETCH: float = 0.0
_JWKS_CACHE_TTL: float = 300.0  # 5 phút


class UserClaims(BaseModel):
    sub: str
    tenant: str
    roles: List[str] = []
    preferred_username: Optional[str] = None
    name: Optional[str] = None
    azp: Optional[str] = None
    raw: Dict[str, Any] = {}

    def has_role(self, role: str) -> bool:
        return role in self.roles or "dx:platform-admin" in self.roles


def is_allowed_client(client_id: Optional[str]) -> bool:
    if not client_id:
        return False
    configured = {c.strip() for c in os.getenv("ALLOWED_CLIENT_IDS", "").split(",") if c.strip()}
    if client_id in configured:
        return True
    base_clients = {
        "dxos-web",
        "dx-portal",
        "dx-seed",
        "dx-test",
        "dx-sensor",
        "dx-files",
        "dx-flow",
        "svc-files",
        "svc-doc-sign",
        "svc-flow",
        "apisix",
        "admin-cli",
    }
    if client_id in base_clients:
        return True
    if client_id.startswith("dxos-") or client_id.startswith("dx-app-") or client_id.startswith("dx-") or client_id.startswith("svc-"):
        return True
    return False


def get_jwks(force_refresh: bool = False) -> Dict[str, Any]:
    global _JWKS_CACHE, _JWKS_LAST_FETCH
    now = time.time()
    if not force_refresh and _JWKS_CACHE and (now - _JWKS_LAST_FETCH) < _JWKS_CACHE_TTL:
        return _JWKS_CACHE

    jwks_url = f"{settings.keycloak_internal_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(jwks_url)
            if resp.status_code == 200:
                _JWKS_CACHE = resp.json()
                _JWKS_LAST_FETCH = now
                return _JWKS_CACHE
    except Exception:
        if _JWKS_CACHE and not force_refresh:
            return _JWKS_CACHE
    return {"keys": []}


def verify_jwt_token(token: str) -> UserClaims:
    """Xác minh JWT; token sai, hết hạn hoặc thiếu đều trả 401 (không để lọt thành lỗi 500)."""
    try:
        return _verify_jwt_token_raw(token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail={"loi": "Phiên đăng nhập không hợp lệ hoặc đã hết hạn", "ma_loi": "TOKEN_INVALID", "chi_tiet": str(e)[:120]},
            headers={"WWW-Authenticate": "Bearer"},
        )


def _verify_jwt_token_raw(token: str) -> UserClaims:
    """
    Xác minh chữ ký và các claims bắt buộc của JWT token do Keycloak cấp.
    Luôn kiểm tra tính hợp lệ bằng khóa công khai JWKS thực tế, không chấp nhận mock/bypass.
    """
    if not token:
        raise ValueError("Token không được để trống")

    if token.startswith("Bearer "):
        token = token[7:]

    # Lấy key id (kid) từ unverified header
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")

    jwks = get_jwks(force_refresh=False)
    public_key = None
    for key_dict in jwks.get("keys", []):
        if key_dict.get("kid") == kid:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_dict)
            break

    # Nếu không tìm thấy khóa, làm mới JWKS một lần để kiểm tra có khóa mới xoay vòng
    if not public_key:
        jwks = get_jwks(force_refresh=True)
        for key_dict in jwks.get("keys", []):
            if key_dict.get("kid") == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_dict)
                break

    if not public_key:
        raise ValueError("Khóa công khai (kid) không tìm thấy trong JWKS hoặc token không hợp lệ")

    expected_iss = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
    internal_iss = f"{settings.keycloak_internal_url}/realms/{settings.keycloak_realm}"

    payload = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        leeway=10,  # dung sai lệch đồng hồ nhỏ giữa các container
        options={
            "verify_exp": True,
            "verify_nbf": True,
            "verify_aud": False,  # Audience trong Keycloak có thể là 'account'
        },
    )

    # 1. Kiểm tra issuer bắt buộc
    token_iss = payload.get("iss", "")
    if token_iss not in (expected_iss, internal_iss):
        raise ValueError(f"Issuer không hợp lệ: {token_iss}")

    # 2. Kiểm tra authorized party (azp)
    azp = payload.get("azp")
    if azp and not is_allowed_client(azp):
        raise ValueError(f"Client azp '{azp}' không nằm trong danh sách client được phê duyệt")

    if azp == "dx-test" and not settings.demo_mode:
        raise ValueError("Client dx-test chỉ được phép hoạt động khi bật DEMO_MODE")

    return _extract_claims(payload)


def _extract_claims(payload: Dict[str, Any]) -> UserClaims:
    sub = payload.get("sub", "")
    tenant = payload.get("tenant", "")
    azp = payload.get("azp", "")

    # Trích xuất danh sách vai trò
    roles: List[str] = []
    if "roles" in payload and isinstance(payload["roles"], list):
        roles.extend(payload["roles"])
    if "realm_access" in payload and isinstance(payload["realm_access"], dict):
        realm_roles = payload["realm_access"].get("roles", [])
        roles.extend(r for r in realm_roles if r not in roles)

    # Nếu là client service account nội bộ, gán vai trò dx:service
    if azp and (azp.startswith("svc-") or azp in {"svc-doc-sign", "svc-flow", "svc-files"}):
        if "dx:service" not in roles:
            roles.append("dx:service")
        # Không gán địa bàn mặc định: tài khoản dịch vụ không thuộc phường nào

    return UserClaims(
        sub=sub,
        tenant=tenant,
        roles=roles,
        preferred_username=payload.get("preferred_username"),
        name=payload.get("name"),
        azp=payload.get("azp"),
        raw=payload,
    )

# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Kiểm thử đơn vị cho việc đồng bộ vai dx:data-steward và phân quyền DQ (D-MDM-04)."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services"))

from dxos_core import user_sync
from construction.dh import LoiDH, VAI_GIAO_DQ, VAI_QUAN_TRI_DU_LIEU, can_vai, co_vai


@pytest.mark.asyncio
async def test_sync_realm_roles_tao_vai_va_gan_cho_mc_thu():
    """Tạo vai dx:data-steward nếu chưa có và gán cho mc.thu."""
    mock_client = AsyncMock()

    # 1. GET roles: ban đầu chưa có dx:data-steward
    roles_get_res = MagicMock(status_code=200)
    roles_get_res.json.return_value = [{"name": "dx:platform-admin", "id": "r-admin"}]

    # 2. POST role: tạo thành công 201
    role_post_res = MagicMock(status_code=201)

    # 3. GET role representation sau khi tạo
    role_rep_res = MagicMock(status_code=200)
    steward_obj = {"id": "role-steward-uuid", "name": "dx:data-steward", "description": "Chủ quản dữ liệu"}
    role_rep_res.json.return_value = steward_obj

    # 4. GET user mc.thu
    users_get_res = MagicMock(status_code=200)
    user_mc_thu = {"id": "user-thu-uuid", "username": "mc.thu"}
    users_get_res.json.return_value = [user_mc_thu]

    # 5. GET user role-mappings: chưa có dx:data-steward
    user_roles_res = MagicMock(status_code=200)
    user_roles_res.json.return_value = [{"name": "app:cap-phep:mot-cua", "id": "r-mc"}]

    # 6. POST role-mappings: gán vai thành công 204
    assign_post_res = MagicMock(status_code=204)

    def mock_get(url, **kwargs):
        if url.endswith("/roles"):
            return roles_get_res
        if url.endswith("/roles/dx:data-steward"):
            return role_rep_res
        if "?username=mc.thu" in url:
            return users_get_res
        if url.endswith("/role-mappings/realm"):
            return user_roles_res
        return MagicMock(status_code=404)

    def mock_post(url, **kwargs):
        if url.endswith("/roles"):
            return role_post_res
        if url.endswith("/role-mappings/realm"):
            return assign_post_res
        return MagicMock(status_code=400)

    mock_client.get = AsyncMock(side_effect=mock_get)
    mock_client.post = AsyncMock(side_effect=mock_post)

    await user_sync.sync_realm_roles(mock_client, "http://kc-test", "token-test")

    # Kiểm tra gọi POST tạo role
    role_calls = [c for c in mock_client.post.call_args_list if c[0][0].endswith("/roles")]
    assert len(role_calls) == 1
    assert role_calls[0][1]["json"]["name"] == "dx:data-steward"

    # Kiểm tra gọi POST gán role cho mc.thu
    assign_calls = [c for c in mock_client.post.call_args_list if "role-mappings/realm" in c[0][0]]
    assert len(assign_calls) == 1
    assert assign_calls[0][1]["json"] == [steward_obj]


@pytest.mark.asyncio
async def test_sync_realm_roles_idempotent_khi_da_co_vai():
    """Khi vai dx:data-steward và mc.thu đã có vai, không tạo hay gán lại."""
    mock_client = AsyncMock()
    steward_obj = {"id": "role-steward-uuid", "name": "dx:data-steward"}

    roles_get_res = MagicMock(status_code=200)
    roles_get_res.json.return_value = [steward_obj]

    users_get_res = MagicMock(status_code=200)
    users_get_res.json.return_value = [{"id": "user-thu-uuid", "username": "mc.thu"}]

    user_roles_res = MagicMock(status_code=200)
    user_roles_res.json.return_value = [steward_obj]

    def mock_get(url, **kwargs):
        if url.endswith("/roles"):
            return roles_get_res
        if "?username=mc.thu" in url:
            return users_get_res
        if url.endswith("/role-mappings/realm"):
            return user_roles_res
        return MagicMock(status_code=404)

    mock_client.get = AsyncMock(side_effect=mock_get)
    mock_client.post = AsyncMock()

    await user_sync.sync_realm_roles(mock_client, "http://kc-test", "token-test")

    # Không gọi POST nào vì đã tồn tại và đã được gán
    assert mock_client.post.call_count == 0


def test_phan_quyen_dq_data_steward():
    """Tài khoản có vai dx:data-steward giao và đóng được issue DQ; vai thường bị 403."""
    claims_steward = SimpleNamespace(roles=["app:cap-phep:mot-cua", "dx:data-steward"], tenant="phuong-a", sub="sub-thu")
    claims_lanh_dao = SimpleNamespace(roles=["app:cap-phep:lanh-dao"], tenant="phuong-a", sub="sub-hoa")
    claims_tham_dinh = SimpleNamespace(roles=["app:cap-phep:tham-dinh"], tenant="phuong-a", sub="sub-binh")
    claims_mot_cua = SimpleNamespace(roles=["app:cap-phep:mot-cua"], tenant="phuong-a", sub="sub-thu-no-role")

    # 1. Giao vấn đề: VAI_GIAO_DQ cho phép lanh-dao, tenant-admin, data-steward
    assert can_vai(claims_steward, VAI_GIAO_DQ) is None
    assert can_vai(claims_lanh_dao, VAI_GIAO_DQ) is None
    with pytest.raises(LoiDH) as ex1:
        can_vai(claims_tham_dinh, VAI_GIAO_DQ)
    assert ex1.value.status_code == 403

    with pytest.raises(LoiDH) as ex2:
        can_vai(claims_mot_cua, VAI_GIAO_DQ)
    assert ex2.value.status_code == 403

    # 2. Đóng vấn đề: VAI_QUAN_TRI_DU_LIEU gồm tenant-admin, data-steward
    assert co_vai(claims_steward, VAI_QUAN_TRI_DU_LIEU) is True
    assert co_vai(claims_tham_dinh, VAI_QUAN_TRI_DU_LIEU) is False
    assert co_vai(claims_mot_cua, VAI_QUAN_TRI_DU_LIEU) is False

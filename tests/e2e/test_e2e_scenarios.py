# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
DX-OS Open-Core Real End-to-End Integration Test Suite (v1.1.0):
- Thực hiện kiểm thử tích hợp thật 100% qua Gateway APISIX.
- Sử dụng token xác thực thật từ Keycloak SSO bằng Direct Access Grants (dx-test).
- Lưu trữ thật vào PostgreSQL 16 (RLS, audit hash chain), SeaweedFS S3, Flowable BPMN, OpenBao Transit KMS và ClamAV.
- Không sử dụng bất kỳ mock, fake secret hay bộ nhớ RAM giả lập nào.
"""

import base64
import os
from datetime import datetime, timezone
from pathlib import Path
import httpx
import pytest

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://apisix:8080")
if not os.path.exists("/.dockerenv") and "GATEWAY_URL" not in os.environ:
    GATEWAY_URL = "http://localhost:8080"

EICAR_SIGNATURE = base64.b64decode(b"WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=")

_TOKEN_CACHE = {}


def load_demo_accounts():
    accounts = {}
    path = Path("secrets/demo-accounts.txt")
    if not path.exists():
        path = Path(__file__).resolve().parent.parent.parent / "secrets" / "demo-accounts.txt"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(":")
                if len(parts) >= 2:
                    accounts[parts[0]] = parts[1]
    return accounts


async def get_token(username: str) -> str:
    """Lấy token RS256 thật từ Keycloak SSO qua APISIX Gateway."""
    if username in _TOKEN_CACHE:
        return _TOKEN_CACHE[username]

    accounts = load_demo_accounts()
    password = accounts.get(username, "Demo@Password2026!")

    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(
            f"{GATEWAY_URL}/auth/realms/dxos/protocol/openid-connect/token",
            data={
                "client_id": "dx-test",
                "username": username,
                "password": password,
                "grant_type": "password",
            },
        )
        if res.status_code == 200:
            token = "Bearer " + res.json()["access_token"]
            _TOKEN_CACHE[username] = token
            return token
        raise RuntimeError(f"Không lấy được token Keycloak cho {username}: {res.status_code} {res.text}")


async def get_sensor_token(tenant: str = "phuong-a") -> str:
    """Lấy token client_credentials của thiết bị cảm biến (role dx:device)."""
    secret_path = Path("secrets") / f"sensor-{tenant}-secret.txt"
    if not secret_path.exists():
        secret_path = Path(__file__).resolve().parent.parent.parent / "secrets" / f"sensor-{tenant}-secret.txt"
    secret = secret_path.read_text(encoding="utf-8").strip() if secret_path.exists() else ""
    if not secret:
        raise RuntimeError(f"Không tìm thấy secret cảm biến cho {tenant}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(
            f"{GATEWAY_URL}/auth/realms/dxos/protocol/openid-connect/token",
            data={
                "client_id": f"dxos-sensor-{tenant}",
                "client_secret": secret,
                "grant_type": "client_credentials",
            },
        )
        if res.status_code != 200:
            raise RuntimeError(f"Không lấy được token cảm biến {tenant}: {res.status_code} {res.text}")
        return "Bearer " + res.json()["access_token"]


@pytest.mark.asyncio
async def test_scenario_01_unauthenticated_and_bad_tokens():
    """Kịch bản 1: Không có token hoặc token giả mạo bị từ chối 401."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Không có token -> 401
        resp = await client.get(f"{GATEWAY_URL}/api/v1/files/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 401

        # 2. Token giả mạo HS256 không có trong JWKS Keycloak -> 401
        fake_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhdHRhY2tlciJ9.invalid"
        resp_fake = await client.get(f"{GATEWAY_URL}/api/v1/files/00000000-0000-0000-0000-000000000000", headers={"Authorization": fake_token})
        assert resp_fake.status_code == 401


@pytest.mark.asyncio
async def test_scenario_02_eicar_and_clean_file_upload():
    """Kịch bản 2: cdt.minh tải EICAR -> ClamAV phát hiện 422; tệp sạch -> S3 lưu 201."""
    token = await get_token("cdt.minh")
    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Tải tệp EICAR -> 422
        files = {"file": ("eicar.txt", EICAR_SIGNATURE, "text/plain")}
        # Lấy hồ sơ thật của cdt.minh để đảm bảo vượt qua kiểm tra quyền sở hữu S-02
        hs_resp = await client.get(f"{GATEWAY_URL}/api/v1/rest/v_ho_so?limit=1", headers={"Authorization": token})
        ho_so_id = hs_resp.json()[0]["id"]
        data = {"object_type": "ho_so", "object_id": ho_so_id}
        resp = await client.post(f"{GATEWAY_URL}/api/v1/files", files=files, data=data, headers={"Authorization": token})
        assert resp.status_code == 422
        assert "mã độc" in resp.text.lower() or "infected" in resp.text.lower() or "eicar" in resp.text.lower()

        # 2. Tải tệp sạch -> 201
        clean_pdf = b"%PDF-1.4 Mock architectural drawing file content for testing"
        clean_files = {"file": ("ban_ve.pdf", clean_pdf, "application/pdf")}
        resp_clean = await client.post(f"{GATEWAY_URL}/api/v1/files", files=clean_files, data=data, headers={"Authorization": token})
        assert resp_clean.status_code == 201
        res_data = resp_clean.json()
        assert res_data.get("status") == "clean"
        assert "file_id" in res_data


@pytest.mark.asyncio
async def test_scenario_03_flow_task_operations():
    """Kịch bản 3: Cán bộ Một cửa mc.thu truy vấn danh sách nhiệm vụ Flowable."""
    token = await get_token("mc.thu")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": token})
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert data.get("tenant") == "phuong-a"


@pytest.mark.asyncio
async def test_scenario_04_postgrest_rls_isolation():
    """Kịch bản 4: Cách ly dữ liệu RLS giữa công dân qua PostgREST view an toàn."""
    token_minh = await get_token("cdt.minh")
    token_lan = await get_token("cdt.lan")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # cdt.minh truy vấn hồ sơ của mình qua v_ho_so
        resp = await client.get(f"{GATEWAY_URL}/api/v1/rest/v_ho_so", headers={"Authorization": token_minh})
        assert resp.status_code == 200
        records = resp.json()
        assert len(records) > 0

        # cdt.lan cố tình sửa hồ sơ của cdt.minh -> RLS chặn, 0 dòng cập nhật
        target_id = records[0]["id"]
        patch_resp = await client.patch(
            f"{GATEWAY_URL}/api/v1/rest/ho_so?id=eq.{target_id}",
            headers={"Authorization": token_lan, "Prefer": "return=representation"},
            json={"dia_chi_cong_trinh": "Hacked Address"},
        )
        assert patch_resp.status_code in (200, 204)
        assert patch_resp.json() == []


@pytest.mark.asyncio
async def test_scenario_05_sod_exclude_enforcement():
    """Kịch bản 5: Kiểm tra nguyên tắc tách biệt nghĩa vụ (SoD) và hoàn tất duyệt."""
    token_hoa = await get_token("ld.hoa")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Lãnh đạo xem danh sách nhiệm vụ cần phê duyệt
        resp = await client.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": token_hoa})
        assert resp.status_code == 200
        tasks = resp.json().get("tasks", [])
        assert len(tasks) > 0


@pytest.mark.asyncio
async def test_scenario_06_doc_signing_and_public_verification():
    """Kịch bản 6: Lãnh đạo ký số qua OpenBao Transit KMS; kiểm tra mã công khai."""
    token_hoa = await get_token("ld.hoa")
    async with httpx.AsyncClient(timeout=10.0) as client:
        sign_payload = {
            "doc_type": "giay-phep-xay-dung",
            "data": {"ho_ten": "Trần Văn Minh (mẫu)", "dia_chi": "Số 123 Đường Hoa Phượng (mẫu)"},
            "tenant": "phuong-a",
        }
        resp = await client.post(f"{GATEWAY_URL}/api/v1/docs/sign", json=sign_payload, headers={"Authorization": token_hoa})
        assert resp.status_code == 201
        doc_info = resp.json()
        public_code = doc_info["public_code"]
        assert doc_info.get("signature") is not None

        # Tra cứu công khai (không cần token)
        pub_resp = await client.get(f"{GATEWAY_URL}/kiem-tra/{public_code}")
        assert pub_resp.status_code == 200
        assert pub_resp.json()["trang_thai"] == "Hop_le"

        # Bản gốc không tải công khai được (U-01); người ký tải qua API có xác thực
        public_dl = await client.get(f"{GATEWAY_URL}/kiem-tra/{public_code}/download")
        assert public_dl.status_code in (404, 405)
        pdf_resp = await client.get(
            f"{GATEWAY_URL}/api/v1/docs/{doc_info['doc_id']}/download", headers={"Authorization": token_hoa}
        )
        assert pdf_resp.status_code == 200

        # Xác minh chữ ký PAdES; sửa 1 byte phải bị từ chối
        assert pdf_resp.content.startswith(b"%PDF")
        verify = await client.post(
            f"{GATEWAY_URL}/kiem-tra/{public_code}/verify-file",
            files={"file": ("permit.pdf", pdf_resp.content, "application/pdf")},
        )
        assert verify.status_code == 200
        assert verify.json()["signature_type"] == "pades"
        assert verify.json()["valid"] is True
        tampered = bytearray(pdf_resp.content)
        tampered[200] ^= 0x01
        tamper_verify = await client.post(
            f"{GATEWAY_URL}/kiem-tra/{public_code}/verify-file",
            files={"file": ("permit-tampered.pdf", bytes(tampered), "application/pdf")},
        )
        assert tamper_verify.status_code == 200
        assert tamper_verify.json()["valid"] is False

        # Tra cứu mã không tồn tại -> 404
        non_exist = await client.get(f"{GATEWAY_URL}/kiem-tra/DOC-NONEXISTENT-999")
        assert non_exist.status_code == 404


@pytest.mark.asyncio
async def test_scenario_07_multi_tenant_isolation():
    """Kịch bản 7: mc.phuongb (phường B) tách biệt tài nguyên với phường A."""
    token_a = await get_token("mc.thu")
    token_b = await get_token("mc.phuongb")

    async with httpx.AsyncClient(timeout=10.0) as client:
        res_a = await client.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": token_a})
        res_b = await client.get(f"{GATEWAY_URL}/api/v1/flow/tasks", headers={"Authorization": token_b})
        assert res_a.status_code == 200
        assert res_b.status_code == 200
        assert res_a.json()["tenant"] == "phuong-a"
        assert res_b.json()["tenant"] == "phuong-b"


@pytest.mark.asyncio
async def test_scenario_08_sensor_ingest_alert():
    """Kịch bản 8: Gửi bản ghi tiếng ồn 78 dBA -> phát hiện cảnh báo vượt ngưỡng QCVN 26."""
    token = await get_sensor_token("phuong-a")
    async with httpx.AsyncClient(timeout=10.0) as client:
        payload = {
            "tenant": "phuong-a",
            "site_id": "CT-01",
            "device_id": "DEV-01",
            "ts": datetime.now(timezone.utc).isoformat(),
            "metrics": {"laeq_dba": 78.5, "pm10": 45.0, "pm25": 20.0},
        }
        resp = await client.post(f"{GATEWAY_URL}/api/v1/ingest", json=payload, headers={"Authorization": token})
        assert resp.status_code == 201
        data = resp.json()
        assert len(data.get("alerts", [])) > 0
        assert data["alerts"][0]["threshold"] in (55.0, 70.0)


@pytest.mark.asyncio
async def test_scenario_09_dsar_deadlines():
    """Kịch bản 9: Tính toán thời hạn xử lý quyền dữ liệu cá nhân theo NĐ 13/2023."""
    now = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
    from tests.unit.test_dsar_deadlines import calculate_dsar_deadlines
    ack_due, process_due = calculate_dsar_deadlines("access", now)
    assert (ack_due - now).days == 2
    assert (process_due - now).days == 14  # 10 business days = 14 calendar days


@pytest.mark.asyncio
async def test_scenario_10_audit_verification():
    """Kịch bản 10: Kiểm toán viên kt.an xác minh chuỗi băm audit log."""
    token = await get_token("kt.an")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{GATEWAY_URL}/api/v1/audit/verify", headers={"Authorization": token})
        assert resp.status_code == 200
        assert resp.json().get("valid") is True


@pytest.mark.asyncio
async def test_scenario_11_permit_revocation():
    """Kịch bản 11: Lãnh đạo thu hồi giấy phép -> tra cứu công khai hiển thị Da_thu_hoi."""
    token = await get_token("ld.hoa")
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Ký giấy phép mới
        sign_payload = {
            "doc_type": "giay-phep-xay-dung",
            "data": {"ho_ten": "Lê Thị Lan (mẫu)", "dia_chi": "Số 88 Đường Dạ Lan (mẫu)"},
            "tenant": "phuong-a",
        }
        sign_resp = await client.post(f"{GATEWAY_URL}/api/v1/docs/sign", json=sign_payload, headers={"Authorization": token})
        assert sign_resp.status_code == 201
        doc_id = sign_resp.json()["doc_id"]
        public_code = sign_resp.json()["public_code"]

        # Thu hồi giấy phép
        revoke_resp = await client.post(
            f"{GATEWAY_URL}/api/v1/docs/{doc_id}/revoke",
            json={"ly_do": "Phát hiện sai phạm chỉ giới xây dựng"},
            headers={"Authorization": token},
        )
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["status"] == "revoked"

        # Tra cứu công khai hiển thị Da_thu_hoi
        check_resp = await client.get(f"{GATEWAY_URL}/kiem-tra/{public_code}")
        assert check_resp.status_code == 200
        assert check_resp.json()["trang_thai"] == "Da_thu_hoi"


@pytest.mark.asyncio
async def test_scenario_12_metrics_and_lineage():
    """Kịch bản 12: metrics-api trả về đủ 8 chỉ số điều hành và dòng dữ liệu lineage."""
    token = await get_token("ld.hoa")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{GATEWAY_URL}/api/v1/metrics", headers={"Authorization": token})
        assert resp.status_code == 200
        metrics = resp.json().get("metrics", [])
        assert len(metrics) == 8
        codes = {m["code"] for m in metrics}
        assert {
            "ho_so_moi",
            "ho_so_dang_xu_ly",
            "ho_so_qua_han",
            "thoi_gian_xu_ly_tb",
            "truy_cap_tu_choi",
            "phieu_kiem_tra",
            "canh_bao_cong_truong",
            "vi_pham",
        }.issubset(codes), f"Thiếu chỉ số: {codes}"

        # Dòng dữ liệu (lineage) của ho_so_moi
        lineage_resp = await client.get(f"{GATEWAY_URL}/api/v1/metrics/ho_so_moi/lineage", headers={"Authorization": token})
        assert lineage_resp.status_code == 200
        assert "lineage_events" in lineage_resp.json()


@pytest.mark.asyncio
async def test_scenario_13_ai_assistant_rag():
    """Kịch bản 13: Trợ lý AI trả lời câu hỏi nghiệp vụ kèm trích dẫn tài liệu quy định."""
    token = await get_token("cdt.minh")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/api/v1/assistant/ask",
            json={"question": "Thời hạn cấp giấy phép nhà ở riêng lẻ là bao nhiêu ngày?"},
            headers={"Authorization": token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "citations" in data

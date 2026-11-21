# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

"""FIX-V11-09: đường dẫn /api/ không có route trả 404 JSON; route cụ thể và web vẫn như cũ."""

import httpx

GW = "http://localhost:8080"


def test_V11_09_api_khong_ton_tai_tra_404_json():
    with httpx.Client(timeout=5.0) as client:
        for path in ("/api/v1/khong-co", "/api/khong-co", "/api/v2/ho-so"):
            resp = client.get(GW + path)
            assert resp.status_code == 404, path
            assert resp.headers.get("content-type", "").startswith("application/json"), path
            assert resp.json()["detail"]["ma_loi"] == "NOT_FOUND", path


def test_V11_09_route_cu_the_khong_bi_che():
    with httpx.Client(timeout=5.0) as client:
        assert client.get(GW + "/api/v1/health").status_code == 200
        web = client.get(GW + "/")
        assert web.status_code == 200 and "text/html" in web.headers.get("content-type", "")
